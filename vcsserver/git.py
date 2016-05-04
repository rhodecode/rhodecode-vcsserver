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

import logging
import os
import posixpath as vcspath
import re
import stat
import urllib
import urllib2
from functools import wraps

from dulwich import index, objects
from dulwich.client import HttpGitClient, LocalGitClient
from dulwich.errors import (
    NotGitRepository, ChecksumMismatch, WrongObjectException,
    MissingCommitError, ObjectMissing, HangupException,
    UnexpectedCommandError)
from dulwich.repo import Repo as DulwichRepo, Tag
from dulwich.server import update_server_info

from vcsserver import exceptions, settings, subprocessio
from vcsserver.utils import safe_str
from vcsserver.base import RepoFactory
from vcsserver.hgcompat import (
    hg_url, httpbasicauthhandler, httpdigestauthhandler)


DIR_STAT = stat.S_IFDIR
FILE_MODE = stat.S_IFMT
GIT_LINK = objects.S_IFGITLINK

log = logging.getLogger(__name__)


def reraise_safe_exceptions(func):
    """Converts Dulwich exceptions to something neutral."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ChecksumMismatch, WrongObjectException, MissingCommitError,
                ObjectMissing) as e:
            raise exceptions.LookupException(e.message)
        except (HangupException, UnexpectedCommandError) as e:
            raise exceptions.VcsException(e.message)
    return wrapper


class Repo(DulwichRepo):
    """
    A wrapper for dulwich Repo class.

    Since dulwich is sometimes keeping .idx file descriptors open, it leads to
    "Too many open files" error. We need to close all opened file descriptors
    once the repo object is destroyed.

    TODO: mikhail: please check if we need this wrapper after updating dulwich
    to 0.12.0 +
    """
    def __del__(self):
        if hasattr(self, 'object_store'):
            self.close()


class GitFactory(RepoFactory):

    def _create_repo(self, wire, create):
        repo_path = str_to_dulwich(wire['path'])
        return Repo(repo_path)


class GitRemote(object):

    def __init__(self, factory):
        self._factory = factory

        self._bulk_methods = {
            "author": self.commit_attribute,
            "date": self.get_object_attrs,
            "message": self.commit_attribute,
            "parents": self.commit_attribute,
            "_commit": self.revision,
        }

    def _assign_ref(self, wire, ref, commit_id):
        repo = self._factory.repo(wire)
        repo[ref] = commit_id

    @reraise_safe_exceptions
    def add_object(self, wire, content):
        repo = self._factory.repo(wire)
        blob = objects.Blob()
        blob.set_raw_string(content)
        repo.object_store.add_object(blob)
        return blob.id

    @reraise_safe_exceptions
    def assert_correct_path(self, wire):
        try:
            self._factory.repo(wire)
        except NotGitRepository as e:
            # Exception can contain unicode which we convert
            raise exceptions.AbortException(repr(e))

    @reraise_safe_exceptions
    def bare(self, wire):
        repo = self._factory.repo(wire)
        return repo.bare

    @reraise_safe_exceptions
    def blob_as_pretty_string(self, wire, sha):
        repo = self._factory.repo(wire)
        return repo[sha].as_pretty_string()

    @reraise_safe_exceptions
    def blob_raw_length(self, wire, sha):
        repo = self._factory.repo(wire)
        blob = repo[sha]
        return blob.raw_length()

    @reraise_safe_exceptions
    def bulk_request(self, wire, rev, pre_load):
        result = {}
        for attr in pre_load:
            try:
                method = self._bulk_methods[attr]
                args = [wire, rev]
                if attr == "date":
                    args.extend(["commit_time", "commit_timezone"])
                elif attr in ["author", "message", "parents"]:
                    args.append(attr)
                result[attr] = method(*args)
            except KeyError:
                raise exceptions.VcsException(
                    "Unknown bulk attribute: %s" % attr)
        return result

    def _build_opener(self, url):
        handlers = []
        url_obj = hg_url(url)
        _, authinfo = url_obj.authinfo()

        if authinfo:
            # create a password manager
            passmgr = urllib2.HTTPPasswordMgrWithDefaultRealm()
            passmgr.add_password(*authinfo)

            handlers.extend((httpbasicauthhandler(passmgr),
                             httpdigestauthhandler(passmgr)))

        return urllib2.build_opener(*handlers)

    @reraise_safe_exceptions
    def check_url(self, url, config):
        url_obj = hg_url(url)
        test_uri, _ = url_obj.authinfo()
        url_obj.passwd = '*****'
        cleaned_uri = str(url_obj)

        if not test_uri.endswith('info/refs'):
            test_uri = test_uri.rstrip('/') + '/info/refs'

        o = self._build_opener(url)
        o.addheaders = [('User-Agent', 'git/1.7.8.0')]  # fake some git

        q = {"service": 'git-upload-pack'}
        qs = '?%s' % urllib.urlencode(q)
        cu = "%s%s" % (test_uri, qs)
        req = urllib2.Request(cu, None, {})

        try:
            resp = o.open(req)
            if resp.code != 200:
                raise Exception('Return Code is not 200')
        except Exception as e:
            # means it cannot be cloned
            raise urllib2.URLError("[%s] org_exc: %s" % (cleaned_uri, e))

        # now detect if it's proper git repo
        gitdata = resp.read()
        if 'service=git-upload-pack' in gitdata:
            pass
        elif re.findall(r'[0-9a-fA-F]{40}\s+refs', gitdata):
            # old style git can return some other format !
            pass
        else:
            raise urllib2.URLError(
                "url [%s] does not look like an git" % (cleaned_uri,))

        return True

    @reraise_safe_exceptions
    def clone(self, wire, url, deferred, valid_refs, update_after_clone):
        remote_refs = self.fetch(wire, url, apply_refs=False)
        repo = self._factory.repo(wire)
        if isinstance(valid_refs, list):
            valid_refs = tuple(valid_refs)

        for k in remote_refs:
            # only parse heads/tags and skip so called deferred tags
            if k.startswith(valid_refs) and not k.endswith(deferred):
                repo[k] = remote_refs[k]

        if update_after_clone:
            # we want to checkout HEAD
            repo["HEAD"] = remote_refs["HEAD"]
            index.build_index_from_tree(repo.path, repo.index_path(),
                                        repo.object_store, repo["HEAD"].tree)

    # TODO: this is quite complex, check if that can be simplified
    @reraise_safe_exceptions
    def commit(self, wire, commit_data, branch, commit_tree, updated, removed):
        repo = self._factory.repo(wire)
        object_store = repo.object_store

        # Create tree and populates it with blobs
        commit_tree = commit_tree and repo[commit_tree] or objects.Tree()

        for node in updated:
            # Compute subdirs if needed
            dirpath, nodename = vcspath.split(node['path'])
            dirnames = map(safe_str, dirpath and dirpath.split('/') or [])
            parent = commit_tree
            ancestors = [('', parent)]

            # Tries to dig for the deepest existing tree
            while dirnames:
                curdir = dirnames.pop(0)
                try:
                    dir_id = parent[curdir][1]
                except KeyError:
                    # put curdir back into dirnames and stops
                    dirnames.insert(0, curdir)
                    break
                else:
                    # If found, updates parent
                    parent = repo[dir_id]
                    ancestors.append((curdir, parent))
            # Now parent is deepest existing tree and we need to create
            # subtrees for dirnames (in reverse order)
            # [this only applies for nodes from added]
            new_trees = []

            blob = objects.Blob.from_string(node['content'])

            if dirnames:
                # If there are trees which should be created we need to build
                # them now (in reverse order)
                reversed_dirnames = list(reversed(dirnames))
                curtree = objects.Tree()
                curtree[node['node_path']] = node['mode'], blob.id
                new_trees.append(curtree)
                for dirname in reversed_dirnames[:-1]:
                    newtree = objects.Tree()
                    newtree[dirname] = (DIR_STAT, curtree.id)
                    new_trees.append(newtree)
                    curtree = newtree
                parent[reversed_dirnames[-1]] = (DIR_STAT, curtree.id)
            else:
                parent.add(
                    name=node['node_path'], mode=node['mode'], hexsha=blob.id)

            new_trees.append(parent)
            # Update ancestors
            reversed_ancestors = reversed(
                [(a[1], b[1], b[0]) for a, b in zip(ancestors, ancestors[1:])])
            for parent, tree, path in reversed_ancestors:
                parent[path] = (DIR_STAT, tree.id)
                object_store.add_object(tree)

            object_store.add_object(blob)
            for tree in new_trees:
                object_store.add_object(tree)

        for node_path in removed:
            paths = node_path.split('/')
            tree = commit_tree
            trees = [tree]
            # Traverse deep into the forest...
            for path in paths:
                try:
                    obj = repo[tree[path][1]]
                    if isinstance(obj, objects.Tree):
                        trees.append(obj)
                        tree = obj
                except KeyError:
                    break
            # Cut down the blob and all rotten trees on the way back...
            for path, tree in reversed(zip(paths, trees)):
                del tree[path]
                if tree:
                    # This tree still has elements - don't remove it or any
                    # of it's parents
                    break

        object_store.add_object(commit_tree)

        # Create commit
        commit = objects.Commit()
        commit.tree = commit_tree.id
        for k, v in commit_data.iteritems():
            setattr(commit, k, v)
        object_store.add_object(commit)

        ref = 'refs/heads/%s' % branch
        repo.refs[ref] = commit.id

        return commit.id

    @reraise_safe_exceptions
    def fetch(self, wire, url, apply_refs=True, refs=None):
        if url != 'default' and '://' not in url:
            client = LocalGitClient(url)
        else:
            url_obj = hg_url(url)
            o = self._build_opener(url)
            url, _ = url_obj.authinfo()
            client = HttpGitClient(base_url=url, opener=o)
        repo = self._factory.repo(wire)

        determine_wants = repo.object_store.determine_wants_all
        if refs:
            def determine_wants_requested(references):
                return [references[r] for r in references if r in refs]
            determine_wants = determine_wants_requested

        try:
            remote_refs = client.fetch(
                path=url, target=repo, determine_wants=determine_wants)
        except NotGitRepository:
            log.warning(
                'Trying to fetch from "%s" failed, not a Git repository.', url)
            raise exceptions.AbortException()

        # mikhail: client.fetch() returns all the remote refs, but fetches only
        # refs filtered by `determine_wants` function. We need to filter result
        # as well
        if refs:
            remote_refs = {k: remote_refs[k] for k in remote_refs if k in refs}

        if apply_refs:
            # TODO: johbo: Needs proper test coverage with a git repository
            # that contains a tag object, so that we would end up with
            # a peeled ref at this point.
            PEELED_REF_MARKER = '^{}'
            for k in remote_refs:
                if k.endswith(PEELED_REF_MARKER):
                    log.info("Skipping peeled reference %s", k)
                    continue
                repo[k] = remote_refs[k]

            if refs:
                # mikhail: explicitly set the head to the last ref.
                repo['HEAD'] = remote_refs[refs[-1]]

            # TODO: mikhail: should we return remote_refs here to be
            # consistent?
        else:
            return remote_refs

    @reraise_safe_exceptions
    def get_remote_refs(self, wire, url):
        repo = Repo(url)
        return repo.get_refs()

    @reraise_safe_exceptions
    def get_description(self, wire):
        repo = self._factory.repo(wire)
        return repo.get_description()

    @reraise_safe_exceptions
    def get_file_history(self, wire, file_path, commit_id, limit):
        repo = self._factory.repo(wire)
        include = [commit_id]
        paths = [file_path]

        walker = repo.get_walker(include, paths=paths, max_entries=limit)
        return [x.commit.id for x in walker]

    @reraise_safe_exceptions
    def get_missing_revs(self, wire, rev1, rev2, path2):
        repo = self._factory.repo(wire)
        LocalGitClient(thin_packs=False).fetch(path2, repo)

        wire_remote = wire.copy()
        wire_remote['path'] = path2
        repo_remote = self._factory.repo(wire_remote)
        LocalGitClient(thin_packs=False).fetch(wire["path"], repo_remote)

        revs = [
            x.commit.id
            for x in repo_remote.get_walker(include=[rev2], exclude=[rev1])]
        return revs

    @reraise_safe_exceptions
    def get_object(self, wire, sha):
        repo = self._factory.repo(wire)
        obj = repo.get_object(sha)
        commit_id = obj.id

        if isinstance(obj, Tag):
            commit_id = obj.object[1]

        return {
            'id': obj.id,
            'type': obj.type_name,
            'commit_id': commit_id
        }

    @reraise_safe_exceptions
    def get_object_attrs(self, wire, sha, *attrs):
        repo = self._factory.repo(wire)
        obj = repo.get_object(sha)
        return list(getattr(obj, a) for a in attrs)

    @reraise_safe_exceptions
    def get_refs(self, wire, keys=None):
        # FIXME(skreft): this method is affected by bug
        # http://bugs.rhodecode.com/issues/298.
        # Basically, it will overwrite previously computed references if
        # there's another one with the same name and given the order of
        # repo.get_refs() is not guaranteed, the output of this method is not
        # stable either.
        repo = self._factory.repo(wire)
        refs = repo.get_refs()
        if keys is None:
            return refs

        _refs = {}
        for ref, sha in refs.iteritems():
            for k, type_ in keys:
                if ref.startswith(k):
                    _key = ref[len(k):]
                    if type_ == 'T':
                        sha = repo.get_object(sha).id
                    _refs[_key] = [sha, type_]
                    break
        return _refs

    @reraise_safe_exceptions
    def get_refs_path(self, wire):
        repo = self._factory.repo(wire)
        return repo.refs.path

    @reraise_safe_exceptions
    def head(self, wire):
        repo = self._factory.repo(wire)
        return repo.head()

    @reraise_safe_exceptions
    def init(self, wire):
        repo_path = str_to_dulwich(wire['path'])
        self.repo = Repo.init(repo_path)

    @reraise_safe_exceptions
    def init_bare(self, wire):
        repo_path = str_to_dulwich(wire['path'])
        self.repo = Repo.init_bare(repo_path)

    @reraise_safe_exceptions
    def revision(self, wire, rev):
        repo = self._factory.repo(wire)
        obj = repo[rev]
        obj_data = {
            'id': obj.id,
        }
        try:
            obj_data['tree'] = obj.tree
        except AttributeError:
            pass
        return obj_data

    @reraise_safe_exceptions
    def commit_attribute(self, wire, rev, attr):
        repo = self._factory.repo(wire)
        obj = repo[rev]
        return getattr(obj, attr)

    @reraise_safe_exceptions
    def set_refs(self, wire, key, value):
        repo = self._factory.repo(wire)
        repo.refs[key] = value

    @reraise_safe_exceptions
    def remove_ref(self, wire, key):
        repo = self._factory.repo(wire)
        del repo.refs[key]

    @reraise_safe_exceptions
    def tree_changes(self, wire, source_id, target_id):
        repo = self._factory.repo(wire)
        source = repo[source_id].tree if source_id else None
        target = repo[target_id].tree
        result = repo.object_store.tree_changes(source, target)
        return list(result)

    @reraise_safe_exceptions
    def tree_items(self, wire, tree_id):
        repo = self._factory.repo(wire)
        tree = repo[tree_id]

        result = []
        for item in tree.iteritems():
            item_sha = item.sha
            item_mode = item.mode

            if FILE_MODE(item_mode) == GIT_LINK:
                item_type = "link"
            else:
                item_type = repo[item_sha].type_name

            result.append((item.path, item_mode, item_sha, item_type))
        return result

    @reraise_safe_exceptions
    def update_server_info(self, wire):
        repo = self._factory.repo(wire)
        update_server_info(repo)

    @reraise_safe_exceptions
    def discover_git_version(self):
        stdout, _ = self.run_git_command(
            {}, ['--version'], _bare=True, _safe=True)
        return stdout

    @reraise_safe_exceptions
    def run_git_command(self, wire, cmd, **opts):
        path = wire.get('path', None)

        if path and os.path.isdir(path):
            opts['cwd'] = path

        if '_bare' in opts:
            _copts = []
            del opts['_bare']
        else:
            _copts = ['-c', 'core.quotepath=false', ]
        safe_call = False
        if '_safe' in opts:
            # no exc on failure
            del opts['_safe']
            safe_call = True

        gitenv = os.environ.copy()
        gitenv.update(opts.pop('extra_env', {}))
        # need to clean fix GIT_DIR !
        if 'GIT_DIR' in gitenv:
            del gitenv['GIT_DIR']
        gitenv['GIT_CONFIG_NOGLOBAL'] = '1'

        cmd = [settings.GIT_EXECUTABLE] + _copts + cmd

        try:
            _opts = {'env': gitenv, 'shell': False}
            _opts.update(opts)
            p = subprocessio.SubprocessIOChunker(cmd, **_opts)

            return ''.join(p), ''.join(p.error)
        except (EnvironmentError, OSError) as err:
            tb_err = ("Couldn't run git command (%s).\n"
                      "Original error was:%s\n" % (cmd, err))
            log.exception(tb_err)
            if safe_call:
                return '', err
            else:
                raise exceptions.VcsException(tb_err)


def str_to_dulwich(value):
    """
    Dulwich 0.10.1a requires `unicode` objects to be passed in.
    """
    return value.decode(settings.WIRE_ENCODING)
