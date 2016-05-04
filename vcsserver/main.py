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

import atexit
import locale
import logging
import optparse
import os
import textwrap
import threading
import sys

import configobj
import Pyro4
from beaker.cache import CacheManager
from beaker.util import parse_cache_config_options

try:
    from vcsserver.git import GitFactory, GitRemote
except ImportError:
    GitFactory = None
    GitRemote = None
try:
    from vcsserver.hg import MercurialFactory, HgRemote
except ImportError:
    MercurialFactory = None
    HgRemote = None
try:
    from vcsserver.svn import SubversionFactory, SvnRemote
except ImportError:
    SubversionFactory = None
    SvnRemote = None

from server import VcsServer
from vcsserver import hgpatches, remote_wsgi, settings
from vcsserver.echo_stub import remote_wsgi as remote_wsgi_stub

log = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
SERVER_RUNNING_FILE = None


# HOOKS - inspired by gunicorn #

def when_ready(server):
    """
    Called just after the server is started.
    """

    def _remove_server_running_file():
        if os.path.isfile(SERVER_RUNNING_FILE):
            os.remove(SERVER_RUNNING_FILE)

    # top up to match to level location
    if SERVER_RUNNING_FILE:
        with open(SERVER_RUNNING_FILE, 'wb') as f:
            f.write(str(os.getpid()))
        # register cleanup of that file when server exits
        atexit.register(_remove_server_running_file)


class LazyWriter(object):
    """
    File-like object that opens a file lazily when it is first written
    to.
    """

    def __init__(self, filename, mode='w'):
        self.filename = filename
        self.fileobj = None
        self.lock = threading.Lock()
        self.mode = mode

    def open(self):
        if self.fileobj is None:
            with self.lock:
                self.fileobj = open(self.filename, self.mode)
        return self.fileobj

    def close(self):
        fileobj = self.fileobj
        if fileobj is not None:
            fileobj.close()

    def __del__(self):
        self.close()

    def write(self, text):
        fileobj = self.open()
        fileobj.write(text)
        fileobj.flush()

    def writelines(self, text):
        fileobj = self.open()
        fileobj.writelines(text)
        fileobj.flush()

    def flush(self):
        self.open().flush()


class Application(object):
    """
    Represents the vcs server application.

    This object is responsible to initialize the application and all needed
    libraries. After that it hooks together the different objects and provides
    them a way to access things like configuration.
    """

    def __init__(
            self, host, port=None, locale='', threadpool_size=None,
            timeout=None, cache_config=None, remote_wsgi_=None):

        self.host = host
        self.port = int(port) or settings.PYRO_PORT
        self.threadpool_size = (
            int(threadpool_size) if threadpool_size else None)
        self.locale = locale
        self.timeout = timeout
        self.cache_config = cache_config
        self.remote_wsgi = remote_wsgi_ or remote_wsgi

    def init(self):
        """
        Configure and hook together all relevant objects.
        """
        self._configure_locale()
        self._configure_pyro()
        self._initialize_cache()
        self._create_daemon_and_remote_objects(host=self.host, port=self.port)

    def run(self):
        """
        Start the main loop of the application.
        """

        if hasattr(os, 'getpid'):
            log.info('Starting %s in PID %i.', __name__, os.getpid())
        else:
            log.info('Starting %s.', __name__)
        if SERVER_RUNNING_FILE:
            log.info('PID file written as %s', SERVER_RUNNING_FILE)
        else:
            log.info('No PID file written by default.')
        when_ready(self)
        try:
            self._pyrodaemon.requestLoop(
                loopCondition=lambda: not self._vcsserver._shutdown)
        finally:
            self._pyrodaemon.shutdown()

    def _configure_locale(self):
        if self.locale:
            log.info('Settings locale: `LC_ALL` to %s' % self.locale)
        else:
            log.info(
                'Configuring locale subsystem based on environment variables')

        try:
            # If self.locale is the empty string, then the locale
            # module will use the environment variables. See the
            # documentation of the package `locale`.
            locale.setlocale(locale.LC_ALL, self.locale)

            language_code, encoding = locale.getlocale()
            log.info(
                'Locale set to language code "%s" with encoding "%s".',
                language_code, encoding)
        except locale.Error:
            log.exception(
                'Cannot set locale, not configuring the locale system')

    def _configure_pyro(self):
        if self.threadpool_size is not None:
            log.info("Threadpool size set to %s", self.threadpool_size)
            Pyro4.config.THREADPOOL_SIZE = self.threadpool_size
        if self.timeout not in (None, 0, 0.0, '0'):
            log.info("Timeout for RPC calls set to %s seconds", self.timeout)
            Pyro4.config.COMMTIMEOUT = float(self.timeout)
        Pyro4.config.SERIALIZER = 'pickle'
        Pyro4.config.SERIALIZERS_ACCEPTED.add('pickle')
        Pyro4.config.SOCK_REUSE = True
        # Uncomment the next line when you need to debug remote errors
        # Pyro4.config.DETAILED_TRACEBACK = True

    def _initialize_cache(self):
        cache_config = parse_cache_config_options(self.cache_config)
        log.info('Initializing beaker cache: %s' % cache_config)
        self.cache = CacheManager(**cache_config)

    def _create_daemon_and_remote_objects(self, host='localhost',
                                          port=settings.PYRO_PORT):
        daemon = Pyro4.Daemon(host=host, port=port)

        self._vcsserver = VcsServer()
        uri = daemon.register(
            self._vcsserver, objectId=settings.PYRO_VCSSERVER)
        log.info("Object registered = %s", uri)

        if GitFactory and GitRemote:
            git_repo_cache = self.cache.get_cache_region('git', region='repo_object')
            git_factory = GitFactory(git_repo_cache)
            self._git_remote = GitRemote(git_factory)
            uri = daemon.register(self._git_remote, objectId=settings.PYRO_GIT)
            log.info("Object registered = %s", uri)
        else:
            log.info("Git client import failed")

        if MercurialFactory and HgRemote:
            hg_repo_cache = self.cache.get_cache_region('hg', region='repo_object')
            hg_factory = MercurialFactory(hg_repo_cache)
            self._hg_remote = HgRemote(hg_factory)
            uri = daemon.register(self._hg_remote, objectId=settings.PYRO_HG)
            log.info("Object registered = %s", uri)
        else:
            log.info("Mercurial client import failed")

        if SubversionFactory and SvnRemote:
            svn_repo_cache = self.cache.get_cache_region('svn', region='repo_object')
            svn_factory = SubversionFactory(svn_repo_cache)
            self._svn_remote = SvnRemote(svn_factory, hg_factory=hg_factory)
            uri = daemon.register(self._svn_remote, objectId=settings.PYRO_SVN)
            log.info("Object registered = %s", uri)
        else:
            log.info("Subversion client import failed")

        self._git_remote_wsgi = self.remote_wsgi.GitRemoteWsgi()
        uri = daemon.register(self._git_remote_wsgi,
                              objectId=settings.PYRO_GIT_REMOTE_WSGI)
        log.info("Object registered = %s", uri)

        self._hg_remote_wsgi = self.remote_wsgi.HgRemoteWsgi()
        uri = daemon.register(self._hg_remote_wsgi,
                              objectId=settings.PYRO_HG_REMOTE_WSGI)
        log.info("Object registered = %s", uri)

        self._pyrodaemon = daemon


class VcsServerCommand(object):

    usage = '%prog'
    description = """
    Runs the VCS server
    """
    default_verbosity = 1

    parser = optparse.OptionParser(
        usage,
        description=textwrap.dedent(description)
    )
    parser.add_option(
        '--host',
        type="str",
        dest="host",
    )
    parser.add_option(
        '--port',
        type="int",
        dest="port"
    )
    parser.add_option(
        '--running-file',
        dest='running_file',
        metavar='RUNNING_FILE',
        help="Create a running file after the server is initalized with "
             "stored PID of process"
    )
    parser.add_option(
        '--locale',
        dest='locale',
        help="Allows to set the locale, e.g. en_US.UTF-8",
        default=""
    )
    parser.add_option(
        '--log-file',
        dest='log_file',
        metavar='LOG_FILE',
        help="Save output to the given log file (redirects stdout)"
    )
    parser.add_option(
        '--log-level',
        dest="log_level",
        metavar="LOG_LEVEL",
        help="use LOG_LEVEL to set log level "
             "(debug,info,warning,error,critical)"
    )
    parser.add_option(
        '--threadpool',
        dest='threadpool_size',
        type='int',
        help="Set the size of the threadpool used to communicate with the "
             "WSGI workers. This should be at least 6 times the number of "
             "WSGI worker processes."
        )
    parser.add_option(
        '--timeout',
        dest='timeout',
        type='float',
        help="Set the timeout for RPC communication in seconds."
        )
    parser.add_option(
        '--config',
        dest='config_file',
        type='string',
        help="Configuration file for vcsserver."
        )

    def __init__(self, argv, quiet=False):
        self.options, self.args = self.parser.parse_args(argv[1:])
        if quiet:
            self.options.verbose = 0

    def _get_file_config(self):
        ini_conf = {}
        conf = configobj.ConfigObj(self.options.config_file)
        if 'DEFAULT' in conf:
            ini_conf = conf['DEFAULT']

        return ini_conf

    def _show_config(self, vcsserver_config):
        order = [
            'config_file',
            'host',
            'port',
            'log_file',
            'log_level',
            'locale',
            'threadpool_size',
            'timeout',
            'cache_config',
        ]

        def sorter(k):
            return dict([(y, x) for x, y in enumerate(order)]).get(k)

        _config = []
        for k in sorted(vcsserver_config.keys(), key=sorter):
            v = vcsserver_config[k]
            # construct padded key for display eg %-20s % = key:   val
            k_formatted = ('%-'+str(len(max(order, key=len))+1)+'s') % (k+':')
            _config.append('    * %s %s' % (k_formatted, v))
        log.info('\n[vcsserver configuration]:\n'+'\n'.join(_config))

    def _get_vcsserver_configuration(self):
        _defaults = {
            'config_file': None,
            'git_path': 'git',
            'host': 'localhost',
            'port': settings.PYRO_PORT,
            'log_file': None,
            'log_level': 'debug',
            'locale': None,
            'threadpool_size': 16,
            'timeout': None,

            # Development support
            'dev.use_echo_app': False,

            # caches, baker style config
            'beaker.cache.regions': 'repo_object',
            'beaker.cache.repo_object.expire': '10',
            'beaker.cache.repo_object.type': 'memory',
        }
        config = {}
        config.update(_defaults)
        # overwrite defaults with one loaded from file
        config.update(self._get_file_config())

        # overwrite with self.option which has the top priority
        for k, v in self.options.__dict__.items():
            if v or v == 0:
                config[k] = v

        # clear all "extra" keys if they are somehow passed,
        # we only want defaults, so any extra stuff from self.options is cleared
        # except beaker stuff which needs to be dynamic
        for k in [k for k in config.copy().keys() if not k.startswith('beaker.cache.')]:
            if k not in _defaults:
                del config[k]

        # group together the cache into one key.
        # Needed further for beaker lib configuration
        _k = {}
        for k in [k for k in config.copy() if k.startswith('beaker.cache.')]:
            _k[k] = config.pop(k)
        config['cache_config'] = _k

        return config

    def out(self, msg):  # pragma: no cover
        if self.options.verbose > 0:
            print(msg)

    def run(self):  # pragma: no cover
        vcsserver_config = self._get_vcsserver_configuration()

        # Ensure the log file is writeable
        if vcsserver_config['log_file']:
            stdout_log = self._configure_logfile()
        else:
            stdout_log = None

        # set PID file with running lock
        if self.options.running_file:
            global SERVER_RUNNING_FILE
            SERVER_RUNNING_FILE = self.options.running_file

        # configure logging, and logging based on configuration file
        self._configure_logging(level=vcsserver_config['log_level'],
                                stream=stdout_log)
        if self.options.config_file:
            if not os.path.isfile(self.options.config_file):
                raise OSError('File %s does not exist' %
                              self.options.config_file)

            self._configure_file_logging(self.options.config_file)

        self._configure_settings(vcsserver_config)

        # display current configuration of vcsserver
        self._show_config(vcsserver_config)

        if not vcsserver_config['dev.use_echo_app']:
            remote_wsgi_mod = remote_wsgi
        else:
            log.warning("Using EchoApp for VCS endpoints.")
            remote_wsgi_mod = remote_wsgi_stub

        app = Application(
            host=vcsserver_config['host'],
            port=vcsserver_config['port'],
            locale=vcsserver_config['locale'],
            threadpool_size=vcsserver_config['threadpool_size'],
            timeout=vcsserver_config['timeout'],
            cache_config=vcsserver_config['cache_config'],
            remote_wsgi_=remote_wsgi_mod)
        app.init()
        app.run()

    def _configure_logging(self, level, stream=None):
        _format = (
            '%(asctime)s.%(msecs)03d %(levelname)-5.5s [%(name)s] %(message)s')
        levels = {
            'debug': logging.DEBUG,
            'info': logging.INFO,
            'warning': logging.WARNING,
            'error': logging.ERROR,
            'critical': logging.CRITICAL,
            }
        try:
            level = levels[level]
        except KeyError:
            raise AttributeError(
                'Invalid log level please use one of %s' % (levels.keys(),))
        logging.basicConfig(format=_format, stream=stream, level=level)
        logging.getLogger('Pyro4').setLevel(level)

    def _configure_file_logging(self, config):
        import logging.config
        try:
            logging.config.fileConfig(config)
        except Exception as e:
            log.warning('Failed to configure logging based on given '
                        'config file. Error: %s' % e)

    def _configure_logfile(self):
        try:
            writeable_log_file = open(self.options.log_file, 'a')
        except IOError as ioe:
            msg = 'Error: Unable to write to log file: %s' % ioe
            raise ValueError(msg)
        writeable_log_file.close()
        stdout_log = LazyWriter(self.options.log_file, 'a')
        sys.stdout = stdout_log
        sys.stderr = stdout_log
        return stdout_log

    def _configure_settings(self, config):
        """
        Configure the settings module based on the given `config`.
        """
        settings.GIT_EXECUTABLE = config['git_path']


def main(argv=sys.argv, quiet=False):
    if MercurialFactory:
        hgpatches.patch_largefiles_capabilities()
    command = VcsServerCommand(argv, quiet=quiet)
    return command.run()
