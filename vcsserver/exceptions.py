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
Special exception handling over the wire.

Since we cannot assume that our client is able to import our exception classes,
this module provides a "wrapping" mechanism to raise plain exceptions
which contain an extra attribute `_vcs_kind` to allow a client to distinguish
different error conditions.
"""

import functools


def _make_exception(kind, *args):
    """
    Prepares a base `Exception` instance to be sent over the wire.

    To give our caller a hint what this is about, it will attach an attribute
    `_vcs_kind` to the exception.
    """
    exc = Exception(*args)
    exc._vcs_kind = kind
    return exc


AbortException = functools.partial(_make_exception, 'abort')

ArchiveException = functools.partial(_make_exception, 'archive')

LookupException = functools.partial(_make_exception, 'lookup')

VcsException = functools.partial(_make_exception, 'error')

RepositoryLockedException = functools.partial(_make_exception, 'repo_locked')

RequirementException = functools.partial(_make_exception, 'requirement')

UnhandledException = functools.partial(_make_exception, 'unhandled')

URLError = functools.partial(_make_exception, 'url_error')
