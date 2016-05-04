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

import subprocess
import StringIO
import time

import pytest

from fixture import TestINI


@pytest.mark.parametrize("arguments, expected_texts", [
    (['--threadpool=192'], [
        'threadpool_size: 192',
        'worker pool of size 192 created',
        'Threadpool size set to 192']),
    (['--locale=fake'], [
        'Cannot set locale, not configuring the locale system']),
    (['--timeout=5'], [
        'Timeout for RPC calls set to 5.0 seconds']),
    (['--log-level=info'], [
        'log_level:       info']),
    (['--port={port}'], [
        'port:            {port}',
        'created daemon on localhost:{port}']),
    (['--host=127.0.0.1', '--port={port}'], [
        'port:            {port}',
        'host:            127.0.0.1',
        'created daemon on 127.0.0.1:{port}']),
    (['--config=/bad/file'], ['OSError: File /bad/file does not exist']),
])
def test_vcsserver_calls(arguments, expected_texts, vcsserver_port):
    port_argument = '--port={port}'
    if port_argument not in arguments:
        arguments.append(port_argument)
    arguments = _replace_port(arguments, vcsserver_port)
    expected_texts = _replace_port(expected_texts, vcsserver_port)
    output = call_vcs_server_with_arguments(arguments)
    for text in expected_texts:
        assert text in output


def _replace_port(values, port):
    return [value.format(port=port) for value in values]


def test_vcsserver_with_config(vcsserver_port):
    ini_def = [
        {'DEFAULT': {'host': '127.0.0.1'}},
        {'DEFAULT': {'threadpool_size': '111'}},
        {'DEFAULT': {'port': vcsserver_port}},
    ]

    with TestINI('test.ini', ini_def) as new_test_ini_path:
        output = call_vcs_server_with_arguments(
            ['--config=' + new_test_ini_path])

        expected_texts = [
            'host:            127.0.0.1',
            'Threadpool size set to 111',
        ]
        for text in expected_texts:
            assert text in output


def test_vcsserver_with_config_cli_overwrite(vcsserver_port):
    ini_def = [
        {'DEFAULT': {'host': '127.0.0.1'}},
        {'DEFAULT': {'port': vcsserver_port}},
        {'DEFAULT': {'threadpool_size': '111'}},
        {'DEFAULT': {'timeout': '0'}},
    ]
    with TestINI('test.ini', ini_def) as new_test_ini_path:
        output = call_vcs_server_with_arguments([
            '--config=' + new_test_ini_path,
            '--host=128.0.0.1',
            '--threadpool=256',
            '--timeout=5'])
        expected_texts = [
            'host:            128.0.0.1',
            'Threadpool size set to 256',
            'Timeout for RPC calls set to 5.0 seconds',
        ]
        for text in expected_texts:
            assert text in output


def call_vcs_server_with_arguments(args):
    vcs = subprocess.Popen(
        ["vcsserver"] + args,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    output = read_output_until(
        "Starting vcsserver.main", vcs.stdout)
    vcs.terminate()
    return output


def call_vcs_server_with_non_existing_config_file(args):
    vcs = subprocess.Popen(
        ["vcsserver", "--config=/tmp/bad"] + args,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = read_output_until(
        "Starting vcsserver.main", vcs.stdout)
    vcs.terminate()
    return output


def read_output_until(expected, source, timeout=5):
    ts = time.time()
    buf = StringIO.StringIO()
    while time.time() - ts < timeout:
        line = source.readline()
        buf.write(line)
        if expected in line:
            break
    return buf.getvalue()
