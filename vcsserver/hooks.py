# -*- coding: utf-8 -*-

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

import collections
import importlib
import io
import json
import subprocess
import sys
from httplib import HTTPConnection


import mercurial.scmutil
import mercurial.node
import Pyro4
import simplejson as json

from vcsserver import exceptions


class HooksHttpClient(object):
    connection = None

    def __init__(self, hooks_uri):
        self.hooks_uri = hooks_uri

    def __call__(self, method, extras):
        connection = HTTPConnection(self.hooks_uri)
        body = self._serialize(method, extras)
        connection.request('POST', '/', body)
        response = connection.getresponse()
        return json.loads(response.read())

    def _serialize(self, hook_name, extras):
        data = {
            'method': hook_name,
            'extras': extras
        }
        return json.dumps(data)


class HooksDummyClient(object):
    def __init__(self, hooks_module):
        self._hooks_module = importlib.import_module(hooks_module)

    def __call__(self, hook_name, extras):
        with self._hooks_module.Hooks() as hooks:
            return getattr(hooks, hook_name)(extras)


class HooksPyro4Client(object):
    def __init__(self, hooks_uri):
        self.hooks_uri = hooks_uri

    def __call__(self, hook_name, extras):
        with Pyro4.Proxy(self.hooks_uri) as hooks:
            return getattr(hooks, hook_name)(extras)


class RemoteMessageWriter(object):
    """Writer base class."""
    def write(message):
        raise NotImplementedError()


class HgMessageWriter(RemoteMessageWriter):
    """Writer that knows how to send messages to mercurial clients."""

    def __init__(self, ui):
        self.ui = ui

    def write(self, message):
        # TODO: Check why the quiet flag is set by default.
        old = self.ui.quiet
        self.ui.quiet = False
        self.ui.status(message.encode('utf-8'))
        self.ui.quiet = old


class GitMessageWriter(RemoteMessageWriter):
    """Writer that knows how to send messages to git clients."""

    def __init__(self, stdout=None):
        self.stdout = stdout or sys.stdout

    def write(self, message):
        self.stdout.write(message.encode('utf-8'))


def _handle_exception(result):
    exception_class = result.get('exception')
    if exception_class == 'HTTPLockedRC':
        raise exceptions.RepositoryLockedException(*result['exception_args'])
    elif exception_class == 'RepositoryError':
        raise exceptions.VcsException(*result['exception_args'])
    elif exception_class:
        raise Exception('Got remote exception "%s" with args "%s"' %
                        (exception_class, result['exception_args']))


def _get_hooks_client(extras):
    if 'hooks_uri' in extras:
        protocol = extras.get('hooks_protocol')
        return (
            HooksHttpClient(extras['hooks_uri'])
            if protocol == 'http'
            else HooksPyro4Client(extras['hooks_uri'])
        )
    else:
        return HooksDummyClient(extras['hooks_module'])


def _call_hook(hook_name, extras, writer):
    hooks = _get_hooks_client(extras)
    result = hooks(hook_name, extras)
    writer.write(result['output'])
    _handle_exception(result)

    return result['status']


def _extras_from_ui(ui):
    extras = json.loads(ui.config('rhodecode', 'RC_SCM_DATA'))
    return extras


def repo_size(ui, repo, **kwargs):
    return _call_hook('repo_size', _extras_from_ui(ui), HgMessageWriter(ui))


def pre_pull(ui, repo, **kwargs):
    return _call_hook('pre_pull', _extras_from_ui(ui), HgMessageWriter(ui))


def post_pull(ui, repo, **kwargs):
    return _call_hook('post_pull', _extras_from_ui(ui), HgMessageWriter(ui))


def pre_push(ui, repo, **kwargs):
    return _call_hook('pre_push', _extras_from_ui(ui), HgMessageWriter(ui))


# N.B.(skreft): the two functions below were taken and adapted from
# rhodecode.lib.vcs.remote.handle_git_pre_receive
# They are required to compute the commit_ids
def _get_revs(repo, rev_opt):
    revs = [rev for rev in mercurial.scmutil.revrange(repo, rev_opt)]
    if len(revs) == 0:
        return (mercurial.node.nullrev, mercurial.node.nullrev)

    return max(revs), min(revs)


def _rev_range_hash(repo, node):
    stop, start = _get_revs(repo, [node + ':'])
    revs = [mercurial.node.hex(repo[r].node()) for r in xrange(start, stop + 1)]

    return revs


def post_push(ui, repo, node, **kwargs):
    commit_ids = _rev_range_hash(repo, node)

    extras = _extras_from_ui(ui)
    extras['commit_ids'] = commit_ids

    return _call_hook('post_push', extras, HgMessageWriter(ui))


# backward compat
log_pull_action = post_pull

# backward compat
log_push_action = post_push


def handle_git_pre_receive(unused_repo_path, unused_revs, unused_env):
    """
    Old hook name: keep here for backward compatibility.

    This is only required when the installed git hooks are not upgraded.
    """
    pass


def handle_git_post_receive(unused_repo_path, unused_revs, unused_env):
    """
    Old hook name: keep here for backward compatibility.

    This is only required when the installed git hooks are not upgraded.
    """
    pass


HookResponse = collections.namedtuple('HookResponse', ('status', 'output'))


def git_pre_pull(extras):
    """
    Pre pull hook.

    :param extras: dictionary containing the keys defined in simplevcs
    :type extras: dict

    :return: status code of the hook. 0 for success.
    :rtype: int
    """
    if 'pull' not in extras['hooks']:
        return HookResponse(0, '')

    stdout = io.BytesIO()
    try:
        status = _call_hook('pre_pull', extras, GitMessageWriter(stdout))
    except Exception as error:
        status = 128
        stdout.write('ERROR: %s\n' % str(error))

    return HookResponse(status, stdout.getvalue())


def git_post_pull(extras):
    """
    Post pull hook.

    :param extras: dictionary containing the keys defined in simplevcs
    :type extras: dict

    :return: status code of the hook. 0 for success.
    :rtype: int
    """
    if 'pull' not in extras['hooks']:
        return HookResponse(0, '')

    stdout = io.BytesIO()
    try:
        status = _call_hook('post_pull', extras, GitMessageWriter(stdout))
    except Exception as error:
        status = 128
        stdout.write('ERROR: %s\n' % error)

    return HookResponse(status, stdout.getvalue())


def git_pre_receive(unused_repo_path, unused_revs, env):
    """
    Pre push hook.

    :param extras: dictionary containing the keys defined in simplevcs
    :type extras: dict

    :return: status code of the hook. 0 for success.
    :rtype: int
    """
    extras = json.loads(env['RC_SCM_DATA'])
    if 'push' not in extras['hooks']:
        return 0
    return _call_hook('pre_push', extras, GitMessageWriter())


def _run_command(arguments):
    """
    Run the specified command and return the stdout.

    :param arguments: sequence of program arugments (including the program name)
    :type arguments: list[str]
    """
    # TODO(skreft): refactor this method and all the other similar ones.
    # Probably this should be using subprocessio.
    process = subprocess.Popen(
        arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, _ = process.communicate()

    if process.returncode != 0:
        raise Exception(
            'Command %s exited with exit code %s' % (arguments,
                                                     process.returncode))

    return stdout


def git_post_receive(unused_repo_path, revision_lines, env):
    """
    Post push hook.

    :param extras: dictionary containing the keys defined in simplevcs
    :type extras: dict

    :return: status code of the hook. 0 for success.
    :rtype: int
    """
    extras = json.loads(env['RC_SCM_DATA'])
    if 'push' not in extras['hooks']:
        return 0

    rev_data = []
    for revision_line in revision_lines:
        old_rev, new_rev, ref = revision_line.strip().split(' ')
        ref_data = ref.split('/', 2)
        if ref_data[1] in ('tags', 'heads'):
            rev_data.append({
                'old_rev': old_rev,
                'new_rev': new_rev,
                'ref': ref,
                'type': ref_data[1],
                'name': ref_data[2],
            })

    git_revs = []

    # N.B.(skreft): it is ok to just call git, as git before calling a
    # subcommand sets the PATH environment variable so that it point to the
    # correct version of the git executable.
    empty_commit_id = '0' * 40
    for push_ref in rev_data:
        type_ = push_ref['type']
        if type_ == 'heads':
            if push_ref['old_rev'] == empty_commit_id:

                # Fix up head revision if needed
                cmd = ['git', 'show', 'HEAD']
                try:
                    _run_command(cmd)
                except Exception:
                    cmd = ['git', 'symbolic-ref', 'HEAD',
                           'refs/heads/%s' % push_ref['name']]
                    print "Setting default branch to %s" % push_ref['name']
                    _run_command(cmd)

                cmd = ['git', 'for-each-ref', '--format=%(refname)',
                       'refs/heads/*']
                heads = _run_command(cmd)
                heads = heads.replace(push_ref['ref'], '')
                heads = ' '.join(head for head in heads.splitlines() if head)
                cmd = ['git', 'log', '--reverse', '--pretty=format:%H',
                        '--', push_ref['new_rev'], '--not', heads]
                git_revs.extend(_run_command(cmd).splitlines())
            elif push_ref['new_rev'] == empty_commit_id:
                # delete branch case
                git_revs.append('delete_branch=>%s' % push_ref['name'])
            else:
                cmd = ['git', 'log',
                       '{old_rev}..{new_rev}'.format(**push_ref),
                       '--reverse', '--pretty=format:%H']
                git_revs.extend(_run_command(cmd).splitlines())
        elif type_ == 'tags':
            git_revs.append('tag=>%s' % push_ref['name'])

    extras['commit_ids'] = git_revs

    if 'repo_size' in extras['hooks']:
        try:
            _call_hook('repo_size', extras, GitMessageWriter())
        except:
            pass

    return _call_hook('post_push', extras, GitMessageWriter())
