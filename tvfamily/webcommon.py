
'''webcommon.py - Common web components.

Copyright 2018 Antonio Serrano Hernandez

This file is part of tvfamily.

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

import json
import tornado.web

__script__ = 'tvfamily'
__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'
__homepage__ = 'https://github.com/aserranoh/tvfamily'


class BaseHandler(tornado.web.RequestHandler):
    '''Base class to iplement a http request handler.'''

    def initialize(self, core=None):
        '''Pass the core of the application to the handlers.

        Parameters:
          * core: the core of the tvfamily application.
        '''
        self._core = core

    def write_json(self, **kwargs):
        '''Send json data.'''
        self.set_header('Content-Type', 'application/json')
        if 'code' not in kwargs:
            kwargs['code'] = 0
        self.write(json.dumps(kwargs))

    def write_error(self, code=1, msg=''):
        '''Write an error code and an error message.'''
        self.write_json(code=code, error=msg)

