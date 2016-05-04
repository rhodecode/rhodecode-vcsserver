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
Adjustments to Mercurial

Intentionally kept separate from `hgcompat` and `hg`, so that these patches can
be applied without having to import the whole Mercurial machinery.

Imports are function local, so that just importing this module does not cause
side-effects other than these functions being defined.
"""

import logging


def patch_largefiles_capabilities():
    """
    Patches the capabilities function in the largefiles extension.
    """
    from vcsserver import hgcompat
    lfproto = hgcompat.largefiles.proto
    wrapper = _dynamic_capabilities_wrapper(
        lfproto, hgcompat.extensions.extensions)
    lfproto.capabilities = wrapper


def _dynamic_capabilities_wrapper(lfproto, extensions):

    wrapped_capabilities = lfproto.capabilities
    logger = logging.getLogger('vcsserver.hg')

    def _dynamic_capabilities(repo, proto):
        """
        Adds dynamic behavior, so that the capability is only added if the
        extension is enabled in the current ui object.
        """
        if 'largefiles' in dict(extensions(repo.ui)):
            logger.debug('Extension largefiles enabled')
            calc_capabilities = wrapped_capabilities
        else:
            logger.debug('Extension largefiles disabled')
            calc_capabilities = lfproto.capabilitiesorig
        return calc_capabilities(repo, proto)

    return _dynamic_capabilities
