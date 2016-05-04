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

import wsgiref.simple_server
import wsgiref.validate

from vcsserver import wsgi_app_caller


# pylint: disable=protected-access,too-many-public-methods


@wsgiref.validate.validator
def demo_app(environ, start_response):
    """WSGI app used for testing."""
    data = [
        'Hello World!\n',
        'input_data=%s\n' % environ['wsgi.input'].read(),
    ]
    for key, value in sorted(environ.items()):
        data.append('%s=%s\n' % (key, value))

    write = start_response("200 OK", [('Content-Type', 'text/plain')])
    write('Old school write method\n')
    write('***********************\n')
    return data


BASE_ENVIRON = {
    'REQUEST_METHOD': 'GET',
    'SERVER_NAME': 'localhost',
    'SERVER_PORT': '80',
    'SCRIPT_NAME': '',
    'PATH_INFO': '/',
    'QUERY_STRING': '',
    'foo.var': 'bla',
}


def test_complete_environ():
    environ = dict(BASE_ENVIRON)
    data = "data"
    wsgi_app_caller._complete_environ(environ, data)
    wsgiref.validate.check_environ(environ)

    assert data == environ['wsgi.input'].read()


def test_start_response():
    start_response = wsgi_app_caller._StartResponse()
    status = '200 OK'
    headers = [('Content-Type', 'text/plain')]
    start_response(status, headers)

    assert status == start_response.status
    assert headers == start_response.headers


def test_start_response_with_error():
    start_response = wsgi_app_caller._StartResponse()
    status = '500 Internal Server Error'
    headers = [('Content-Type', 'text/plain')]
    start_response(status, headers, (None, None, None))

    assert status == start_response.status
    assert headers == start_response.headers


def test_wsgi_app_caller():
    caller = wsgi_app_caller.WSGIAppCaller(demo_app)
    environ = dict(BASE_ENVIRON)
    input_data = 'some text'
    responses, status, headers = caller.handle(environ, input_data)
    response = ''.join(responses)

    assert status == '200 OK'
    assert headers == [('Content-Type', 'text/plain')]
    assert response.startswith(
        'Old school write method\n***********************\n')
    assert 'Hello World!\n' in response
    assert 'foo.var=bla\n' in response
    assert 'input_data=%s\n' % input_data in response
