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

from vcsserver import scm_app, wsgi_app_caller


class GitRemoteWsgi(object):
    def handle(self, environ, input_data, *args, **kwargs):
        app = wsgi_app_caller.WSGIAppCaller(
            scm_app.create_git_wsgi_app(*args, **kwargs))

        return app.handle(environ, input_data)


class HgRemoteWsgi(object):
    def handle(self, environ, input_data, *args, **kwargs):
        app = wsgi_app_caller.WSGIAppCaller(
            scm_app.create_hg_wsgi_app(*args, **kwargs))

        return app.handle(environ, input_data)
