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
import shutil
import tempfile

import configobj


class TestINI(object):
    """
    Allows to create a new test.ini file as a copy of existing one with edited
    data. If existing file is not present, it creates a new one. Example usage::

        with TestINI('test.ini', [{'section': {'key': 'val'}}]) as new_test_ini_path:
            print 'vcsserver --config=%s' % new_test_ini
    """

    def __init__(self, ini_file_path, ini_params, new_file_prefix=None,
                 destroy=True):
        self.ini_file_path = ini_file_path
        self.ini_params = ini_params
        self.new_path = None
        self.new_path_prefix = new_file_prefix or 'test'
        self.destroy = destroy

    def __enter__(self):
        _, pref = tempfile.mkstemp()
        loc = tempfile.gettempdir()
        self.new_path = os.path.join(loc, '{}_{}_{}'.format(
            pref, self.new_path_prefix, self.ini_file_path))

        # copy ini file and modify according to the params, if we re-use a file
        if os.path.isfile(self.ini_file_path):
            shutil.copy(self.ini_file_path, self.new_path)
        else:
            # create new dump file for configObj to write to.
            with open(self.new_path, 'wb'):
                pass

        config = configobj.ConfigObj(
            self.new_path, file_error=True, write_empty_values=True)

        for data in self.ini_params:
            section, ini_params = data.items()[0]
            key, val = ini_params.items()[0]
            if section not in config:
                config[section] = {}
            config[section][key] = val

        config.write()
        return self.new_path

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.destroy:
            os.remove(self.new_path)
