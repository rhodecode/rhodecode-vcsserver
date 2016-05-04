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

import dulwich.protocol
import mock
import pytest
import webob
import webtest

from vcsserver import hooks, pygrack

# pylint: disable=redefined-outer-name,protected-access


@pytest.fixture()
def pygrack_instance(tmpdir):
    """
    Creates a pygrack app instance.

    Right now, it does not much helpful regarding the passed directory.
    It just contains the required folders to pass the signature test.
    """
    for dir_name in ('config', 'head', 'info', 'objects', 'refs'):
        tmpdir.mkdir(dir_name)

    return pygrack.GitRepository('repo_name', str(tmpdir), 'git', False, {})


@pytest.fixture()
def pygrack_app(pygrack_instance):
    """
    Creates a pygrack app wrapped in webtest.TestApp.
    """
    return webtest.TestApp(pygrack_instance)


def test_invalid_service_info_refs_returns_403(pygrack_app):
    response = pygrack_app.get('/info/refs?service=git-upload-packs',
                               expect_errors=True)

    assert response.status_int == 403


def test_invalid_endpoint_returns_403(pygrack_app):
    response = pygrack_app.post('/git-upload-packs', expect_errors=True)

    assert response.status_int == 403


@pytest.mark.parametrize('sideband', [
    'side-band-64k',
    'side-band',
    'side-band no-progress',
])
def test_pre_pull_hook_fails_with_sideband(pygrack_app, sideband):
    request = ''.join([
        '0054want 74730d410fcb6603ace96f1dc55ea6196122532d ',
        'multi_ack %s ofs-delta\n' % sideband,
        '0000',
        '0009done\n',
    ])
    with mock.patch('vcsserver.hooks.git_pre_pull',
                    return_value=hooks.HookResponse(1, 'foo')):
        response = pygrack_app.post(
            '/git-upload-pack', params=request,
            content_type='application/x-git-upload-pack')

    data = io.BytesIO(response.body)
    proto = dulwich.protocol.Protocol(data.read, None)
    packets = list(proto.read_pkt_seq())

    expected_packets = [
        'NAK\n', '\x02foo', '\x02Pre pull hook failed: aborting\n',
        '\x01' + pygrack.GitRepository.EMPTY_PACK,
    ]
    assert packets == expected_packets


def test_pre_pull_hook_fails_no_sideband(pygrack_app):
    request = ''.join([
        '0054want 74730d410fcb6603ace96f1dc55ea6196122532d ' +
        'multi_ack ofs-delta\n'
        '0000',
        '0009done\n',
    ])
    with mock.patch('vcsserver.hooks.git_pre_pull',
                    return_value=hooks.HookResponse(1, 'foo')):
        response = pygrack_app.post(
            '/git-upload-pack', params=request,
            content_type='application/x-git-upload-pack')

    assert response.body == pygrack.GitRepository.EMPTY_PACK


def test_pull_has_hook_messages(pygrack_app):
    request = ''.join([
        '0054want 74730d410fcb6603ace96f1dc55ea6196122532d ' +
        'multi_ack side-band-64k ofs-delta\n'
        '0000',
        '0009done\n',
    ])
    with mock.patch('vcsserver.hooks.git_pre_pull',
                    return_value=hooks.HookResponse(0, 'foo')):
        with mock.patch('vcsserver.hooks.git_post_pull',
                        return_value=hooks.HookResponse(1, 'bar')):
            with mock.patch('vcsserver.subprocessio.SubprocessIOChunker',
                            return_value=['0008NAK\n0009subp\n0000']):
                response = pygrack_app.post(
                    '/git-upload-pack', params=request,
                    content_type='application/x-git-upload-pack')

    data = io.BytesIO(response.body)
    proto = dulwich.protocol.Protocol(data.read, None)
    packets = list(proto.read_pkt_seq())

    assert packets == ['NAK\n', '\x02foo', 'subp\n', '\x02bar']


def test_get_want_capabilities(pygrack_instance):
    data = io.BytesIO(
        '0054want 74730d410fcb6603ace96f1dc55ea6196122532d ' +
        'multi_ack side-band-64k ofs-delta\n00000009done\n')

    request = webob.Request({
        'wsgi.input': data,
        'REQUEST_METHOD': 'POST',
        'webob.is_body_seekable': True
    })

    capabilities = pygrack_instance._get_want_capabilities(request)

    assert capabilities == frozenset(
        ('ofs-delta', 'multi_ack', 'side-band-64k'))
    assert data.tell() == 0


@pytest.mark.parametrize('data,capabilities,expected', [
    ('foo', [], []),
    ('', ['side-band-64k'], []),
    ('', ['side-band'], []),
    ('foo', ['side-band-64k'], ['0008\x02foo']),
    ('foo', ['side-band'], ['0008\x02foo']),
    ('f'*1000, ['side-band-64k'], ['03ed\x02' + 'f' * 1000]),
    ('f'*1000, ['side-band'], ['03e8\x02' + 'f' * 995, '000a\x02fffff']),
    ('f'*65520, ['side-band-64k'], ['fff0\x02' + 'f' * 65515, '000a\x02fffff']),
    ('f'*65520, ['side-band'], ['03e8\x02' + 'f' * 995] * 65 + ['0352\x02' + 'f' * 845]),
], ids=[
    'foo-empty',
    'empty-64k', 'empty',
    'foo-64k', 'foo',
    'f-1000-64k', 'f-1000',
    'f-65520-64k', 'f-65520'])
def test_get_messages(pygrack_instance, data, capabilities, expected):
    messages = pygrack_instance._get_messages(data, capabilities)

    assert messages == expected


@pytest.mark.parametrize('response,capabilities,pre_pull_messages,post_pull_messages', [
    # Unexpected response
    ('unexpected_response', ['side-band-64k'], 'foo', 'bar'),
    # No sideband
    ('no-sideband', [], 'foo', 'bar'),
    # No messages
    ('no-messages', ['side-band-64k'], '', ''),
])
def test_inject_messages_to_response_nothing_to_do(
        pygrack_instance, response, capabilities, pre_pull_messages,
        post_pull_messages):
    new_response = pygrack_instance._inject_messages_to_response(
        response, capabilities, pre_pull_messages, post_pull_messages)

    assert new_response == response


@pytest.mark.parametrize('capabilities', [
    ['side-band'],
    ['side-band-64k'],
])
def test_inject_messages_to_response_single_element(pygrack_instance,
                                                    capabilities):
    response = ['0008NAK\n0009subp\n0000']
    new_response = pygrack_instance._inject_messages_to_response(
        response, capabilities, 'foo', 'bar')

    expected_response = [
        '0008NAK\n', '0008\x02foo', '0009subp\n', '0008\x02bar', '0000']

    assert new_response == expected_response


@pytest.mark.parametrize('capabilities', [
    ['side-band'],
    ['side-band-64k'],
])
def test_inject_messages_to_response_multi_element(pygrack_instance,
                                                   capabilities):
    response = [
        '0008NAK\n000asubp1\n', '000asubp2\n', '000asubp3\n', '000asubp4\n0000']
    new_response = pygrack_instance._inject_messages_to_response(
        response, capabilities, 'foo', 'bar')

    expected_response = [
        '0008NAK\n', '0008\x02foo', '000asubp1\n', '000asubp2\n', '000asubp3\n',
        '000asubp4\n', '0008\x02bar', '0000'
    ]

    assert new_response == expected_response


def test_build_failed_pre_pull_response_no_sideband(pygrack_instance):
    response = pygrack_instance._build_failed_pre_pull_response([], 'foo')

    assert response == [pygrack.GitRepository.EMPTY_PACK]


@pytest.mark.parametrize('capabilities', [
    ['side-band'],
    ['side-band-64k'],
    ['side-band-64k', 'no-progress'],
])
def test_build_failed_pre_pull_response(pygrack_instance, capabilities):
    response = pygrack_instance._build_failed_pre_pull_response(
        capabilities, 'foo')

    expected_response = [
        '0008NAK\n', '0008\x02foo', '0024\x02Pre pull hook failed: aborting\n',
        '%04x\x01%s' % (len(pygrack.GitRepository.EMPTY_PACK) + 5,
                        pygrack.GitRepository.EMPTY_PACK),
        '0000',
    ]

    assert response == expected_response
