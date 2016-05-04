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

import inspect
import sys
import traceback

import pytest
from mercurial.error import LookupError
from mock import Mock, MagicMock, patch

from vcsserver import exceptions, hg, hgcompat


class TestHGLookup(object):
    def setup(self):
        self.mock_repo = MagicMock()
        self.mock_repo.__getitem__.side_effect = LookupError(
            'revision_or_commit_id', 'index', 'message')
        factory = Mock()
        factory.repo = Mock(return_value=self.mock_repo)
        self.remote_hg = hg.HgRemote(factory)

    def test_fail_lookup_hg(self):
        with pytest.raises(Exception) as exc_info:
            self.remote_hg.lookup(
                wire=None, revision='revision_or_commit_id', both=True)

        assert exc_info.value._vcs_kind == 'lookup'
        assert 'revision_or_commit_id' in exc_info.value.args


class TestDiff(object):
    def test_raising_safe_exception_when_lookup_failed(self):
        repo = Mock()
        factory = Mock()
        factory.repo = Mock(return_value=repo)
        hg_remote = hg.HgRemote(factory)
        with patch('mercurial.patch.diff') as diff_mock:
            diff_mock.side_effect = LookupError(
                'deadbeef', 'index', 'message')
            with pytest.raises(Exception) as exc_info:
                hg_remote.diff(
                    wire=None, rev1='deadbeef', rev2='deadbee1',
                    file_filter=None, opt_git=True, opt_ignorews=True,
                    context=3)
            assert type(exc_info.value) == Exception
            assert exc_info.value._vcs_kind == 'lookup'


class TestReraiseSafeExceptions(object):
    def test_method_decorated_with_reraise_safe_exceptions(self):
        factory = Mock()
        hg_remote = hg.HgRemote(factory)
        methods = inspect.getmembers(hg_remote, predicate=inspect.ismethod)
        decorator = hg.reraise_safe_exceptions(None)
        for method_name, method in methods:
            if not method_name.startswith('_'):
                assert method.im_func.__code__ == decorator.__code__

    @pytest.mark.parametrize('side_effect, expected_type', [
        (hgcompat.Abort(), 'abort'),
        (hgcompat.InterventionRequired(), 'abort'),
        (hgcompat.RepoLookupError(), 'lookup'),
        (hgcompat.LookupError('deadbeef', 'index', 'message'), 'lookup'),
        (hgcompat.RepoError(), 'error'),
        (hgcompat.RequirementError(), 'requirement'),
    ])
    def test_safe_exceptions_reraised(self, side_effect, expected_type):
        @hg.reraise_safe_exceptions
        def fake_method():
            raise side_effect

        with pytest.raises(Exception) as exc_info:
            fake_method()
        assert type(exc_info.value) == Exception
        assert exc_info.value._vcs_kind == expected_type

    def test_keeps_original_traceback(self):
        @hg.reraise_safe_exceptions
        def fake_method():
            try:
                raise hgcompat.Abort()
            except:
                self.original_traceback = traceback.format_tb(
                    sys.exc_info()[2])
                raise

        try:
            fake_method()
        except Exception:
            new_traceback = traceback.format_tb(sys.exc_info()[2])

        new_traceback_tail = new_traceback[-len(self.original_traceback):]
        assert new_traceback_tail == self.original_traceback

    def test_maps_unknow_exceptions_to_unhandled(self):
        @hg.reraise_safe_exceptions
        def stub_method():
            raise ValueError('stub')

        with pytest.raises(Exception) as exc_info:
            stub_method()
        assert exc_info.value._vcs_kind == 'unhandled'

    def test_does_not_map_known_exceptions(self):
        @hg.reraise_safe_exceptions
        def stub_method():
            raise exceptions.LookupException('stub')

        with pytest.raises(Exception) as exc_info:
            stub_method()
        assert exc_info.value._vcs_kind == 'lookup'
