"""
Provides the same API as :mod:`remote_wsgi`.

Uses the `EchoApp` instead of real implementations.
"""

import logging

from .echo_app import EchoApp
from vcsserver import wsgi_app_caller


log = logging.getLogger(__name__)


class GitRemoteWsgi(object):
    def handle(self, environ, input_data, *args, **kwargs):
        app = wsgi_app_caller.WSGIAppCaller(
            create_echo_wsgi_app(*args, **kwargs))

        return app.handle(environ, input_data)


class HgRemoteWsgi(object):
    def handle(self, environ, input_data, *args, **kwargs):
        app = wsgi_app_caller.WSGIAppCaller(
            create_echo_wsgi_app(*args, **kwargs))

        return app.handle(environ, input_data)


def create_echo_wsgi_app(repo_path, repo_name, config):
    log.debug("Creating EchoApp WSGI application")

    _assert_valid_config(config)

    # Remaining items are forwarded to have the extras available
    return EchoApp(repo_path, repo_name, config=config)


def _assert_valid_config(config):
    config = config.copy()

    # This is what git needs from config at this stage
    config.pop('git_update_server_info')
