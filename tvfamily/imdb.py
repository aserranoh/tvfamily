
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
import json
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
_IMDB_TITLE = 'https://www.imdb.com/title/{}'
_IMDB_SEASON = (
    'https://www.imdb.com/title/{}/episodes?season={}&ref_=tt_ov_epl')
_RE_YEARS = re.compile(
    r'\(.*?(?P<air_year>\d{4})(–(?P<end_year>\d{4}|\s*))?\)$')


def _get_years(data):
    '''Return the air and end year of a tv series.'''
    m = _RE_YEARS.search(data)
    if m:
        air_year = int(m.group('air_year'))
        end_year = m.group('end_year')
        if end_year is not None:
            if end_year.strip() != '':
                end_year = int(end_year)
            else:
                end_year = 0
        return air_year, end_year
    else:
        raise ValueError()


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
            try:
                self._air_year, self._end_year = _get_years(data)
            except ValueError:
                pass

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
                self.results.append({
                    'title': self._title,
                    'air_year': self._air_year,
                    'end_year': self._end_year,
                    'imdb_id': self._id
                })
        elif tag == 'a':
            self._in_a = False


class TitleParser(HTMLParser):
    '''Parse the IMDB title page.'''

    def __init__(self):
        super(TitleParser, self).__init__()
        self.attrs = {}
        self._in_bd = False
        self._in_poster = True

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            for a in attrs:
                if a == ('type', 'application/ld+json'):
                    self._in_bd = True
        elif tag == 'meta':
            in_title = False
            if attrs[0] == ('property', 'og:title'):
                self.attrs['air_year'], self.attrs['end_year'] = _get_years(
                    attrs[1][1])
        elif tag == 'div':
            for a in attrs:
                if a == ('class', 'poster'):
                    self._in_poster = True
        elif tag == 'img' and self._in_poster:
            for a in attrs:
                if a[0] == 'src':
                    self.attrs['poster_url'] = a[1]

    def handle_data(self, data):
        if self._in_bd:
            bd = json.loads(data)
            self.attrs['plot'] = bd['description']
            self.attrs['genre'] = bd['genre']
            self.attrs['rating'] = bd['aggregateRating']['ratingValue']

    def handle_endtag(self, tag):
        if tag == 'script':
            self._in_bd = False
        elif tag == 'div':
            self._in_poster = False


class SeasonParser(HTMLParser):
    '''Parse the IMDB page that contains a season's episodes descriptions.'''

    def __init__(self, season):
        super(SeasonParser, self).__init__()
        self.episodes = {}
        self.attrs = {'seasons': {str(season): self.episodes}}
        self._in_airdate = False
        self._in_rating_container = False
        self._in_rating = False
        self._in_plot = False
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            # Check if it is a episode still and get the source of the image
            is_still = False
            for a in attrs:
                if a == ('class', 'zero-z-index'):
                    is_still = True
                elif a[0] == 'src':
                    still = a[1]
            if is_still:
                self.current['still'] = still
        elif tag == 'meta':
            # Check if it is the episode number
            is_episodenumber = False
            for a in attrs:
                if a == ('itemprop', 'episodeNumber'):
                    is_episodenumber = True
                elif a[0] == 'content':
                    episodenumber = a[1]
            if is_episodenumber:
                self.episodes[episodenumber] = self.current
        elif tag == 'div':
            for a in attrs:
                if a == ('class', 'list_item odd') or a == (
                        'class', 'list_item even'):
                    # New episode
                    self.current = {}
                if a == ('class', 'airdate'):
                    self._in_airdate = True
                    break
                elif a == ('class', 'ipl-rating-star '):
                    self._in_rating_container = True
                    break
                elif a == ('class', 'item_description'):
                    self._in_plot = True
                    break
        elif tag == 'span' and self._in_rating_container:
            for a in attrs:
                if a == ('class', 'ipl-rating-star__rating'):
                    self._in_rating = True
                    break
        elif tag == 'a':
            for a in attrs:
                if a == ('itemprop', 'name'):
                    self._in_title = True
                    break

    def handle_data(self, data):
        if self._in_airdate:
            self.current['air_date'] = data.strip()
        elif self._in_rating:
            self.current['rating'] = float(data)
        elif self._in_plot:
            self.current['plot'] = data.strip()
        elif self._in_title:
            self.current['title'] = data

    def handle_endtag(self, tag):
        if tag == 'div':
            if self._in_airdate:
                self._in_airdate = False
            elif self._in_rating_container:
                self._in_rating_container = False
            elif self._in_plot:
                self._in_plot = False
        elif tag == 'span' and self._in_rating:
            self._in_rating = False
        elif tag == 'a' and self._in_title:
            self._in_title = False


class IMDBTitle(object):
    '''Represents a title in the IMDB database.

    Constructor parameters:
      * attrs: attributes of this title.
    '''

    def __init__(self, attrs):
        self.attrs = dict((k, v) for k, v in attrs.items())

    @gen.coroutine
    def fetch(self):
        '''Obtain the remaining attributes from the title's main IMDB page.'''
        try:
            # Fetch the title page
            imdb_id = self.attrs['imdb_id']
            url = _IMDB_TITLE.format(imdb_id)
            http_client = AsyncHTTPClient()
            print('fetching', url)
            response = yield http_client.fetch(
                url, headers={'Accept-Language': 'en-US'})
            # Parse the important information
            parser = TitleParser()
            parser.feed(response.body.decode('utf-8'))
            self.attrs.update(parser.attrs)
        except KeyError:
            pass

    @gen.coroutine
    def fetch_season(self, season):
        '''Obtain a given season's episodes descriptions.'''
        try:
            # Fetch the title page
            imdb_id = self.attrs['imdb_id']
            url = _IMDB_SEASON.format(imdb_id, season)
            http_client = AsyncHTTPClient()
            print('fetching', url)
            response = yield http_client.fetch(
                url, headers={'Accept-Language': 'en-US'})
            # Parse the important information
            parser = SeasonParser(season)
            parser.feed(response.body.decode('utf-8'))
            self.attrs.update(parser.attrs)
        except KeyError:
            pass


@gen.coroutine
def search(title, title_type, year=None):
    '''Search by title in the IMDB site.
    title_type might be: 'feature' or 'tv_series'.
    '''
    http_client = AsyncHTTPClient()
    # Fetch the list of titles
    search_attributes = {
        'title': title,
        'title_type': ','.join(title_type),
        'view': 'simple',
    }
    if year is not None:
        search_attributes['release_date'] = '{0},{0}'.format(year)
    url = '{}?{}'.format(_IMDB_SEARCH_TITLE, urllib.parse.urlencode(
        search_attributes))
    print('fetching', url)
    response = yield http_client.fetch(
        url, headers={'Accept-Language': 'en-US'})
    # Parse the important information
    parser = SearchResultParser()
    parser.feed(response.body.decode('utf-8'))
    return [IMDBTitle(a) for a in parser.results]

