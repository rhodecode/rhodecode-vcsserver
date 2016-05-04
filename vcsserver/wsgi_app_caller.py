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

"""Extract the responses of a WSGI app."""

__all__ = ('WSGIAppCaller',)

import io
import logging
import os


log = logging.getLogger(__name__)

DEV_NULL = open(os.devnull)


def _complete_environ(environ, input_data):
    """Update the missing wsgi.* variables of a WSGI environment.

    :param environ: WSGI environment to update
    :type environ: dict
    :param input_data: data to be read by the app
    :type input_data: str
    """
    environ.update({
        'wsgi.version': (1, 0),
        'wsgi.url_scheme': 'http',
        'wsgi.multithread': True,
        'wsgi.multiprocess': True,
        'wsgi.run_once': False,
        'wsgi.input': io.BytesIO(input_data),
        'wsgi.errors': DEV_NULL,
    })


# pylint: disable=too-few-public-methods
class _StartResponse(object):
    """Save the arguments of a start_response call."""

    __slots__ = ['status', 'headers', 'content']

    def __init__(self):
        self.status = None
        self.headers = None
        self.content = []

    def __call__(self, status, headers, exc_info=None):
        # TODO(skreft): do something meaningful with the exc_info
        exc_info = None  # avoid dangling circular reference
        self.status = status
        self.headers = headers

        return self.write

    def write(self, content):
        """Write method returning when calling this object.

        All the data written is then available in content.
        """
        self.content.append(content)


class WSGIAppCaller(object):
    """Calls a WSGI app."""

    def __init__(self, app):
        """
        :param app: WSGI app to call
        """
        self.app = app

    def handle(self, environ, input_data):
        """Process a request with the WSGI app.

        The returned data of the app is fully consumed into a list.

        :param environ: WSGI environment to update
        :type environ: dict
        :param input_data: data to be read by the app
        :type input_data: str

        :returns: a tuple with the contents, status and headers
        :rtype: (list<str>, str, list<(str, str)>)
        """
        _complete_environ(environ, input_data)
        start_response = _StartResponse()
        log.debug("Calling wrapped WSGI application")
        responses = self.app(environ, start_response)
        responses_list = list(responses)
        existing_responses = start_response.content
        if existing_responses:
            log.debug(
                "Adding returned response to response written via write()")
            existing_responses.extend(responses_list)
            responses_list = existing_responses
        if hasattr(responses, 'close'):
            log.debug("Closing iterator from WSGI application")
            responses.close()

        log.debug("Handling of WSGI request done, returning response")
        return responses_list, start_response.status, start_response.headers
