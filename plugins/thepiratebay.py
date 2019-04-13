
'''thepiratebay.py - API to the site ThePirateBay.

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

from bs4 import BeautifulSoup
import logging
import random
import re
import tornado.gen
import tornado.httpclient
import urllib.parse

import tvfamily.torrent

__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 2019 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'
__homepage__ = 'https://github.com/aserranoh/tvfamily'


_TPB_CATEGORIES = {
    # TV Shows: 205, HD TV Shows: 208
    'TV Series': [205],
    # Movies: 201, Movies DVDR: 202, HD Movies: 207
    'Movies': [201, 207],
}
_RE_SIZE = re.compile(r'Size ([\d.]+.*?[MG]iB)')
_HTTP_HEADERS = {'Accept-Language': 'en-US'}


class TorrentsListParser():
    '''Parse the TPB page that contains the top 100 torrents.'''

    def parse(self, html_doc):
        torrents = []
        soup = BeautifulSoup(html_doc, 'html.parser')
        main_content = soup.find(name='div', id='main-content')
        for tr in main_content.table.find_all('tr'):
            cols = tr.find_all('td')
            if len(cols) == 4:
                # Title
                a = cols[1].a
                title = str(a.string)
                # Magnet (its actually the link to the media page)
                magnet = a['href']
                # Size of the media
                size = None
                m = _RE_SIZE.search(str(cols[1].find('font').contents[0]))
                if m is not None:
                    size = m.group(1)
                # Seeders and leechers
                seeders = int(cols[2].string)
                leechers = int(cols[3].string)
                # Append the Torrent
                torrents.append(tvfamily.torrent.Torrent(
                    title, magnet, size, seeders, leechers))
        return torrents


class TorrentPageParser():
    '''Parse the TPB page that contains the description of a torrent.'''

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for a in attrs:
                if a[0] == 'href':
                    href = a[1]
                elif a == ('title', 'Get this torrent'):
                    self.magnet = href

    def handle_data(self, data):
        pass

    def handle_endtag(self, tag):
        pass


async def top(category, options):
    '''Search ThePirateBay site for the top videos.'''
    http_client = tornado.httpclient.AsyncHTTPClient()
    server = _get_server(options)
    torrents = []
    urls = ['{}/top/{}'.format(server, c)
        for c in _TPB_CATEGORIES[category]]
    logging.info('fetching top {}...'.format(category))
    contents = await tornado.gen.multi([_request(http_client, url)
        for url in urls])
    logging.info('received top {}'.format(category))
    # Parse the important information
    for c in contents:
        parser = TorrentsListParser()
        torrents.extend(parser.parse(c.body.decode('utf-8')))
    #for t in torrents:
    #    print(t)
    return torrents

def _get_server(options):
    '''Return a server to use.'''
    return random.choice(options['plugins']['thepiratebay']['urls'])

async def _request(http_client, url):
    '''Make a request and control the 429 error.'''
    while 1:
        try:
            result = await http_client.fetch(url, headers=_HTTP_HEADERS)
            break
        except tornado.httpclient.HTTPError as e:
            if e.code != 429:
                raise
            else:
                await tornado.gen.sleep(int(e.response.headers['Retry-After']))
    return result

async def search(query, options):
    '''Search ThePirateBay for a given query.'''
    http_client = tornado.httpclient.AsyncHTTPClient()
    server = _get_server(options)
    query_params = {'q': query, 'video': 'on', 'page': '0', 'orderby': '99'}
    url = '{}/s/?{}'.format(server, urllib.parse.urlencode(query_params))
    logging.info('fetching url {}...'.format(url))
    contents = await _request(http_client, url)
    logging.info('received url {}'.format(url))
    # Parse the important information
    parser = TorrentsListParser()
    parser.feed(contents.body.decode('utf-8'))
    await tornado.gen.multi([_fetch_torrent_info(server, t)
        for t in parser.torrents if not t.magnet.startswith('magnet')])
    return parser.torrents

async def _fetch_torrent_info(server, torrent):
    '''Fetch the torrent info page.'''
    http_client = tornado.httpclient.AsyncHTTPClient()
    url = server + torrent.magnet
    logging.info('fetching url {}...'.format(url))
    contents = await _request(http_client, url)
    logging.info('received url {}'.format(url))
    # Parse the important information
    parser = TorrentPageParser()
    parser.feed(contents.body.decode('utf-8'))
    torrent.magnet = parser.magnet

