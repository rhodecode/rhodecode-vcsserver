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

"""Handles the Git smart protocol."""

import os
import socket
import logging

import simplejson as json
import dulwich.protocol
from webob import Request, Response, exc

from vcsserver import hooks, subprocessio


log = logging.getLogger(__name__)


class FileWrapper(object):
    """File wrapper that ensures how much data is read from it."""

    def __init__(self, fd, content_length):
        self.fd = fd
        self.content_length = content_length
        self.remain = content_length

    def read(self, size):
        if size <= self.remain:
            try:
                data = self.fd.read(size)
            except socket.error:
                raise IOError(self)
            self.remain -= size
        elif self.remain:
            data = self.fd.read(self.remain)
            self.remain = 0
        else:
            data = None
        return data

    def __repr__(self):
        return '<FileWrapper %s len: %s, read: %s>' % (
            self.fd, self.content_length, self.content_length - self.remain
        )


class GitRepository(object):
    """WSGI app for handling Git smart protocol endpoints."""

    git_folder_signature = frozenset(
        ('config', 'head', 'info', 'objects', 'refs'))
    commands = frozenset(('git-upload-pack', 'git-receive-pack'))
    valid_accepts = frozenset(('application/x-%s-result' %
                               c for c in commands))

    # The last bytes are the SHA1 of the first 12 bytes.
    EMPTY_PACK = (
        'PACK\x00\x00\x00\x02\x00\x00\x00\x00' +
        '\x02\x9d\x08\x82;\xd8\xa8\xea\xb5\x10\xadj\xc7\\\x82<\xfd>\xd3\x1e'
    )
    SIDE_BAND_CAPS = frozenset(('side-band', 'side-band-64k'))

    def __init__(self, repo_name, content_path, git_path, update_server_info,
                 extras):
        files = frozenset(f.lower() for f in os.listdir(content_path))
        valid_dir_signature = self.git_folder_signature.issubset(files)

        if not valid_dir_signature:
            raise OSError('%s missing git signature' % content_path)

        self.content_path = content_path
        self.repo_name = repo_name
        self.extras = extras
        self.git_path = git_path
        self.update_server_info = update_server_info

    def _get_fixedpath(self, path):
        """
        Small fix for repo_path

        :param path:
        """
        return path.split(self.repo_name, 1)[-1].strip('/')

    def inforefs(self, request, unused_environ):
        """
        WSGI Response producer for HTTP GET Git Smart
        HTTP /info/refs request.
        """

        git_command = request.GET.get('service')
        if git_command not in self.commands:
            log.debug('command %s not allowed', git_command)
            return exc.HTTPForbidden()

        # please, resist the urge to add '\n' to git capture and increment
        # line count by 1.
        # by git docs: Documentation/technical/http-protocol.txt#L214 \n is
        # a part of protocol.
        # The code in Git client not only does NOT need '\n', but actually
        # blows up if you sprinkle "flush" (0000) as "0001\n".
        # It reads binary, per number of bytes specified.
        # if you do add '\n' as part of data, count it.
        server_advert = '# service=%s\n' % git_command
        packet_len = str(hex(len(server_advert) + 4)[2:].rjust(4, '0')).lower()
        try:
            gitenv = dict(os.environ)
            # forget all configs
            gitenv['RC_SCM_DATA'] = json.dumps(self.extras)
            command = [self.git_path, git_command[4:], '--stateless-rpc',
                       '--advertise-refs', self.content_path]
            out = subprocessio.SubprocessIOChunker(
                command,
                env=gitenv,
                starting_values=[packet_len + server_advert + '0000'],
                shell=False
            )
        except EnvironmentError:
            log.exception('Error processing command')
            raise exc.HTTPExpectationFailed()

        resp = Response()
        resp.content_type = 'application/x-%s-advertisement' % str(git_command)
        resp.charset = None
        resp.app_iter = out

        return resp

    def _get_want_capabilities(self, request):
        """Read the capabilities found in the first want line of the request."""
        pos = request.body_file_seekable.tell()
        first_line = request.body_file_seekable.readline()
        request.body_file_seekable.seek(pos)

        return frozenset(
            dulwich.protocol.extract_want_line_capabilities(first_line)[1])

    def _build_failed_pre_pull_response(self, capabilities, pre_pull_messages):
        """
        Construct a response with an empty PACK file.

        We use an empty PACK file, as that would trigger the failure of the pull
        or clone command.

        We also print in the error output a message explaining why the command
        was aborted.

        If aditionally, the user is accepting messages we send them the output
        of the pre-pull hook.

        Note that for clients not supporting side-band we just send them the
        emtpy PACK file.
        """
        if self.SIDE_BAND_CAPS.intersection(capabilities):
            response = []
            proto = dulwich.protocol.Protocol(None, response.append)
            proto.write_pkt_line('NAK\n')
            self._write_sideband_to_proto(pre_pull_messages, proto,
                                          capabilities)
            # N.B.(skreft): Do not change the sideband channel to 3, as that
            # produces a fatal error in the client:
            #   fatal: error in sideband demultiplexer
            proto.write_sideband(2, 'Pre pull hook failed: aborting\n')
            proto.write_sideband(1, self.EMPTY_PACK)

            # writes 0000
            proto.write_pkt_line(None)

            return response
        else:
            return [self.EMPTY_PACK]

    def _write_sideband_to_proto(self, data, proto, capabilities):
        """
        Write the data to the proto's sideband number 2.

        We do not use dulwich's write_sideband directly as it only supports
        side-band-64k.
        """
        if not data:
            return

        # N.B.(skreft): The values below are explained in the pack protocol
        # documentation, section Packfile Data.
        # https://github.com/git/git/blob/master/Documentation/technical/pack-protocol.txt
        if 'side-band-64k' in capabilities:
            chunk_size = 65515
        elif 'side-band' in capabilities:
            chunk_size = 995
        else:
            return

        chunker = (
            data[i:i + chunk_size] for i in xrange(0, len(data), chunk_size))

        for chunk in chunker:
            proto.write_sideband(2, chunk)

    def _get_messages(self, data, capabilities):
        """Return a list with packets for sending data in sideband number 2."""
        response = []
        proto = dulwich.protocol.Protocol(None, response.append)

        self._write_sideband_to_proto(data, proto, capabilities)

        return response

    def _inject_messages_to_response(self, response, capabilities,
                                     start_messages, end_messages):
        """
        Given a list reponse we inject the pre/post-pull messages.

        We only inject the messages if the client supports sideband, and the
        response has the format:
            0008NAK\n...0000

        Note that we do not check the no-progress capability as by default, git
        sends it, which effectively would block all messages.
        """
        if not self.SIDE_BAND_CAPS.intersection(capabilities):
            return response

        if (not response[0].startswith('0008NAK\n') or
                not response[-1].endswith('0000')):
            return response

        if not start_messages and not end_messages:
            return response

        new_response = ['0008NAK\n']
        new_response.extend(self._get_messages(start_messages, capabilities))
        if len(response) == 1:
            new_response.append(response[0][8:-4])
        else:
            new_response.append(response[0][8:])
            new_response.extend(response[1:-1])
            new_response.append(response[-1][:-4])
        new_response.extend(self._get_messages(end_messages, capabilities))
        new_response.append('0000')

        return new_response

    def backend(self, request, environ):
        """
        WSGI Response producer for HTTP POST Git Smart HTTP requests.
        Reads commands and data from HTTP POST's body.
        returns an iterator obj with contents of git command's
        response to stdout
        """
        # TODO(skreft): think how we could detect an HTTPLockedException, as
        # we probably want to have the same mechanism used by mercurial and
        # simplevcs.
        # For that we would need to parse the output of the command looking for
        # some signs of the HTTPLockedError, parse the data and reraise it in
        # pygrack. However, that would interfere with the streaming.
        #
        # Now the output of a blocked push is:
        # Pushing to http://test_regular:test12@127.0.0.1:5001/vcs_test_git
        # POST git-receive-pack (1047 bytes)
        # remote: ERROR: Repository `vcs_test_git` locked by user `test_admin`. Reason:`lock_auto`
        # To http://test_regular:test12@127.0.0.1:5001/vcs_test_git
        # ! [remote rejected] master -> master (pre-receive hook declined)
        # error: failed to push some refs to 'http://test_regular:test12@127.0.0.1:5001/vcs_test_git'

        git_command = self._get_fixedpath(request.path_info)
        if git_command not in self.commands:
            log.debug('command %s not allowed', git_command)
            return exc.HTTPForbidden()

        capabilities = None
        if git_command == 'git-upload-pack':
            capabilities = self._get_want_capabilities(request)

        if 'CONTENT_LENGTH' in environ:
            inputstream = FileWrapper(request.body_file_seekable,
                                      request.content_length)
        else:
            inputstream = request.body_file_seekable

        resp = Response()
        resp.content_type = ('application/x-%s-result' %
                             git_command.encode('utf8'))
        resp.charset = None

        if git_command == 'git-upload-pack':
            status, pre_pull_messages = hooks.git_pre_pull(self.extras)
            if status != 0:
                resp.app_iter = self._build_failed_pre_pull_response(
                    capabilities, pre_pull_messages)
                return resp

        gitenv = dict(os.environ)
        # forget all configs
        gitenv['GIT_CONFIG_NOGLOBAL'] = '1'
        gitenv['RC_SCM_DATA'] = json.dumps(self.extras)
        cmd = [self.git_path, git_command[4:], '--stateless-rpc',
               self.content_path]
        log.debug('handling cmd %s', cmd)

        out = subprocessio.SubprocessIOChunker(
            cmd,
            inputstream=inputstream,
            env=gitenv,
            cwd=self.content_path,
            shell=False,
            fail_on_stderr=False,
            fail_on_return_code=False
        )

        if self.update_server_info and git_command == 'git-receive-pack':
            # We need to fully consume the iterator here, as the
            # update-server-info command needs to be run after the push.
            out = list(out)

            # Updating refs manually after each push.
            # This is required as some clients are exposing Git repos internally
            # with the dumb protocol.
            cmd = [self.git_path, 'update-server-info']
            log.debug('handling cmd %s', cmd)
            output = subprocessio.SubprocessIOChunker(
                cmd,
                inputstream=inputstream,
                env=gitenv,
                cwd=self.content_path,
                shell=False,
                fail_on_stderr=False,
                fail_on_return_code=False
            )
            # Consume all the output so the subprocess finishes
            for _ in output:
                pass

        if git_command == 'git-upload-pack':
            out = list(out)
            unused_status, post_pull_messages = hooks.git_post_pull(self.extras)
            resp.app_iter = self._inject_messages_to_response(
                out, capabilities, pre_pull_messages, post_pull_messages)
        else:
            resp.app_iter = out

        return resp

    def __call__(self, environ, start_response):
        request = Request(environ)
        _path = self._get_fixedpath(request.path_info)
        if _path.startswith('info/refs'):
            app = self.inforefs
        else:
            app = self.backend

        try:
            resp = app(request, environ)
        except exc.HTTPException as error:
            log.exception('HTTP Error')
            resp = error
        except Exception:
            log.exception('Unknown error')
            resp = exc.HTTPInternalServerError()

        return resp(environ, start_response)
