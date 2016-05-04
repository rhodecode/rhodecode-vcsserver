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

import socket

import pytest


def pytest_addoption(parser):
    parser.addoption(
        '--repeat', type=int, default=100,
        help="Number of repetitions in performance tests.")


@pytest.fixture(scope='session')
def repeat(request):
    """
    The number of repetitions is based on this fixture.

    Slower calls may divide it by 10 or 100. It is chosen in a way so that the
    tests are not too slow in our default test suite.
    """
    return request.config.getoption('--repeat')


@pytest.fixture(scope='session')
def vcsserver_port(request):
    port = get_available_port()
    print 'Using vcsserver port %s' % (port, )
    return port


def get_available_port():
    family = socket.AF_INET
    socktype = socket.SOCK_STREAM
    host = '127.0.0.1'

    mysocket = socket.socket(family, socktype)
    mysocket.bind((host, 0))
    port = mysocket.getsockname()[1]
    mysocket.close()
    del mysocket
    return port
