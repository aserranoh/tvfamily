
'''torrent.py - Common Torrent objects.

Copyright 2018 2019 Antonio Serrano Hernandez

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

import tvfamily.PTN

__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 2019 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'
__homepage__ = 'https://github.com/aserranoh/tvfamily'


class Torrent(object):
    '''Represents a torrent object.'''

    def __init__(self, name, magnet=None, size=0, seeders=0, leechers=0):
        self.name = name
        self.magnet = magnet
        self.size = size
        self.seeders = seeders
        self.leechers = leechers
        self.name_info = tvfamily.PTN.parse(self.name)

    def todict(self):
        '''Return a dictionary with the elements of this instance.'''
        return {'name': self.name, 'magnet': self.magnet, 'size': self.size,
            'seeders': self.seeders, 'leechers': self.leechers}

