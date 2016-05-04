# RhodeCode VCSServer provides access to different vcs backends via network.
# Copyright (C) 2014-2016 RodeCode GmbH
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301  USA

import io
import logging
import stat
import sys
import urllib
import urllib2

from hgext import largefiles, rebase
from hgext.strip import strip as hgext_strip
from mercurial import commands
from mercurial import unionrepo

from vcsserver import exceptions
from vcsserver.base import RepoFactory
from vcsserver.hgcompat import (
    archival, bin, clone, config as hgconfig, diffopts, hex, hg_url,
    httpbasicauthhandler, httpdigestauthhandler, httppeer, localrepository,
    match, memctx, exchange, memfilectx, nullrev, patch, peer, revrange, ui,
    Abort, LookupError, RepoError, RepoLookupError, InterventionRequired,
    RequirementError)

log = logging.getLogger(__name__)


def make_ui_from_config(repo_config):
    baseui = ui.ui()

    # clean the baseui object
    baseui._ocfg = hgconfig.config()
    baseui._ucfg = hgconfig.config()
    baseui._tcfg = hgconfig.config()

    for section, option, value in repo_config:
        baseui.setconfig(section, option, value)

    # make our hgweb quiet so it doesn't print output
    baseui.setconfig('ui', 'quiet', 'true')

    # force mercurial to only use 1 thread, otherwise it may try to set a
    # signal in a non-main thread, thus generating a ValueError.
    baseui.setconfig('worker', 'numcpus', 1)

    return baseui


def reraise_safe_exceptions(func):
    """Decorator for converting mercurial exceptions to something neutral."""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (Abort, InterventionRequired):
            raise_from_original(exceptions.AbortException)
        except RepoLookupError:
            raise_from_original(exceptions.LookupException)
        except RequirementError:
            raise_from_original(exceptions.RequirementException)
        except RepoError:
            raise_from_original(exceptions.VcsException)
        except LookupError:
            raise_from_original(exceptions.LookupException)
        except Exception as e:
            if not hasattr(e, '_vcs_kind'):
                log.exception("Unhandled exception in hg remote call")
                raise_from_original(exceptions.UnhandledException)
            raise
    return wrapper


def raise_from_original(new_type):
    """
    Raise a new exception type with original args and traceback.
    """
    _, original, traceback = sys.exc_info()
    try:
        raise new_type(*original.args), None, traceback
    finally:
        del traceback


class MercurialFactory(RepoFactory):

    def _create_config(self, config, hooks=True):
        if not hooks:
            hooks_to_clean = frozenset((
                'changegroup.repo_size', 'preoutgoing.pre_pull',
                'outgoing.pull_logger', 'prechangegroup.pre_push'))
            new_config = []
            for section, option, value in config:
                if section == 'hooks' and option in hooks_to_clean:
                    continue
                new_config.append((section, option, value))
            config = new_config

        baseui = make_ui_from_config(config)
        return baseui

    def _create_repo(self, wire, create):
        baseui = self._create_config(wire["config"])
        return localrepository(baseui, wire["path"], create)


class HgRemote(object):

    def __init__(self, factory):
        self._factory = factory

        self._bulk_methods = {
            "affected_files": self.ctx_files,
            "author": self.ctx_user,
            "branch": self.ctx_branch,
            "children": self.ctx_children,
            "date": self.ctx_date,
            "message": self.ctx_description,
            "parents": self.ctx_parents,
            "status": self.ctx_status,
            "_file_paths": self.ctx_list,
        }

    @reraise_safe_exceptions
    def archive_repo(self, archive_path, mtime, file_info, kind):
        if kind == "tgz":
            archiver = archival.tarit(archive_path, mtime, "gz")
        elif kind == "tbz2":
            archiver = archival.tarit(archive_path, mtime, "bz2")
        elif kind == 'zip':
            archiver = archival.zipit(archive_path, mtime)
        else:
            raise exceptions.ArchiveException(
                'Remote does not support: "%s".' % kind)

        for f_path, f_mode, f_is_link, f_content in file_info:
            archiver.addfile(f_path, f_mode, f_is_link, f_content)
        archiver.done()

    @reraise_safe_exceptions
    def bookmarks(self, wire):
        repo = self._factory.repo(wire)
        return dict(repo._bookmarks)

    @reraise_safe_exceptions
    def branches(self, wire, normal, closed):
        repo = self._factory.repo(wire)
        iter_branches = repo.branchmap().iterbranches()
        bt = {}
        for branch_name, _heads, tip, is_closed in iter_branches:
            if normal and not is_closed:
                bt[branch_name] = tip
            if closed and is_closed:
                bt[branch_name] = tip

        return bt

    @reraise_safe_exceptions
    def bulk_request(self, wire, rev, pre_load):
        result = {}
        for attr in pre_load:
            try:
                method = self._bulk_methods[attr]
                result[attr] = method(wire, rev)
            except KeyError:
                raise exceptions.VcsException(
                    'Unknown bulk attribute: "%s"' % attr)
        return result

    @reraise_safe_exceptions
    def clone(self, wire, source, dest, update_after_clone=False, hooks=True):
        baseui = self._factory._create_config(wire["config"], hooks=hooks)
        clone(baseui, source, dest, noupdate=not update_after_clone)

    @reraise_safe_exceptions
    def commitctx(
            self, wire, message, parents, commit_time, commit_timezone,
            user, files, extra, removed, updated):

        def _filectxfn(_repo, memctx, path):
            """
            Marks given path as added/changed/removed in a given _repo. This is
            for internal mercurial commit function.
            """

            # check if this path is removed
            if path in removed:
                # returning None is a way to mark node for removal
                return None

            # check if this path is added
            for node in updated:
                if node['path'] == path:
                    return memfilectx(
                        _repo,
                        path=node['path'],
                        data=node['content'],
                        islink=False,
                        isexec=bool(node['mode'] & stat.S_IXUSR),
                        copied=False,
                        memctx=memctx)

            raise exceptions.AbortException(
                "Given path haven't been marked as added, "
                "changed or removed (%s)" % path)

        repo = self._factory.repo(wire)

        commit_ctx = memctx(
            repo=repo,
            parents=parents,
            text=message,
            files=files,
            filectxfn=_filectxfn,
            user=user,
            date=(commit_time, commit_timezone),
            extra=extra)

        n = repo.commitctx(commit_ctx)
        new_id = hex(n)

        return new_id

    @reraise_safe_exceptions
    def ctx_branch(self, wire, revision):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        return ctx.branch()

    @reraise_safe_exceptions
    def ctx_children(self, wire, revision):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        return [child.rev() for child in ctx.children()]

    @reraise_safe_exceptions
    def ctx_date(self, wire, revision):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        return ctx.date()

    @reraise_safe_exceptions
    def ctx_description(self, wire, revision):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        return ctx.description()

    @reraise_safe_exceptions
    def ctx_diff(
            self, wire, revision, git=True, ignore_whitespace=True, context=3):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        result = ctx.diff(
            git=git, ignore_whitespace=ignore_whitespace, context=context)
        return list(result)

    @reraise_safe_exceptions
    def ctx_files(self, wire, revision):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        return ctx.files()

    @reraise_safe_exceptions
    def ctx_list(self, path, revision):
        repo = self._factory.repo(path)
        ctx = repo[revision]
        return list(ctx)

    @reraise_safe_exceptions
    def ctx_parents(self, wire, revision):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        return [parent.rev() for parent in ctx.parents()]

    @reraise_safe_exceptions
    def ctx_substate(self, wire, revision):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        return ctx.substate

    @reraise_safe_exceptions
    def ctx_status(self, wire, revision):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        status = repo[ctx.p1().node()].status(other=ctx.node())
        # object of status (odd, custom named tuple in mercurial) is not
        # correctly serializable via Pyro, we make it a list, as the underling
        # API expects this to be a list
        return list(status)

    @reraise_safe_exceptions
    def ctx_user(self, wire, revision):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        return ctx.user()

    @reraise_safe_exceptions
    def check_url(self, url, config):
        _proto = None
        if '+' in url[:url.find('://')]:
            _proto = url[0:url.find('+')]
            url = url[url.find('+') + 1:]
        handlers = []
        url_obj = hg_url(url)
        test_uri, authinfo = url_obj.authinfo()
        url_obj.passwd = '*****'
        cleaned_uri = str(url_obj)

        if authinfo:
            # create a password manager
            passmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            passmgr.add_password(*authinfo)

            handlers.extend((httpbasicauthhandler(passmgr),
                             httpdigestauthhandler(passmgr)))

        o = urllib2.build_opener(*handlers)
        o.addheaders = [('Content-Type', 'application/mercurial-0.1'),
                        ('Accept', 'application/mercurial-0.1')]

        q = {"cmd": 'between'}
        q.update({'pairs': "%s-%s" % ('0' * 40, '0' * 40)})
        qs = '?%s' % urllib.urlencode(q)
        cu = "%s%s" % (test_uri, qs)
        req = urllib2.Request(cu, None, {})

        try:
            resp = o.open(req)
            if resp.code != 200:
                raise exceptions.URLError('Return Code is not 200')
        except Exception as e:
            # means it cannot be cloned
            raise exceptions.URLError("[%s] org_exc: %s" % (cleaned_uri, e))

        # now check if it's a proper hg repo, but don't do it for svn
        try:
            if _proto == 'svn':
                pass
            else:
                # check for pure hg repos
                httppeer(make_ui_from_config(config), url).lookup('tip')
        except Exception as e:
            raise exceptions.URLError(
                "url [%s] does not look like an hg repo org_exc: %s"
                % (cleaned_uri, e))

        return True

    @reraise_safe_exceptions
    def diff(
            self, wire, rev1, rev2, file_filter, opt_git, opt_ignorews,
            context):
        repo = self._factory.repo(wire)

        if file_filter:
            filter = match(file_filter[0], '', [file_filter[1]])
        else:
            filter = file_filter
        opts = diffopts(git=opt_git, ignorews=opt_ignorews, context=context)

        try:
            return "".join(patch.diff(
                repo, node1=rev1, node2=rev2, match=filter, opts=opts))
        except RepoLookupError:
            raise exceptions.LookupException()

    @reraise_safe_exceptions
    def file_history(self, wire, revision, path, limit):
        repo = self._factory.repo(wire)

        ctx = repo[revision]
        fctx = ctx.filectx(path)

        def history_iter():
            limit_rev = fctx.rev()
            for obj in reversed(list(fctx.filelog())):
                obj = fctx.filectx(obj)
                if limit_rev >= obj.rev():
                    yield obj

        history = []
        for cnt, obj in enumerate(history_iter()):
            if limit and cnt >= limit:
                break
            history.append(hex(obj.node()))

        return [x for x in history]

    @reraise_safe_exceptions
    def file_history_untill(self, wire, revision, path, limit):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        fctx = ctx.filectx(path)

        file_log = list(fctx.filelog())
        if limit:
            # Limit to the last n items
            file_log = file_log[-limit:]

        return [hex(fctx.filectx(cs).node()) for cs in reversed(file_log)]

    @reraise_safe_exceptions
    def fctx_annotate(self, wire, revision, path):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        fctx = ctx.filectx(path)

        result = []
        for i, annotate_data in enumerate(fctx.annotate()):
            ln_no = i + 1
            sha = hex(annotate_data[0].node())
            result.append((ln_no, sha, annotate_data[1]))
        return result

    @reraise_safe_exceptions
    def fctx_data(self, wire, revision, path):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        fctx = ctx.filectx(path)
        return fctx.data()

    @reraise_safe_exceptions
    def fctx_flags(self, wire, revision, path):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        fctx = ctx.filectx(path)
        return fctx.flags()

    @reraise_safe_exceptions
    def fctx_size(self, wire, revision, path):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        fctx = ctx.filectx(path)
        return fctx.size()

    @reraise_safe_exceptions
    def get_all_commit_ids(self, wire, name):
        repo = self._factory.repo(wire)
        revs = repo.filtered(name).changelog.index
        return map(lambda x: hex(x[7]), revs)[:-1]

    @reraise_safe_exceptions
    def get_config_value(self, wire, section, name, untrusted=False):
        repo = self._factory.repo(wire)
        return repo.ui.config(section, name, untrusted=untrusted)

    @reraise_safe_exceptions
    def get_config_bool(self, wire, section, name, untrusted=False):
        repo = self._factory.repo(wire)
        return repo.ui.configbool(section, name, untrusted=untrusted)

    @reraise_safe_exceptions
    def get_config_list(self, wire, section, name, untrusted=False):
        repo = self._factory.repo(wire)
        return repo.ui.configlist(section, name, untrusted=untrusted)

    @reraise_safe_exceptions
    def is_large_file(self, wire, path):
        return largefiles.lfutil.isstandin(path)

    @reraise_safe_exceptions
    def in_store(self, wire, sha):
        repo = self._factory.repo(wire)
        return largefiles.lfutil.instore(repo, sha)

    @reraise_safe_exceptions
    def in_user_cache(self, wire, sha):
        repo = self._factory.repo(wire)
        return largefiles.lfutil.inusercache(repo.ui, sha)

    @reraise_safe_exceptions
    def store_path(self, wire, sha):
        repo = self._factory.repo(wire)
        return largefiles.lfutil.storepath(repo, sha)

    @reraise_safe_exceptions
    def link(self, wire, sha, path):
        repo = self._factory.repo(wire)
        largefiles.lfutil.link(
            largefiles.lfutil.usercachepath(repo.ui, sha), path)

    @reraise_safe_exceptions
    def localrepository(self, wire, create=False):
        self._factory.repo(wire, create=create)

    @reraise_safe_exceptions
    def lookup(self, wire, revision, both):
        # TODO Paris: Ugly hack to "deserialize" long for msgpack
        if isinstance(revision, float):
            revision = long(revision)
        repo = self._factory.repo(wire)
        try:
            ctx = repo[revision]
        except RepoLookupError:
            raise exceptions.LookupException(revision)
        except LookupError as e:
            raise exceptions.LookupException(e.name)

        if not both:
            return ctx.hex()

        ctx = repo[ctx.hex()]
        return ctx.hex(), ctx.rev()

    @reraise_safe_exceptions
    def pull(self, wire, url, commit_ids=None):
        repo = self._factory.repo(wire)
        remote = peer(repo, {}, url)
        if commit_ids:
            commit_ids = [bin(commit_id) for commit_id in commit_ids]

        return exchange.pull(
            repo, remote, heads=commit_ids, force=None).cgresult

    @reraise_safe_exceptions
    def revision(self, wire, rev):
        repo = self._factory.repo(wire)
        ctx = repo[rev]
        return ctx.rev()

    @reraise_safe_exceptions
    def rev_range(self, wire, filter):
        repo = self._factory.repo(wire)
        revisions = [rev for rev in revrange(repo, filter)]
        return revisions

    @reraise_safe_exceptions
    def rev_range_hash(self, wire, node):
        repo = self._factory.repo(wire)

        def get_revs(repo, rev_opt):
            if rev_opt:
                revs = revrange(repo, rev_opt)
                if len(revs) == 0:
                    return (nullrev, nullrev)
                return max(revs), min(revs)
            else:
                return len(repo) - 1, 0

        stop, start = get_revs(repo, [node + ':'])
        revs = [hex(repo[r].node()) for r in xrange(start, stop + 1)]
        return revs

    @reraise_safe_exceptions
    def revs_from_revspec(self, wire, rev_spec, *args, **kwargs):
        other_path = kwargs.pop('other_path', None)

        # case when we want to compare two independent repositories
        if other_path and other_path != wire["path"]:
            baseui = self._factory._create_config(wire["config"])
            repo = unionrepo.unionrepository(baseui, other_path, wire["path"])
        else:
            repo = self._factory.repo(wire)
        return list(repo.revs(rev_spec, *args))

    @reraise_safe_exceptions
    def strip(self, wire, revision, update, backup):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        hgext_strip(
            repo.baseui, repo, ctx.node(), update=update, backup=backup)

    @reraise_safe_exceptions
    def tag(self, wire, name, revision, message, local, user,
            tag_time, tag_timezone):
        repo = self._factory.repo(wire)
        ctx = repo[revision]
        node = ctx.node()

        date = (tag_time, tag_timezone)
        try:
            repo.tag(name, node, message, local, user, date)
        except Abort:
            log.exception("Tag operation aborted")
            raise exceptions.AbortException()

    @reraise_safe_exceptions
    def tags(self, wire):
        repo = self._factory.repo(wire)
        return repo.tags()

    @reraise_safe_exceptions
    def update(self, wire, node=None, clean=False):
        repo = self._factory.repo(wire)
        baseui = self._factory._create_config(wire['config'])
        commands.update(baseui, repo, node=node, clean=clean)

    @reraise_safe_exceptions
    def identify(self, wire):
        repo = self._factory.repo(wire)
        baseui = self._factory._create_config(wire['config'])
        output = io.BytesIO()
        baseui.write = output.write
        # This is required to get a full node id
        baseui.debugflag = True
        commands.identify(baseui, repo, id=True)

        return output.getvalue()

    @reraise_safe_exceptions
    def pull_cmd(self, wire, source, bookmark=None, branch=None, revision=None,
                 hooks=True):
        repo = self._factory.repo(wire)
        baseui = self._factory._create_config(wire['config'], hooks=hooks)

        # Mercurial internally has a lot of logic that checks ONLY if
        # option is defined, we just pass those if they are defined then
        opts = {}
        if bookmark:
            opts['bookmark'] = bookmark
        if branch:
            opts['branch'] = branch
        if revision:
            opts['rev'] = revision

        commands.pull(baseui, repo, source, **opts)

    @reraise_safe_exceptions
    def heads(self, wire, branch=None):
        repo = self._factory.repo(wire)
        baseui = self._factory._create_config(wire['config'])
        output = io.BytesIO()

        def write(data, **unused_kwargs):
            output.write(data)

        baseui.write = write
        if branch:
            args = [branch]
        else:
            args = []
        commands.heads(baseui, repo, template='{node} ', *args)

        return output.getvalue()

    @reraise_safe_exceptions
    def ancestor(self, wire, revision1, revision2):
        repo = self._factory.repo(wire)
        baseui = self._factory._create_config(wire['config'])
        output = io.BytesIO()
        baseui.write = output.write
        commands.debugancestor(baseui, repo, revision1, revision2)

        return output.getvalue()

    @reraise_safe_exceptions
    def push(self, wire, revisions, dest_path, hooks=True,
             push_branches=False):
        repo = self._factory.repo(wire)
        baseui = self._factory._create_config(wire['config'], hooks=hooks)
        commands.push(baseui, repo, dest=dest_path, rev=revisions,
                      new_branch=push_branches)

    @reraise_safe_exceptions
    def merge(self, wire, revision):
        repo = self._factory.repo(wire)
        baseui = self._factory._create_config(wire['config'])
        repo.ui.setconfig('ui', 'merge', 'internal:dump')
        commands.merge(baseui, repo, rev=revision)

    @reraise_safe_exceptions
    def commit(self, wire, message, username):
        repo = self._factory.repo(wire)
        baseui = self._factory._create_config(wire['config'])
        repo.ui.setconfig('ui', 'username', username)
        commands.commit(baseui, repo, message=message)

    @reraise_safe_exceptions
    def rebase(self, wire, source=None, dest=None, abort=False):
        repo = self._factory.repo(wire)
        baseui = self._factory._create_config(wire['config'])
        repo.ui.setconfig('ui', 'merge', 'internal:dump')
        rebase.rebase(
            baseui, repo, base=source, dest=dest, abort=abort, keep=not abort)

    @reraise_safe_exceptions
    def bookmark(self, wire, bookmark, revision=None):
        repo = self._factory.repo(wire)
        baseui = self._factory._create_config(wire['config'])
        commands.bookmark(baseui, repo, bookmark, rev=revision, force=True)
