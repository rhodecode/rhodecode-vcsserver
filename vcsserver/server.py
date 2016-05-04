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

import gc
import logging
import os
import time


log = logging.getLogger(__name__)


class VcsServer(object):
    """
    Exposed remote interface of the vcsserver itself.

    This object can be used to manage the server remotely. Right now the main
    use case is to allow to shut down the server.
    """

    _shutdown = False

    def shutdown(self):
        self._shutdown = True

    def ping(self):
        """
        Utility to probe a server connection.
        """
        log.debug("Received server ping.")

    def echo(self, data):
        """
        Utility for performance testing.

        Allows to pass in arbitrary data and will return this data.
        """
        log.debug("Received server echo.")
        return data

    def sleep(self, seconds):
        """
        Utility to simulate long running server interaction.
        """
        log.debug("Sleeping %s seconds", seconds)
        time.sleep(seconds)

    def get_pid(self):
        """
        Allows to discover the PID based on a proxy object.
        """
        return os.getpid()

    def run_gc(self):
        """
        Allows to trigger the garbage collector.

        Main intention is to support statistics gathering during test runs.
        """
        freed_objects = gc.collect()
        return {
            'freed_objects': freed_objects,
            'garbage': len(gc.garbage),
        }
