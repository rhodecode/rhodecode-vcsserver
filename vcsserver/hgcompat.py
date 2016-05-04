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

"""
Mercurial libs compatibility
"""

import mercurial
import mercurial.demandimport
# patch demandimport, due to bug in mercurial when it always triggers
# demandimport.enable()
mercurial.demandimport.enable = lambda *args, **kwargs: 1

from mercurial import ui
from mercurial import patch
from mercurial import config
from mercurial import extensions
from mercurial import scmutil
from mercurial import archival
from mercurial import discovery
from mercurial import unionrepo
from mercurial import localrepo
from mercurial import merge as hg_merge

from mercurial.commands import clone, nullid, pull
from mercurial.context import memctx, memfilectx
from mercurial.error import (
    LookupError, RepoError, RepoLookupError, Abort, InterventionRequired,
    RequirementError)
from mercurial.hgweb import hgweb_mod
from mercurial.localrepo import localrepository
from mercurial.match import match
from mercurial.mdiff import diffopts
from mercurial.node import bin, hex
from mercurial.encoding import tolocal
from mercurial.discovery import findcommonoutgoing
from mercurial.hg import peer
from mercurial.httppeer import httppeer
from mercurial.util import url as hg_url
from mercurial.scmutil import revrange
from mercurial.node import nullrev
from mercurial import exchange
from hgext import largefiles

# those authnadlers are patched for python 2.6.5 bug an
# infinit looping when given invalid resources
from mercurial.url import httpbasicauthhandler, httpdigestauthhandler
