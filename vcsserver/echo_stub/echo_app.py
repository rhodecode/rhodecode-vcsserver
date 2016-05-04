"""
Implementation of :class:`EchoApp`.

This WSGI application will just echo back the data which it recieves.
"""

import logging


log = logging.getLogger(__name__)


class EchoApp(object):

    def __init__(self, repo_path, repo_name, config):
        self._repo_path = repo_path
        log.info("EchoApp initialized for %s", repo_path)

    def __call__(self, environ, start_response):
        log.debug("EchoApp called for %s", self._repo_path)
        log.debug("Content-Length: %s", environ.get('CONTENT_LENGTH'))
        environ['wsgi.input'].read()
        status = '200 OK'
        headers = []
        start_response(status, headers)
        return ["ECHO"]


def create_app():
    """
    Allows to run this app directly in a WSGI server.
    """
    stub_config = {}
    return EchoApp('stub_path', 'stub_name', stub_config)
