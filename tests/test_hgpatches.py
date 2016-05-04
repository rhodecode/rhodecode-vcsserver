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
import pytest

from vcsserver import hgcompat, hgpatches


LARGEFILES_CAPABILITY = 'largefiles=serve'


def test_patch_largefiles_capabilities_applies_patch(
        patched_capabilities):
    lfproto = hgcompat.largefiles.proto
    hgpatches.patch_largefiles_capabilities()
    assert lfproto.capabilities.func_name == '_dynamic_capabilities'


def test_dynamic_capabilities_uses_original_function_if_not_enabled(
        stub_repo, stub_proto, stub_ui, stub_extensions, patched_capabilities):
    dynamic_capabilities = hgpatches._dynamic_capabilities_wrapper(
        hgcompat.largefiles.proto, stub_extensions)

    caps = dynamic_capabilities(stub_repo, stub_proto)

    stub_extensions.assert_called_once_with(stub_ui)
    assert LARGEFILES_CAPABILITY not in caps


def test_dynamic_capabilities_uses_updated_capabilitiesorig(
        stub_repo, stub_proto, stub_ui, stub_extensions, patched_capabilities):
    dynamic_capabilities = hgpatches._dynamic_capabilities_wrapper(
        hgcompat.largefiles.proto, stub_extensions)

    # This happens when the extension is loaded for the first time, important
    # to ensure that an updated function is correctly picked up.
    hgcompat.largefiles.proto.capabilitiesorig = mock.Mock(
        return_value='REPLACED')

    caps = dynamic_capabilities(stub_repo, stub_proto)
    assert 'REPLACED' == caps


def test_dynamic_capabilities_ignores_updated_capabilities(
        stub_repo, stub_proto, stub_ui, stub_extensions, patched_capabilities):
    stub_extensions.return_value = [('largefiles', mock.Mock())]
    dynamic_capabilities = hgpatches._dynamic_capabilities_wrapper(
        hgcompat.largefiles.proto, stub_extensions)

    # This happens when the extension is loaded for the first time, important
    # to ensure that an updated function is correctly picked up.
    hgcompat.largefiles.proto.capabilities = mock.Mock(
        side_effect=Exception('Must not be called'))

    dynamic_capabilities(stub_repo, stub_proto)


def test_dynamic_capabilities_uses_largefiles_if_enabled(
        stub_repo, stub_proto, stub_ui, stub_extensions, patched_capabilities):
    stub_extensions.return_value = [('largefiles', mock.Mock())]

    dynamic_capabilities = hgpatches._dynamic_capabilities_wrapper(
        hgcompat.largefiles.proto, stub_extensions)

    caps = dynamic_capabilities(stub_repo, stub_proto)

    stub_extensions.assert_called_once_with(stub_ui)
    assert LARGEFILES_CAPABILITY in caps


@pytest.fixture
def patched_capabilities(request):
    """
    Patch in `capabilitiesorig` and restore both capability functions.
    """
    lfproto = hgcompat.largefiles.proto
    orig_capabilities = lfproto.capabilities
    orig_capabilitiesorig = lfproto.capabilitiesorig

    lfproto.capabilitiesorig = mock.Mock(return_value='ORIG')

    @request.addfinalizer
    def restore():
        lfproto.capabilities = orig_capabilities
        lfproto.capabilitiesorig = orig_capabilitiesorig


@pytest.fixture
def stub_repo(stub_ui):
    repo = mock.Mock()
    repo.ui = stub_ui
    return repo


@pytest.fixture
def stub_proto(stub_ui):
    proto = mock.Mock()
    proto.ui = stub_ui
    return proto


@pytest.fixture
def stub_ui():
    return hgcompat.ui.ui()


@pytest.fixture
def stub_extensions():
    extensions = mock.Mock(return_value=tuple())
    return extensions
