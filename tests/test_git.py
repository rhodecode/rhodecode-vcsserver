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

import pytest
import dulwich.errors
from mock import Mock, patch

from vcsserver import git


SAMPLE_REFS = {
    'HEAD': 'fd627b9e0dd80b47be81af07c4a98518244ed2f7',
    'refs/tags/v0.1.9': '341d28f0eec5ddf0b6b77871e13c2bbd6bec685c',
    'refs/tags/v0.1.8': '74ebce002c088b8a5ecf40073db09375515ecd68',
    'refs/tags/v0.1.1': 'e6ea6d16e2f26250124a1f4b4fe37a912f9d86a0',
    'refs/tags/v0.1.3': '5a3a8fb005554692b16e21dee62bf02667d8dc3e',
}


@pytest.fixture
def git_remote():
    """
    A GitRemote instance with a mock factory.
    """
    factory = Mock()
    remote = git.GitRemote(factory)
    return remote


def test_discover_git_version(git_remote):
    version = git_remote.discover_git_version()
    assert version


class TestGitFetch(object):
    def setup(self):
        self.mock_repo = Mock()
        factory = Mock()
        factory.repo = Mock(return_value=self.mock_repo)
        self.remote_git = git.GitRemote(factory)

    def test_fetches_all_when_no_commit_ids_specified(self):
        def side_effect(determine_wants, *args, **kwargs):
            determine_wants(SAMPLE_REFS)

        with patch('dulwich.client.LocalGitClient.fetch') as mock_fetch:
            mock_fetch.side_effect = side_effect
            self.remote_git.fetch(wire=None, url='/tmp/', apply_refs=False)
            determine_wants = self.mock_repo.object_store.determine_wants_all
            determine_wants.assert_called_once_with(SAMPLE_REFS)

    def test_fetches_specified_commits(self):
        selected_refs = {
            'refs/tags/v0.1.8': '74ebce002c088b8a5ecf40073db09375515ecd68',
            'refs/tags/v0.1.3': '5a3a8fb005554692b16e21dee62bf02667d8dc3e',
        }

        def side_effect(determine_wants, *args, **kwargs):
            result = determine_wants(SAMPLE_REFS)
            assert sorted(result) == sorted(selected_refs.values())
            return result

        with patch('dulwich.client.LocalGitClient.fetch') as mock_fetch:
            mock_fetch.side_effect = side_effect
            self.remote_git.fetch(
                wire=None, url='/tmp/', apply_refs=False,
                refs=selected_refs.keys())
            determine_wants = self.mock_repo.object_store.determine_wants_all
            assert determine_wants.call_count == 0

    def test_get_remote_refs(self):
        factory = Mock()
        remote_git = git.GitRemote(factory)
        url = 'http://example.com/test/test.git'
        sample_refs = {
            'refs/tags/v0.1.8': '74ebce002c088b8a5ecf40073db09375515ecd68',
            'refs/tags/v0.1.3': '5a3a8fb005554692b16e21dee62bf02667d8dc3e',
        }

        with patch('vcsserver.git.Repo', create=False) as mock_repo:
            mock_repo().get_refs.return_value = sample_refs
            remote_refs = remote_git.get_remote_refs(wire=None, url=url)
            mock_repo().get_refs.assert_called_once_with()
            assert remote_refs == sample_refs

    def test_remove_ref(self):
        ref_to_remove = 'refs/tags/v0.1.9'
        self.mock_repo.refs = SAMPLE_REFS.copy()
        self.remote_git.remove_ref(None, ref_to_remove)
        assert ref_to_remove not in self.mock_repo.refs


class TestReraiseSafeExceptions(object):
    def test_method_decorated_with_reraise_safe_exceptions(self):
        factory = Mock()
        git_remote = git.GitRemote(factory)

        def fake_function():
            return None

        decorator = git.reraise_safe_exceptions(fake_function)

        methods = inspect.getmembers(git_remote, predicate=inspect.ismethod)
        for method_name, method in methods:
            if not method_name.startswith('_'):
                assert method.im_func.__code__ == decorator.__code__

    @pytest.mark.parametrize('side_effect, expected_type', [
        (dulwich.errors.ChecksumMismatch('0000000', 'deadbeef'), 'lookup'),
        (dulwich.errors.NotCommitError('deadbeef'), 'lookup'),
        (dulwich.errors.MissingCommitError('deadbeef'), 'lookup'),
        (dulwich.errors.ObjectMissing('deadbeef'), 'lookup'),
        (dulwich.errors.HangupException(), 'error'),
        (dulwich.errors.UnexpectedCommandError('test-cmd'), 'error'),
    ])
    def test_safe_exceptions_reraised(self, side_effect, expected_type):
        @git.reraise_safe_exceptions
        def fake_method():
            raise side_effect

        with pytest.raises(Exception) as exc_info:
            fake_method()
        assert type(exc_info.value) == Exception
        assert exc_info.value._vcs_kind == expected_type


class TestDulwichRepoWrapper(object):
    def test_calls_close_on_delete(self):
        isdir_patcher = patch('dulwich.repo.os.path.isdir', return_value=True)
        with isdir_patcher:
            repo = git.Repo('/tmp/abcde')
        with patch.object(git.DulwichRepo, 'close') as close_mock:
            del repo
        close_mock.assert_called_once_with()


class TestGitFactory(object):
    def test_create_repo_returns_dulwich_wrapper(self):
        factory = git.GitFactory(repo_cache=Mock())
        wire = {
            'path': '/tmp/abcde'
        }
        isdir_patcher = patch('dulwich.repo.os.path.isdir', return_value=True)
        with isdir_patcher:
            result = factory._create_repo(wire, True)
        assert isinstance(result, git.Repo)
