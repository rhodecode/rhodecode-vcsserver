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

import io
import os
import sys

import pytest

from vcsserver import subprocessio


@pytest.fixture(scope='module')
def environ():
    """Delete coverage variables, as they make the tests fail."""
    env = dict(os.environ)
    for key in env.keys():
        if key.startswith('COV_CORE_'):
            del env[key]

    return env


def _get_python_args(script):
    return [sys.executable, '-c',
            'import sys; import time; import shutil; ' + script]


def test_raise_exception_on_non_zero_return_code(environ):
    args = _get_python_args('sys.exit(1)')
    with pytest.raises(EnvironmentError):
        list(subprocessio.SubprocessIOChunker(args, shell=False, env=environ))


def test_does_not_fail_on_non_zero_return_code(environ):
    args = _get_python_args('sys.exit(1)')
    output = ''.join(subprocessio.SubprocessIOChunker(
        args, shell=False, fail_on_return_code=False, env=environ))

    assert output == ''


def test_raise_exception_on_stderr(environ):
    args = _get_python_args('sys.stderr.write("X"); time.sleep(1);')
    with pytest.raises(EnvironmentError) as excinfo:
        list(subprocessio.SubprocessIOChunker(args, shell=False, env=environ))

    assert 'exited due to an error:\nX' in str(excinfo.value)


def test_does_not_fail_on_stderr(environ):
    args = _get_python_args('sys.stderr.write("X"); time.sleep(1);')
    output = ''.join(subprocessio.SubprocessIOChunker(
        args, shell=False, fail_on_stderr=False, env=environ))

    assert output == ''


@pytest.mark.parametrize('size', [1, 10**5])
def test_output_with_no_input(size, environ):
    print type(environ)
    data = 'X'
    args = _get_python_args('sys.stdout.write("%s" * %d)' % (data, size))
    output = ''.join(subprocessio.SubprocessIOChunker(
        args, shell=False, env=environ))

    assert output == data * size


@pytest.mark.parametrize('size', [1, 10**5])
def test_output_with_no_input_does_not_fail(size, environ):
    data = 'X'
    args = _get_python_args(
        'sys.stdout.write("%s" * %d); sys.exit(1)' % (data, size))
    output = ''.join(subprocessio.SubprocessIOChunker(
        args, shell=False, fail_on_return_code=False, env=environ))

    print len(data * size), len(output)
    assert output == data * size


@pytest.mark.parametrize('size', [1, 10**5])
def test_output_with_input(size, environ):
    data = 'X' * size
    inputstream = io.BytesIO(data)
    # This acts like the cat command.
    args = _get_python_args('shutil.copyfileobj(sys.stdin, sys.stdout)')
    output = ''.join(subprocessio.SubprocessIOChunker(
        args, shell=False, inputstream=inputstream, env=environ))

    print len(data), len(output)
    assert output == data


@pytest.mark.parametrize('size', [1, 10**5])
def test_output_with_input_skipping_iterator(size, environ):
    data = 'X' * size
    inputstream = io.BytesIO(data)
    # This acts like the cat command.
    args = _get_python_args('shutil.copyfileobj(sys.stdin, sys.stdout)')

    # Note: assigning the chunker makes sure that it is not deleted too early
    chunker = subprocessio.SubprocessIOChunker(
        args, shell=False, inputstream=inputstream, env=environ)
    output = ''.join(chunker.output)

    print len(data), len(output)
    assert output == data
