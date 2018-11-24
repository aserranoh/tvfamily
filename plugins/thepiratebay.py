
'''thepiratebay.py - API to the site ThePirateBay.

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

import html.parser
import re
import tornado.gen
import tornado.httpclient
import urllib.parse

import tvfamily.torrent

__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'
__homepage__ = 'https://github.com/aserranoh/tvfamily'


_TPB_CATEGORIES = {
    # TV Shows: 205, HD TV Shows: 208
    'TV Series': [205, 208],
    # Movies: 201, Movies DVDR: 202, HD Movies: 207
    'Movies': [201, 207],
}
_RE_SIZE = re.compile(r'Size ([\d.]+.*?[MG]iB)')
_HTTP_HEADERS = {'Accept-Language': 'en-US'}


class TorrentsListParser(html.parser.HTMLParser):
    '''Parse the TPB page that contains the top 100 torrents.'''

    def __init__(self):
        super(TorrentsListParser, self).__init__()
        # True if we are inside a <td> element
        self._in_column = False
        # True if we are in the <a> element that contains the title of the
        # torrent
        self._in_title = False
        # True if we are in the <font> element that contains the description
        self._in_description = False
        # Temporary holds the title of the torrent
        self._title = None
        # Resulting list of torrents
        self.torrents = []

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            # New row of the table that contains the torrents. Reset the column
            # counter to 0.
            self._column = 0
        elif tag == 'td':
            # A cell in the table. Signal that we are in a <td> element.
            self._in_column = True
        elif tag == 'a' and self._in_column and self._column == 1:
            # We are in the second column. The <a> element can contain the
            # title of the torrent or its magnet link (not always present).
            # Reset the magnet link to None in case is not present.
            self._magnet = None
            for a in attrs:
                if a == ('class', 'detLink'):
                    # This class of <a> element denotes the title. Signal that
                    # we are in the title (the actual title is in the data).
                    self._in_title = True
                elif a[0] == 'href' and a[1].startswith('magnet:'):
                    # If the href of this <a> element starts with 'magnet'
                    # it denotes the magnet link.
                    self._magnet = a[1]
        elif tag == 'font' and self._in_column and self._column == 1:
            for a in attrs:
                if a == ('class', 'detDesc'):
                    # We are in the description
                    self._in_description = True
                    self._size = None
                    break

    def handle_data(self, data):
        if self._in_title:
            self._title = data
        elif self._in_description and self._size is None:
            # Don't update the description if it has already been filled
            m = _RE_SIZE.search(data)
            if m is not None:
                self._size = m.group(1)
        elif self._in_column:
            # Columns 2 and 3 simply has the number of seeders and leechers
            # in its data field.
            if self._column == 2:
                self._seeders = int(data)
            elif self._column == 3:
                self._leechers = int(data)

    def handle_endtag(self, tag):
        if tag == 'tr':
            # If a title was found, add a new torrent to the resulting list.
            if self._title is not None:
                self.torrents.append(tvfamily.torrent.Torrent(self._title,
                    self._magnet, self._size, self._seeders, self._leechers))
            # Reset the state variables when the row is finished.
            self._title = None
            self._size = None
            self._column = 0
        elif tag == 'td':
            # When a column is finished, signal it in the in_column state
            # variable and increment the column counter.
            self._in_column = False
            self._column += 1
        elif tag == 'a':
            self._in_title = False
        elif tag == 'font':
            self._in_description = False


@tornado.gen.coroutine
def top(category, options):
    '''Search ThePirateBay site for the top videos.'''
    http_client = tornado.httpclient.AsyncHTTPClient()
    torrents = []
    urls = ['{}/top/{}'.format(options['plugins']['thepiratebay']['url'], c)
        for c in _TPB_CATEGORIES[category]]
    contents = yield [http_client.fetch(url, headers=_HTTP_HEADERS)
        for url in urls]
    # Parse the important information
    for c in contents:
        parser = TorrentsListParser()
        parser.feed(c.body.decode('utf-8'))
        torrents.extend(parser.torrents)
    return torrents

@tornado.gen.coroutine
def search(title, options):
    '''Search ThePirateBay for a given title.'''
    http_client = tornado.httpclient.AsyncHTTPClient()
    query_params = {'q': title, 'video': 'on', 'page': '0', 'orderby': '99'}
    url = '{}/s/?{}'.format(options['plugins']['thepiratebay']['url'],
        urllib.parse.urlencode(query_params))
    contents = yield http_client.fetch(url, headers=_HTTP_HEADERS)
    # Parse the important information
    parser = TorrentsListParser()
    parser.feed(contents.body.decode('utf-8'))
    return parser.torrents

