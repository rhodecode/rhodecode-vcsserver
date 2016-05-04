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


PYRO_PORT = 9900

PYRO_GIT = 'git_remote'
PYRO_HG = 'hg_remote'
PYRO_SVN = 'svn_remote'
PYRO_VCSSERVER = 'vcs_server'
PYRO_GIT_REMOTE_WSGI = 'git_remote_wsgi'
PYRO_HG_REMOTE_WSGI = 'hg_remote_wsgi'

WIRE_ENCODING = 'UTF-8'

GIT_EXECUTABLE = 'git'
