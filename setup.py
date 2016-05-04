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

from setuptools import setup, find_packages
from setuptools.command.test import test as TestCommand
from codecs import open
from os import path
import pkgutil
import sys


here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.rst'), encoding='utf-8') as f:
    long_description = f.read()


def get_version():
    version = pkgutil.get_data('vcsserver', 'VERSION')
    return version.strip()


class PyTest(TestCommand):
    user_options = [('pytest-args=', 'a', "Arguments to pass to py.test")]

    def initialize_options(self):
        TestCommand.initialize_options(self)
        self.pytest_args = []

    def finalize_options(self):
        TestCommand.finalize_options(self)
        self.test_args = []
        self.test_suite = True

    def run_tests(self):
        # import here, cause outside the eggs aren't loaded
        import pytest
        errno = pytest.main(self.pytest_args)
        sys.exit(errno)


setup(
    name='rhodecode-vcsserver',
    version=get_version(),
    description='Version Control System Server',
    long_description=long_description,
    url='http://www.rhodecode.com',
    author='RhodeCode GmbH',
    author_email='marcin@rhodecode.com',
    cmdclass={'test': PyTest},
    license='GPLv3',
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Version Control',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        'Programming Language :: Python :: 2.7',
    ],
    packages=find_packages(),
    tests_require=[
        'mock',
        'pytest',
        'WebTest',
    ],
    install_requires=[
        'configobj',
        'dulwich',
        'hgsubversion',
        'infrae.cache',
        'mercurial',
        'msgpack-python',
        'pyramid',
        'Pyro4',
        'simplejson',
        'subprocess32',
        'waitress',
        'WebOb',
    ],
    package_data={
        'vcsserver': ['VERSION'],
    },
    entry_points={
        'console_scripts': [
            'vcsserver=vcsserver.main:main',
        ],
        'paste.app_factory': ['main=vcsserver.http_main:main']
    },
)
