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

import base64
import locale
import logging
import uuid
import wsgiref.util
from itertools import chain

import msgpack
from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options
from pyramid.config import Configurator
from pyramid.wsgi import wsgiapp

from vcsserver import remote_wsgi, scm_app, settings, hgpatches
from vcsserver.echo_stub import remote_wsgi as remote_wsgi_stub
from vcsserver.echo_stub.echo_app import EchoApp
from vcsserver.server import VcsServer

try:
    from vcsserver.git import GitFactory, GitRemote
except ImportError:
    GitFactory = None
    GitRemote = None
try:
    from vcsserver.hg import MercurialFactory, HgRemote
except ImportError:
    MercurialFactory = None
    HgRemote = None
try:
    from vcsserver.svn import SubversionFactory, SvnRemote
except ImportError:
    SubversionFactory = None
    SvnRemote = None

log = logging.getLogger(__name__)


class VCS(object):
    def __init__(self, locale=None, cache_config=None):
        self.locale = locale
        self.cache_config = cache_config
        self._configure_locale()
        self._initialize_cache()

        if GitFactory and GitRemote:
            git_repo_cache = self.cache.get_cache_region(
                'git', region='repo_object')
            git_factory = GitFactory(git_repo_cache)
            self._git_remote = GitRemote(git_factory)
        else:
            log.info("Git client import failed")

        if MercurialFactory and HgRemote:
            hg_repo_cache = self.cache.get_cache_region(
                'hg', region='repo_object')
            hg_factory = MercurialFactory(hg_repo_cache)
            self._hg_remote = HgRemote(hg_factory)
        else:
            log.info("Mercurial client import failed")

        if SubversionFactory and SvnRemote:
            svn_repo_cache = self.cache.get_cache_region(
                'svn', region='repo_object')
            svn_factory = SubversionFactory(svn_repo_cache)
            self._svn_remote = SvnRemote(svn_factory, hg_factory=hg_factory)
        else:
            log.info("Subversion client import failed")

        self._vcsserver = VcsServer()

    def _initialize_cache(self):
        cache_config = parse_cache_config_options(self.cache_config)
        log.info('Initializing beaker cache: %s' % cache_config)
        self.cache = CacheManager(**cache_config)

    def _configure_locale(self):
        if self.locale:
            log.info('Settings locale: `LC_ALL` to %s' % self.locale)
        else:
            log.info(
                'Configuring locale subsystem based on environment variables')
        try:
            # If self.locale is the empty string, then the locale
            # module will use the environment variables. See the
            # documentation of the package `locale`.
            locale.setlocale(locale.LC_ALL, self.locale)

            language_code, encoding = locale.getlocale()
            log.info(
                'Locale set to language code "%s" with encoding "%s".',
                language_code, encoding)
        except locale.Error:
            log.exception(
                'Cannot set locale, not configuring the locale system')


class WsgiProxy(object):
    def __init__(self, wsgi):
        self.wsgi = wsgi

    def __call__(self, environ, start_response):
        input_data = environ['wsgi.input'].read()
        input_data = msgpack.unpackb(input_data)

        error = None
        try:
            data, status, headers = self.wsgi.handle(
                input_data['environment'], input_data['input_data'],
                *input_data['args'], **input_data['kwargs'])
        except Exception as e:
            data, status, headers = [], None, None
            error = {
                'message': str(e),
                '_vcs_kind': getattr(e, '_vcs_kind', None)
            }

        start_response(200, {})
        return self._iterator(error, status, headers, data)

    def _iterator(self, error, status, headers, data):
        initial_data = [
            error,
            status,
            headers,
        ]

        for d in chain(initial_data, data):
            yield msgpack.packb(d)


class HTTPApplication(object):
    ALLOWED_EXCEPTIONS = ('KeyError', 'URLError')

    remote_wsgi = remote_wsgi
    _use_echo_app = False

    def __init__(self, settings=None):
        self.config = Configurator(settings=settings)
        locale = settings.get('', 'en_US.UTF-8')
        vcs = VCS(locale=locale, cache_config=settings)
        self._remotes = {
            'hg': vcs._hg_remote,
            'git': vcs._git_remote,
            'svn': vcs._svn_remote,
            'server': vcs._vcsserver,
        }
        if settings.get('dev.use_echo_app', 'false').lower() == 'true':
            self._use_echo_app = True
            log.warning("Using EchoApp for VCS operations.")
            self.remote_wsgi = remote_wsgi_stub
        self._configure_settings(settings)
        self._configure()

    def _configure_settings(self, app_settings):
        """
        Configure the settings module.
        """
        git_path = app_settings.get('git_path', None)
        if git_path:
            settings.GIT_EXECUTABLE = git_path

    def _configure(self):
        self.config.add_renderer(
            name='msgpack',
            factory=self._msgpack_renderer_factory)

        self.config.add_route('status', '/status')
        self.config.add_route('hg_proxy', '/proxy/hg')
        self.config.add_route('git_proxy', '/proxy/git')
        self.config.add_route('vcs', '/{backend}')
        self.config.add_route('stream_git', '/stream/git/*repo_name')
        self.config.add_route('stream_hg', '/stream/hg/*repo_name')

        self.config.add_view(
            self.status_view, route_name='status', renderer='json')
        self.config.add_view(self.hg_proxy(), route_name='hg_proxy')
        self.config.add_view(self.git_proxy(), route_name='git_proxy')
        self.config.add_view(
            self.vcs_view, route_name='vcs', renderer='msgpack')

        self.config.add_view(self.hg_stream(), route_name='stream_hg')
        self.config.add_view(self.git_stream(), route_name='stream_git')

    def wsgi_app(self):
        return self.config.make_wsgi_app()

    def vcs_view(self, request):
        remote = self._remotes[request.matchdict['backend']]
        payload = msgpack.unpackb(request.body, use_list=True)
        method = payload.get('method')
        params = payload.get('params')
        wire = params.get('wire')
        args = params.get('args')
        kwargs = params.get('kwargs')
        if wire:
            try:
                wire['context'] = uuid.UUID(wire['context'])
            except KeyError:
                pass
            args.insert(0, wire)

        try:
            resp = getattr(remote, method)(*args, **kwargs)
        except Exception as e:
            type_ = e.__class__.__name__
            if type_ not in self.ALLOWED_EXCEPTIONS:
                type_ = None

            resp = {
                'id': payload.get('id'),
                'error': {
                    'message': e.message,
                    'type': type_
                }
            }
            try:
                resp['error']['_vcs_kind'] = e._vcs_kind
            except AttributeError:
                pass
        else:
            resp = {
                'id': payload.get('id'),
                'result': resp
            }

        return resp

    def status_view(self, request):
        return {'status': 'OK'}

    def _msgpack_renderer_factory(self, info):
        def _render(value, system):
            value = msgpack.packb(value)
            request = system.get('request')
            if request is not None:
                response = request.response
                ct = response.content_type
                if ct == response.default_content_type:
                    response.content_type = 'application/x-msgpack'
            return value
        return _render

    def hg_proxy(self):
        @wsgiapp
        def _hg_proxy(environ, start_response):
            app = WsgiProxy(self.remote_wsgi.HgRemoteWsgi())
            return app(environ, start_response)
        return _hg_proxy

    def git_proxy(self):
        @wsgiapp
        def _git_proxy(environ, start_response):
            app = WsgiProxy(self.remote_wsgi.GitRemoteWsgi())
            return app(environ, start_response)
        return _git_proxy

    def hg_stream(self):
        if self._use_echo_app:
            @wsgiapp
            def _hg_stream(environ, start_response):
                app = EchoApp('fake_path', 'fake_name', None)
                return app(environ, start_response)
            return _hg_stream
        else:
            @wsgiapp
            def _hg_stream(environ, start_response):
                repo_path = environ['HTTP_X_RC_REPO_PATH']
                repo_name = environ['HTTP_X_RC_REPO_NAME']
                packed_config = base64.b64decode(
                    environ['HTTP_X_RC_REPO_CONFIG'])
                config = msgpack.unpackb(packed_config)
                app = scm_app.create_hg_wsgi_app(
                    repo_path, repo_name, config)

                # Consitent path information for hgweb
                environ['PATH_INFO'] = environ['HTTP_X_RC_PATH_INFO']
                environ['REPO_NAME'] = repo_name
                return app(environ, ResponseFilter(start_response))
            return _hg_stream

    def git_stream(self):
        if self._use_echo_app:
            @wsgiapp
            def _git_stream(environ, start_response):
                app = EchoApp('fake_path', 'fake_name', None)
                return app(environ, start_response)
            return _git_stream
        else:
            @wsgiapp
            def _git_stream(environ, start_response):
                repo_path = environ['HTTP_X_RC_REPO_PATH']
                repo_name = environ['HTTP_X_RC_REPO_NAME']
                packed_config = base64.b64decode(
                    environ['HTTP_X_RC_REPO_CONFIG'])
                config = msgpack.unpackb(packed_config)

                environ['PATH_INFO'] = environ['HTTP_X_RC_PATH_INFO']
                app = scm_app.create_git_wsgi_app(
                    repo_path, repo_name, config)
                return app(environ, start_response)
            return _git_stream


class ResponseFilter(object):

    def __init__(self, start_response):
        self._start_response = start_response

    def __call__(self, status, response_headers, exc_info=None):
        headers = tuple(
            (h, v) for h, v in response_headers
            if not wsgiref.util.is_hop_by_hop(h))
        return self._start_response(status, headers, exc_info)


def main(global_config, **settings):
    if MercurialFactory:
        hgpatches.patch_largefiles_capabilities()
    app = HTTPApplication(settings=settings)
    return app.wsgi_app()
