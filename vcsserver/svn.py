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

from __future__ import absolute_import

from urllib2 import URLError
import logging
import posixpath as vcspath
import StringIO
import subprocess
import urllib

import svn.client
import svn.core
import svn.delta
import svn.diff
import svn.fs
import svn.repos

from vcsserver import svn_diff
from vcsserver.base import RepoFactory


log = logging.getLogger(__name__)


# Set of svn compatible version flags.
# Compare with subversion/svnadmin/svnadmin.c
svn_compatible_versions = set([
    'pre-1.4-compatible',
    'pre-1.5-compatible',
    'pre-1.6-compatible',
    'pre-1.8-compatible',
])


class SubversionFactory(RepoFactory):

    def _create_repo(self, wire, create, compatible_version):
        path = svn.core.svn_path_canonicalize(wire['path'])
        if create:
            fs_config = {}
            if compatible_version:
                if compatible_version not in svn_compatible_versions:
                    raise Exception('Unknown SVN compatible version "{}"'
                                    .format(compatible_version))
                log.debug('Create SVN repo with compatible version "%s"',
                          compatible_version)
                fs_config[compatible_version] = '1'
            repo = svn.repos.create(path, "", "", None, fs_config)
        else:
            repo = svn.repos.open(path)
        return repo

    def repo(self, wire, create=False, compatible_version=None):
        def create_new_repo():
            return self._create_repo(wire, create, compatible_version)

        return self._repo(wire, create_new_repo)



NODE_TYPE_MAPPING = {
    svn.core.svn_node_file: 'file',
    svn.core.svn_node_dir: 'dir',
}


class SvnRemote(object):

    def __init__(self, factory, hg_factory=None):
        self._factory = factory
        # TODO: Remove once we do not use internal Mercurial objects anymore
        # for subversion
        self._hg_factory = hg_factory

    def check_url(self, url, config_items):
        # this can throw exception if not installed, but we detect this
        from hgsubversion import svnrepo

        baseui = self._hg_factory._create_config(config_items)
        # uuid function get's only valid UUID from proper repo, else
        # throws exception
        try:
            svnrepo.svnremoterepo(baseui, url).svn.uuid
        except:
            log.debug("Invalid svn url: %s", url)
            raise URLError(
                '"%s" is not a valid Subversion source url.' % (url, ))
        return True

    def is_path_valid_repository(self, wire, path):
        try:
            svn.repos.open(path)
        except svn.core.SubversionException:
            log.debug("Invalid Subversion path %s", path)
            return False
        return True

    def lookup(self, wire, revision):
        if revision not in [-1, None, 'HEAD']:
            raise NotImplementedError
        repo = self._factory.repo(wire)
        fs_ptr = svn.repos.fs(repo)
        head = svn.fs.youngest_rev(fs_ptr)
        return head

    def lookup_interval(self, wire, start_ts, end_ts):
        repo = self._factory.repo(wire)
        fsobj = svn.repos.fs(repo)
        start_rev = None
        end_rev = None
        if start_ts:
            start_ts_svn = apr_time_t(start_ts)
            start_rev = svn.repos.dated_revision(repo, start_ts_svn) + 1
        else:
            start_rev = 1
        if end_ts:
            end_ts_svn = apr_time_t(end_ts)
            end_rev = svn.repos.dated_revision(repo, end_ts_svn)
        else:
            end_rev = svn.fs.youngest_rev(fsobj)
        return start_rev, end_rev

    def revision_properties(self, wire, revision):
        repo = self._factory.repo(wire)
        fs_ptr = svn.repos.fs(repo)
        return svn.fs.revision_proplist(fs_ptr, revision)

    def revision_changes(self, wire, revision):

        repo = self._factory.repo(wire)
        fsobj = svn.repos.fs(repo)
        rev_root = svn.fs.revision_root(fsobj, revision)

        editor = svn.repos.ChangeCollector(fsobj, rev_root)
        editor_ptr, editor_baton = svn.delta.make_editor(editor)
        base_dir = ""
        send_deltas = False
        svn.repos.replay2(
            rev_root, base_dir, svn.core.SVN_INVALID_REVNUM, send_deltas,
            editor_ptr, editor_baton, None)

        added = []
        changed = []
        removed = []

        # TODO: CHANGE_ACTION_REPLACE: Figure out where it belongs
        for path, change in editor.changes.iteritems():
            # TODO: Decide what to do with directory nodes. Subversion can add
            # empty directories.
            if change.item_kind == svn.core.svn_node_dir:
                continue
            if change.action == svn.repos.CHANGE_ACTION_ADD:
                added.append(path)
            elif change.action == svn.repos.CHANGE_ACTION_MODIFY:
                changed.append(path)
            elif change.action == svn.repos.CHANGE_ACTION_DELETE:
                removed.append(path)
            else:
                raise NotImplementedError(
                    "Action %s not supported on path %s" % (
                        change.action, path))

        changes = {
            'added': added,
            'changed': changed,
            'removed': removed,
        }
        return changes

    def node_history(self, wire, path, revision, limit):
        cross_copies = False
        repo = self._factory.repo(wire)
        fsobj = svn.repos.fs(repo)
        rev_root = svn.fs.revision_root(fsobj, revision)

        history_revisions = []
        history = svn.fs.node_history(rev_root, path)
        history = svn.fs.history_prev(history, cross_copies)
        while history:
            __, node_revision = svn.fs.history_location(history)
            history_revisions.append(node_revision)
            if limit and len(history_revisions) >= limit:
                break
            history = svn.fs.history_prev(history, cross_copies)
        return history_revisions

    def node_properties(self, wire, path, revision):
        repo = self._factory.repo(wire)
        fsobj = svn.repos.fs(repo)
        rev_root = svn.fs.revision_root(fsobj, revision)
        return svn.fs.node_proplist(rev_root, path)

    def file_annotate(self, wire, path, revision):
        abs_path = 'file://' + urllib.pathname2url(
            vcspath.join(wire['path'], path))
        file_uri = svn.core.svn_path_canonicalize(abs_path)

        start_rev = svn_opt_revision_value_t(0)
        peg_rev = svn_opt_revision_value_t(revision)
        end_rev = peg_rev

        annotations = []

        def receiver(line_no, revision, author, date, line, pool):
            annotations.append((line_no, revision, line))

        # TODO: Cannot use blame5, missing typemap function in the swig code
        try:
            svn.client.blame2(
                file_uri, peg_rev, start_rev, end_rev,
                receiver, svn.client.create_context())
        except svn.core.SubversionException as exc:
            log.exception("Error during blame operation.")
            raise Exception(
                "Blame not supported or file does not exist at path %s. "
                "Error %s." % (path, exc))

        return annotations

    def get_node_type(self, wire, path, rev=None):
        repo = self._factory.repo(wire)
        fs_ptr = svn.repos.fs(repo)
        if rev is None:
            rev = svn.fs.youngest_rev(fs_ptr)
        root = svn.fs.revision_root(fs_ptr, rev)
        node = svn.fs.check_path(root, path)
        return NODE_TYPE_MAPPING.get(node, None)

    def get_nodes(self, wire, path, revision=None):
        repo = self._factory.repo(wire)
        fsobj = svn.repos.fs(repo)
        if revision is None:
            revision = svn.fs.youngest_rev(fsobj)
        root = svn.fs.revision_root(fsobj, revision)
        entries = svn.fs.dir_entries(root, path)
        result = []
        for entry_path, entry_info in entries.iteritems():
            result.append(
                (entry_path, NODE_TYPE_MAPPING.get(entry_info.kind, None)))
        return result

    def get_file_content(self, wire, path, rev=None):
        repo = self._factory.repo(wire)
        fsobj = svn.repos.fs(repo)
        if rev is None:
            rev = svn.fs.youngest_revision(fsobj)
        root = svn.fs.revision_root(fsobj, rev)
        content = svn.core.Stream(svn.fs.file_contents(root, path))
        return content.read()

    def get_file_size(self, wire, path, revision=None):
        repo = self._factory.repo(wire)
        fsobj = svn.repos.fs(repo)
        if revision is None:
            revision = svn.fs.youngest_revision(fsobj)
        root = svn.fs.revision_root(fsobj, revision)
        size = svn.fs.file_length(root, path)
        return size

    def create_repository(self, wire, compatible_version=None):
        log.info('Creating Subversion repository in path "%s"', wire['path'])
        self._factory.repo(wire, create=True,
                           compatible_version=compatible_version)

    def import_remote_repository(self, wire, src_url):
        repo_path = wire['path']
        if not self.is_path_valid_repository(wire, repo_path):
            raise Exception(
                "Path %s is not a valid Subversion repository." % repo_path)
        # TODO: johbo: URL checks ?
        rdump = subprocess.Popen(
            ['svnrdump', 'dump', '--non-interactive', src_url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        load = subprocess.Popen(
            ['svnadmin', 'load', repo_path], stdin=rdump.stdout)

        # TODO: johbo: This can be a very long operation, might be better
        # to track some kind of status and provide an api to check if the
        # import is done.
        rdump.wait()
        load.wait()

        if rdump.returncode != 0:
            errors = rdump.stderr.read()
            log.error('svnrdump dump failed: statuscode %s: message: %s',
                      rdump.returncode, errors)
            reason = 'UNKNOWN'
            if 'svnrdump: E230001:' in errors:
                reason = 'INVALID_CERTIFICATE'
            raise Exception(
                'Failed to dump the remote repository from %s.' % src_url,
                reason)
        if load.returncode != 0:
            raise Exception(
                'Failed to load the dump of remote repository from %s.' %
                (src_url, ))

    def commit(self, wire, message, author, timestamp, updated, removed):
        assert isinstance(message, str)
        assert isinstance(author, str)

        repo = self._factory.repo(wire)
        fsobj = svn.repos.fs(repo)

        rev = svn.fs.youngest_rev(fsobj)
        txn = svn.repos.fs_begin_txn_for_commit(repo, rev, author, message)
        txn_root = svn.fs.txn_root(txn)

        for node in updated:
            TxnNodeProcessor(node, txn_root).update()
        for node in removed:
            TxnNodeProcessor(node, txn_root).remove()

        commit_id = svn.repos.fs_commit_txn(repo, txn)

        if timestamp:
            apr_time = apr_time_t(timestamp)
            ts_formatted = svn.core.svn_time_to_cstring(apr_time)
            svn.fs.change_rev_prop(fsobj, commit_id, 'svn:date', ts_formatted)

        log.debug('Committed revision "%s" to "%s".', commit_id, wire['path'])
        return commit_id

    def diff(self, wire, rev1, rev2, path1=None, path2=None,
             ignore_whitespace=False, context=3):
        wire.update(cache=False)
        repo = self._factory.repo(wire)
        diff_creator = SvnDiffer(
            repo, rev1, path1, rev2, path2, ignore_whitespace, context)
        return diff_creator.generate_diff()


class SvnDiffer(object):
    """
    Utility to create diffs based on difflib and the Subversion api
    """

    binary_content = False

    def __init__(
            self, repo, src_rev, src_path, tgt_rev, tgt_path,
            ignore_whitespace, context):
        self.repo = repo
        self.ignore_whitespace = ignore_whitespace
        self.context = context

        fsobj = svn.repos.fs(repo)

        self.tgt_rev = tgt_rev
        self.tgt_path = tgt_path or ''
        self.tgt_root = svn.fs.revision_root(fsobj, tgt_rev)
        self.tgt_kind = svn.fs.check_path(self.tgt_root, self.tgt_path)

        self.src_rev = src_rev
        self.src_path = src_path or self.tgt_path
        self.src_root = svn.fs.revision_root(fsobj, src_rev)
        self.src_kind = svn.fs.check_path(self.src_root, self.src_path)

        self._validate()

    def _validate(self):
        if (self.tgt_kind != svn.core.svn_node_none and
                self.src_kind != svn.core.svn_node_none and
                self.src_kind != self.tgt_kind):
            # TODO: johbo: proper error handling
            raise Exception(
                "Source and target are not compatible for diff generation. "
                "Source type: %s, target type: %s" %
                (self.src_kind, self.tgt_kind))

    def generate_diff(self):
        buf = StringIO.StringIO()
        if self.tgt_kind == svn.core.svn_node_dir:
            self._generate_dir_diff(buf)
        else:
            self._generate_file_diff(buf)
        return buf.getvalue()

    def _generate_dir_diff(self, buf):
        editor = DiffChangeEditor()
        editor_ptr, editor_baton = svn.delta.make_editor(editor)
        svn.repos.dir_delta2(
            self.src_root,
            self.src_path,
            '',  # src_entry
            self.tgt_root,
            self.tgt_path,
            editor_ptr, editor_baton,
            authorization_callback_allow_all,
            False,  # text_deltas
            svn.core.svn_depth_infinity,  # depth
            False,  # entry_props
            False,  # ignore_ancestry
        )

        for path, __, change in sorted(editor.changes):
            self._generate_node_diff(
                buf, change, path, self.tgt_path, path, self.src_path)

    def _generate_file_diff(self, buf):
            change = None
            if self.src_kind == svn.core.svn_node_none:
                change = "add"
            elif self.tgt_kind == svn.core.svn_node_none:
                change = "delete"
            tgt_base, tgt_path = vcspath.split(self.tgt_path)
            src_base, src_path = vcspath.split(self.src_path)
            self._generate_node_diff(
                buf, change, tgt_path, tgt_base, src_path, src_base)

    def _generate_node_diff(
            self, buf, change, tgt_path, tgt_base, src_path, src_base):
        tgt_full_path = vcspath.join(tgt_base, tgt_path)
        src_full_path = vcspath.join(src_base, src_path)

        self.binary_content = False
        mime_type = self._get_mime_type(tgt_full_path)
        if mime_type and not mime_type.startswith('text'):
            self.binary_content = True
            buf.write("=" * 67 + '\n')
            buf.write("Cannot display: file marked as a binary type.\n")
            buf.write("svn:mime-type = %s\n" % mime_type)
        buf.write("Index: %s\n" % (tgt_path, ))
        buf.write("=" * 67 + '\n')
        buf.write("diff --git a/%(tgt_path)s b/%(tgt_path)s\n" % {
            'tgt_path': tgt_path})

        if change == 'add':
            # TODO: johbo: SVN is missing a zero here compared to git
            buf.write("new file mode 10644\n")
            buf.write("--- /dev/null\t(revision 0)\n")
            src_lines = []
        else:
            if change == 'delete':
                buf.write("deleted file mode 10644\n")
            buf.write("--- a/%s\t(revision %s)\n" % (
                src_path, self.src_rev))
            src_lines = self._svn_readlines(self.src_root, src_full_path)

        if change == 'delete':
            buf.write("+++ /dev/null\t(revision %s)\n" % (self.tgt_rev, ))
            tgt_lines = []
        else:
            buf.write("+++ b/%s\t(revision %s)\n" % (
                tgt_path, self.tgt_rev))
            tgt_lines = self._svn_readlines(self.tgt_root, tgt_full_path)

        if not self.binary_content:
            udiff = svn_diff.unified_diff(
                src_lines, tgt_lines, context=self.context,
                ignore_blank_lines=self.ignore_whitespace,
                ignore_case=False,
                ignore_space_changes=self.ignore_whitespace)
            buf.writelines(udiff)

    def _get_mime_type(self, path):
        try:
            mime_type = svn.fs.node_prop(
                self.tgt_root, path, svn.core.SVN_PROP_MIME_TYPE)
        except svn.core.SubversionException:
            mime_type = svn.fs.node_prop(
                self.src_root, path, svn.core.SVN_PROP_MIME_TYPE)
        return mime_type

    def _svn_readlines(self, fs_root, node_path):
        if self.binary_content:
            return []
        node_kind = svn.fs.check_path(fs_root, node_path)
        if node_kind not in (
                svn.core.svn_node_file, svn.core.svn_node_symlink):
            return []
        content = svn.core.Stream(
            svn.fs.file_contents(fs_root, node_path)).read()
        return content.splitlines(True)


class DiffChangeEditor(svn.delta.Editor):
    """
    Records changes between two given revisions
    """

    def __init__(self):
        self.changes = []

    def delete_entry(self, path, revision, parent_baton, pool=None):
        self.changes.append((path, None, 'delete'))

    def add_file(
            self, path, parent_baton, copyfrom_path, copyfrom_revision,
            file_pool=None):
        self.changes.append((path, 'file', 'add'))

    def open_file(self, path, parent_baton, base_revision, file_pool=None):
        self.changes.append((path, 'file', 'change'))


def authorization_callback_allow_all(root, path, pool):
    return True


class TxnNodeProcessor(object):
    """
    Utility to process the change of one node within a transaction root.

    It encapsulates the knowledge of how to add, update or remove
    a node for a given transaction root. The purpose is to support the method
    `SvnRemote.commit`.
    """

    def __init__(self, node, txn_root):
        assert isinstance(node['path'], str)

        self.node = node
        self.txn_root = txn_root

    def update(self):
        self._ensure_parent_dirs()
        self._add_file_if_node_does_not_exist()
        self._update_file_content()
        self._update_file_properties()

    def remove(self):
        svn.fs.delete(self.txn_root, self.node['path'])
        # TODO: Clean up directory if empty

    def _ensure_parent_dirs(self):
        curdir = vcspath.dirname(self.node['path'])
        dirs_to_create = []
        while not self._svn_path_exists(curdir):
            dirs_to_create.append(curdir)
            curdir = vcspath.dirname(curdir)

        for curdir in reversed(dirs_to_create):
            log.debug('Creating missing directory "%s"', curdir)
            svn.fs.make_dir(self.txn_root, curdir)

    def _svn_path_exists(self, path):
        path_status = svn.fs.check_path(self.txn_root, path)
        return path_status != svn.core.svn_node_none

    def _add_file_if_node_does_not_exist(self):
        kind = svn.fs.check_path(self.txn_root, self.node['path'])
        if kind == svn.core.svn_node_none:
            svn.fs.make_file(self.txn_root, self.node['path'])

    def _update_file_content(self):
        assert isinstance(self.node['content'], str)
        handler, baton = svn.fs.apply_textdelta(
            self.txn_root, self.node['path'], None, None)
        svn.delta.svn_txdelta_send_string(self.node['content'], handler, baton)

    def _update_file_properties(self):
        properties = self.node.get('properties', {})
        for key, value in properties.iteritems():
            svn.fs.change_node_prop(
                self.txn_root, self.node['path'], key, value)


def apr_time_t(timestamp):
    """
    Convert a Python timestamp into APR timestamp type apr_time_t
    """
    return timestamp * 1E6


def svn_opt_revision_value_t(num):
    """
    Put `num` into a `svn_opt_revision_value_t` structure.
    """
    value = svn.core.svn_opt_revision_value_t()
    value.number = num
    revision = svn.core.svn_opt_revision_t()
    revision.kind = svn.core.svn_opt_revision_number
    revision.value = value
    return revision
