
'''httpserver.py - Implements a generic Web Server.

Copyright 2018 Antonio Serrano Hernandez

tvfamily is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

tvfamily is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with tvfamily; see the file COPYING.  If not, see
<http://www.gnu.org/licenses/>.
'''

import argparse
import json
import os
import random
import signal
import sys

import tornado.httpclient

__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'


DEFAULT_CONFIG_FILE = os.path.join('/etc', os.path.basename(sys.argv[0]))
SECRET_BITS = 128

# Select libcurl implementation for HTTP requests
tornado.httpclient.AsyncHTTPClient.configure(
    "tornado.curl_httpclient.CurlAsyncHTTPClient")

class HTTPServerError(Exception): pass


class HTTPServer(object):
    '''A generic HTTPServer.'''

    def __init__(self, name, description, version=None, epilog=None,
            settings={}):
        '''kwargs may contain description, epilog and version.'''
        # Parse the command line options
        kwargs = {'prog': name, 'description': description}
        if epilog is not None:
            kwargs['epilog'] = epilog
        self._command_line_options(version, **kwargs)
        # Load the configuration file
        try:
            with open(self.config_file, 'r') as f:
                self.options = json.loads(f.read())
        except OSError:
            msg = 'cannot load options file'
            print('error:', msg, file=sys.stderr)
            raise HTTPServerError(msg)
        # Instantiate the application
        settings['cookie_secret'] = '{:x}'.format(
            random.getrandbits(SECRET_BITS))
        self._app = tornado.web.Application(**settings)
        # Handle signals
        def signal_handler(signum, frame):
            tornado.ioloop.IOLoop.current().stop()
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _command_line_options(self, version=None, **kwargs):
        '''Process the command line options. kwargs may contain prog, epilog
        and description arguments for the argparse constructor.
        '''
        parser = argparse.ArgumentParser(**kwargs,
            formatter_class=argparse.RawTextHelpFormatter)
        if version is not None:
            parser.add_argument('--version', action='version', version=version)
        parser.add_argument('-c', '--config', default=DEFAULT_CONFIG_FILE,
            help='configuration file')
        parser.add_argument('-d', '--daemonize', action='store_true',
            help='daemonize this server')
        args = parser.parse_args()
        self.config_file = args.config
        self.daemonize = args.daemonize

    def add_handlers(self, handlers):
        '''Add the handlers for the sites.'''
        self._app.add_handlers(r'.*', handlers)

    def run(self):
        '''Run the HTTP server and start processing requests.'''
        self._app.listen(self.options['server']['port'])
        tornado.ioloop.IOLoop.current().start()

