
'''imdb.py - Obtains movies information from the site www.imdb.com.

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

from html.parser import HTMLParser
import re
from tornado import gen
from tornado.httpclient import AsyncHTTPClient
import urllib.parse

__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'
__homepage__ = 'https://github.com/aserranoh/tvfamily'


_IMDB_SEARCH_TITLE = 'https://www.imdb.com/search/title'
_RE_YEAR = re.compile(r'\((?P<air_year>\d{4})(–(?P<end_year>\d{4}|\s*))?\)')

class IMDBSearchResult(object):
    '''Represents a search result.

    Constructor parameters:
      * title: the title's title.
      * air_year: the title's air year.
      * end_year: the title's end year (in case of a tv series).
      * id: the IMDB title's identifier.
    '''

    def __init__(self, title, air_year, end_year, id):
        self.title = title
        self.air_year = air_year
        self.end_year = end_year
        self.id = id


class SearchResultParser(HTMLParser):
    '''Parse the IMDB search result page.'''

    def __init__(self):
        super(SearchResultParser, self).__init__()
        self._in_span_header = False
        self._in_span_index = False
        self._in_span_title = False
        self._in_span_year = False
        self._in_a = False
        self.results = []

    def handle_starttag(self, tag, attrs):
        if tag == 'span':
            # Check if it is the span we are looking for
            for a in attrs:
                if a == ('class', 'lister-item-header'):
                    # inside title of search result
                    self._in_span_header = True
                    break
                elif a[0] == 'class' and a[1].startswith('lister-item-index'):
                    # Inside index
                    self._in_span_index = True
                    break
                elif a[0] == 'title':
                    # Inside title
                    self._in_span_title = True
                    break
                elif a[0] == 'class' and a[1].startswith('lister-item-year'):
                    # Inside year
                    self._in_span_year = True
                    break
        elif self._in_span_title and tag == 'a':
            self._in_a = True
            # Get the id from the href attribute
            self._id = attrs[0][1].split('/')[2]

    def handle_data(self, data):
        if self._in_a:
            self._title = data
        elif self._in_span_year:
            m = _RE_YEAR.search(data)
            self._air_year = int(m.group('air_year'))
            end_year = m.group('end_year')
            if end_year is not None:
                if end_year.strip() != '':
                    end_year = int(end_year)
                else:
                    end_year = 0
            self._end_year = end_year

    def handle_endtag(self, tag):
        if tag == 'span':
            if self._in_span_index:
                self._in_span_index = False
            elif self._in_span_year:
                self._in_span_year = False
            elif self._in_span_title:
                self._in_span_title = False
            elif self._in_span_header:
                self._in_span_header = False
                # Add the found result
                self.results.append(IMDBSearchResult(
                    self._title, self._air_year, self._end_year, self._id))
        elif tag == 'a':
            self._in_a = False


@gen.coroutine
def search(title, title_type='tv_series'):
    '''Search by title in the IMDB site.
    title_type might be: 'feature' or 'tv_series'.
    '''
    http_client = AsyncHTTPClient()
    # Fetch the list of titles
    search_attributes = {
        'title': title,
        'title_type': title_type,
        'view': 'simple',
    }
    url = '{}?{}'.format(_IMDB_SEARCH_TITLE, urllib.parse.urlencode(
        search_attributes))
    response = yield http_client.fetch(
        url, headers={'Accept-Language': 'en-US'})
    # Parse the important information
    parser = SearchResultParser()
    parser.feed(response.body.decode('utf-8'))
    return parser.results

