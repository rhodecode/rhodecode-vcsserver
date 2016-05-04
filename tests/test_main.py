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

import mock

from vcsserver import main


@mock.patch('vcsserver.main.VcsServerCommand', mock.Mock())
@mock.patch('vcsserver.hgpatches.patch_largefiles_capabilities')
def test_applies_largefiles_patch(patch_largefiles_capabilities):
    main.main([])
    patch_largefiles_capabilities.assert_called_once_with()


@mock.patch('vcsserver.main.VcsServerCommand', mock.Mock())
@mock.patch('vcsserver.main.MercurialFactory', None)
@mock.patch(
    'vcsserver.hgpatches.patch_largefiles_capabilities',
    mock.Mock(side_effect=Exception("Must not be called")))
def test_applies_largefiles_patch_only_if_mercurial_is_available():
    main.main([])
