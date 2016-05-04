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

import os

import mercurial.hg
import mercurial.ui
import mercurial.error
import mock
import pytest
import webtest

from vcsserver import scm_app


def test_hg_does_not_accept_invalid_cmd(tmpdir):
    repo = mercurial.hg.repository(mercurial.ui.ui(), str(tmpdir), create=True)
    app = webtest.TestApp(scm_app.HgWeb(repo))

    response = app.get('/repo?cmd=invalidcmd', expect_errors=True)

    assert response.status_int == 400


def test_create_hg_wsgi_app_requirement_error(tmpdir):
    repo = mercurial.hg.repository(mercurial.ui.ui(), str(tmpdir), create=True)
    config = (
        ('paths', 'default', ''),
    )
    with mock.patch('vcsserver.scm_app.HgWeb') as hgweb_mock:
        hgweb_mock.side_effect = mercurial.error.RequirementError()
        with pytest.raises(Exception):
            scm_app.create_hg_wsgi_app(str(tmpdir), repo, config)


def test_git_returns_not_found(tmpdir):
    app = webtest.TestApp(
        scm_app.GitHandler(str(tmpdir), 'repo_name', 'git', False, {}))

    response = app.get('/repo_name/inforefs?service=git-upload-pack',
                       expect_errors=True)

    assert response.status_int == 404


def test_git(tmpdir):
    for dir_name in ('config', 'head', 'info', 'objects', 'refs'):
        tmpdir.mkdir(dir_name)

    app = webtest.TestApp(
        scm_app.GitHandler(str(tmpdir), 'repo_name', 'git', False, {}))

    # We set service to git-upload-packs to trigger a 403
    response = app.get('/repo_name/inforefs?service=git-upload-packs',
                       expect_errors=True)

    assert response.status_int == 403


def test_git_fallbacks_to_git_folder(tmpdir):
    tmpdir.mkdir('.git')
    for dir_name in ('config', 'head', 'info', 'objects', 'refs'):
        tmpdir.mkdir(os.path.join('.git', dir_name))

    app = webtest.TestApp(
        scm_app.GitHandler(str(tmpdir), 'repo_name', 'git', False, {}))

    # We set service to git-upload-packs to trigger a 403
    response = app.get('/repo_name/inforefs?service=git-upload-packs',
                       expect_errors=True)

    assert response.status_int == 403
