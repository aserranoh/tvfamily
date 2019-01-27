
'''imdb.py - Obtains movies information from the site www.imdb.com.

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

import html.parser
import json
import logging
import re
import tornado.httpclient
import urllib.parse

__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 2019 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'
__homepage__ = 'https://github.com/aserranoh/tvfamily'


_HTTP_HEADERS = {'Accept-Language': 'en-US'}
_IMDB_SEARCH_URL = 'https://www.imdb.com/find'
_IMDB_TITLE_URL = 'https://www.imdb.com/title/{}'
_IMDB_SEASON_URL = (
    'https://www.imdb.com/title/{}/episodes?season={}&ref_=tt_ov_epl')
_RE_SEARCH_YEAR = re.compile(r'\((\d{4})\)')
_SEARCH_TYPES = ['TV Series', 'Short', 'TV Episode', 'Video', 'TV Movie',
    'Video Game', 'TV Mini-Series']
_RE_SEARCH_TYPE = re.compile(r'\(({})\)'.format('|'.join(_SEARCH_TYPES)))
# Add 'Movie' as search type (in IMDB movies don't have explicit type)
_SEARCH_TYPES.append('Movie')
_RE_TITLE = re.compile(r'''
    (?P<title> .*? ) \s+
    \( (?P<type> .*? ) \s*
    (?P<air_year> \d{4} )
    ( – (?P<end_year> \d{4} | \s* ) )?
    \) $
    ''', re.X)
_RE_DURATION = re.compile(r'PT(?P<h>\d+)H(?P<m>\d+)M')
_RE_SEASON = re.compile(r'/title/[^/]+/episodes\?season=(?P<season>\d+)')

def _parse_title(data):
    '''Return the air and end year of a tv series.'''
    air_year = end_year = None
    m = _RE_TITLE.search(data)
    if m:
        title = m.group('title')
        air_year = m.group('air_year')
        if air_year is not None:
            air_year = int(air_year)
        end_year = m.group('end_year')
        if end_year is not None:
            if end_year.strip() != '':
                end_year = int(end_year)
            else:
                end_year = 0
    return title, air_year, end_year


class SearchParser(html.parser.HTMLParser):
    '''Parse the IMDB search result page.

    <table class="findList">
    <tr class="findResult ...">
    <td class="primary_photo">...</td>
    <td class="result_text">
      <a href="/title/IMDB_ID/...">TITLE</a>
      (YEAR) (TYPE)
    </td>
    </tr>
    </table>
    '''

    def __init__(self):
        super(SearchParser, self).__init__()
        # True if we are in the title column
        self._in_title = False
        # True if we are inside the <a> element that contains the IMDB ID
        self._in_ref = False
        # Holds the year and type of media
        self._year = None
        self._type = None
        # The list of search results
        self.results = []

    def handle_starttag(self, tag, attrs):
        # Identify the column that contains the title information
        if tag == 'td':
            for a in attrs:
                if a == ('class', 'result_text'):
                    self._in_title = True
        # Identify the link that contains the imdb_id
        elif tag == 'a' and self._in_title:
            for a in attrs:
                if a[0] == 'href':
                    self._imdb_id = a[1].split('/')[2]
            self._in_ref = True

    def handle_data(self, data):
        if self._in_ref:
            self._title = data
        elif self._in_title:
            # Search for additional attributes: the year and the type
            if self._year is None:
                m = _RE_SEARCH_YEAR.search(data)
                if m:
                    self._year = int(m.group(1))
            if self._type is None:
                m = _RE_SEARCH_TYPE.search(data)
                if m:
                    self._type = m.group(1)

    def handle_endtag(self, tag):
        # If closing the title column, add the result to the list.
        if tag == 'td' and self._in_title:
            # If type was none, means it is a Movie
            if self._type is None:
                self._type = 'Movie'
            self.results.append(IMDBTitle(self._imdb_id, {
                'title': self._title,
                'year': self._year,
                'type': self._type,
            }))
            # Reset state variables.
            self._in_title = False
            self._year = self._type = None
        elif tag == 'a':
            self._in_ref = False


class TitleParser(html.parser.HTMLParser):
    '''Parse the IMDB title page.

    <meta property='og:title' content="TITLE (TYPE START_YEAR–END_YEAR )" />
    <script type="application/ld+json">{
      ...
      "image": "POSTER_URL",
      "genre": [
        "GENRE",
        ...
      ],
      ...
      "description": "DESCRIPTION",
      ...
      "aggregateRating": {
        ...
        "ratingValue": "RATING"
      },
      ...
    }</script>
    <div class="poster">
      <a href="..."><img alt="..." title="..." src="POSTER_URL_SMALL" /></a>
    </div>
    <div class="seasons-and-year-nav">
       ...
       <a href="/title/tt3006802/episodes?season=6&ref_=tt_eps_sn_6">6</a>
       ...
    </div>
    '''

    def __init__(self):
        super(TitleParser, self).__init__()
        # Hold the title's attributes to return
        # True if we are inside the element that contains the DB in JSON format
        self._in_db = False
        # True if we are inside the <div> element that contains the poster
        self._in_poster = False
        # True if we are inside the <div> element that contains the seasons
        self._in_seasons = False
        self.attrs = {}

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            # Check if it is the DB elements
            for a in attrs:
                if a == ('type', 'application/ld+json'):
                    self._in_db = True
        elif tag == 'meta':
            # Check if we are in the title elements
            in_title = False
            if attrs[0] == ('property', 'og:title'):
                # Get the air and end years contained in the title
                (self.attrs['title'], type_, self.attrs['air_year'],
                    end_year) = _parse_title(attrs[1][1])
                self.attrs['type'] = type_ if type_ else 'Movie'
                if end_year is not None:
                    self.attrs['end_year'] = end_year
        elif tag == 'div':
            # Check if we are in the poster <div> element
            for a in attrs:
                if a == ('class', 'poster'):
                    self._in_poster = True
        elif tag == 'img' and self._in_poster:
            # When in poster, img contains the link to the poster image
            for a in attrs:
                if a[0] == 'src':
                    self.attrs['poster_url_small'] = a[1]
        elif tag == 'a':
            for a in attrs:
                if a[0] == 'href':
                    m = _RE_SEASON.match(a[1])
                    if m is not None:
                        if 'seasons' not in self.attrs:
                            self.attrs['seasons'] = {}
                        self.attrs['seasons'][m.group('season')] = {}

    def handle_data(self, data):
        if self._in_db:
            db = json.loads(data)
            # The description may be missing
            try:
                self.attrs['plot'] = db['description']
            except KeyError: pass
            try:
                self.attrs['poster_url'] = db['image']
            except KeyError: pass
            try:
                self.attrs['genre'] = db['genre']
            except KeyError: pass
            try:
                m = _RE_DURATION.match(db['duration'])
                if m is not None:
                    self.attrs['duration'] = '{}h {}m'.format(
                        m.group('h'), m.group('m'))
            except KeyError: pass
            # The rating may be missing
            try:
                self.attrs['rating'] = db['aggregateRating']['ratingValue']
            except KeyError: pass

    def handle_endtag(self, tag):
        if tag == 'script':
            self._in_db = False
        elif tag == 'div':
            self._in_poster = False
            self._in_seasons = False


class SeasonParser(html.parser.HTMLParser):
    '''Parse the IMDB page that contains a season's episodes descriptions.

    <div class="list_item (odd|even)">
    ...
    <img width="200" height="112" class="zero-z-index" ... src="STILL">
    ...
    <meta itemprop="episodeNumber" content="2"/>
    <div class="airdate">AIRDATE</div>
    <strong><a href="..." title="TITLE" itemprop="name">TITLE</a></strong>
    ...
    <div class="ipl-rating-star ">
      ...
      <span class="ipl-rating-star__rating">RATING</span>
      ...
    </div>
    <div class="item_description" itemprop="description">PLOT</div>
    ...
    </div>
    '''

    def __init__(self, season):
        super(SeasonParser, self).__init__()
        # Holds the dictionary of episodes for the requested season
        self.episodes = {}
        # Holds a dictionary with all the seasons (only one season is requested
        # at a time, but is for easy integration with the IMDBTitle object).
        self.attrs = {str(season): self.episodes}
        # True if we are inside the <div> element that contains the airdate
        self._in_airdate = False
        # True if we are inside the <div> element which is the top level rating
        # containter
        self._in_rating_container = False
        # True if we are inside the <span> element that contains the rating
        self._in_rating = False
        # True if we are inside the <div> element that contains the episode
        # plot.
        self._in_plot = False
        # True if we are inside the <a> element that contains the title
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
                self.current_episode['still'] = still
        elif tag == 'meta':
            # Check if it is the episode number
            is_episodenumber = False
            for a in attrs:
                if a == ('itemprop', 'episodeNumber'):
                    is_episodenumber = True
                elif a[0] == 'content':
                    episodenumber = a[1]
            if is_episodenumber:
                self.episodes[episodenumber] = self.current_episode
        elif tag == 'div':
            for a in attrs:
                if a == ('class', 'list_item odd') or a == (
                        'class', 'list_item even'):
                    # New episode
                    self.current_episode = {}
                    break
                elif a == ('class', 'airdate'):
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
            self.current_episode['air_date'] = data.strip()
        elif self._in_rating:
            self.current_episode['rating'] = float(data)
        elif self._in_plot:
            self.current_episode['plot'] = data.strip()
        elif self._in_title:
            self.current_episode['title'] = data

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
    '''Represents a title in the IMDB database.'''

    def __init__(self, imdb_id, attrs=None):
        self.id = imdb_id
        if attrs is None:
            self._attrs = {}
        else:
            self._attrs = attrs

    def __eq__(self, other):
        return self.id == other.id

    def __getitem__(self, attr):
        return self._attrs[attr]

    def __contains__(self, attr):
        return attr in self._attrs

    def __hash__(self):
        return hash(self.id)

    async def fetch(self):
        '''Obtain the remaining attributes from the title's main IMDB page.'''
        # Fetch the title page
        url = _IMDB_TITLE_URL.format(self.id)
        http_client = tornado.httpclient.AsyncHTTPClient()
        logging.info('fetching {}...'.format(url))
        response = await http_client.fetch(url, headers=_HTTP_HEADERS)
        logging.info('received {}'.format(url))
        # Parse the important information
        parser = TitleParser()
        parser.feed(response.body.decode('utf-8'))
        self._attrs.update(parser.attrs)
        # Fetch season information, if it has any seasons
        try:
            for s in self._attrs['seasons'].keys():
                await self._fetch_season(s)
        except KeyError: pass

    async def _fetch_season(self, season):
        '''Obtain a given season's episodes descriptions.'''
        # Fetch the title page
        url = _IMDB_SEASON_URL.format(self.id, season)
        http_client = tornado.httpclient.AsyncHTTPClient()
        logging.info('fetching {}...'.format(url))
        response = await http_client.fetch(url, headers=_HTTP_HEADERS)
        logging.info('received {}'.format(url))
        # Parse the important information
        parser = SeasonParser(season)
        parser.feed(response.body.decode('utf-8'))
        self._attrs['seasons'].update(parser.attrs)


async def search(title, title_types, year=None):
    '''Search by title in the IMDB site.
    title_type might be one of: 'Movie', 'TV Series', 'Video', 'Short',
    'TV Mini-Series', 'TV Movie', 'TV Episode' or 'Video Game'.
    '''
    # Check that the type of title is correct
    for t in title_types:
        if t not in _SEARCH_TYPES:
            raise ValueError("wrong type '{}'".format(t))
    # Build the URL of the search page
    search_attributes = {'ref_': 'nv_sr_fn', 's': 'tt', 'q': title}
    url = '{}?{}'.format(
        _IMDB_SEARCH_URL, urllib.parse.urlencode(search_attributes))

    # Fetch the list of titles
    http_client = tornado.httpclient.AsyncHTTPClient()
    logging.info('fetching {}...'.format(url))
    response = await http_client.fetch(url, headers=_HTTP_HEADERS)
    logging.info('received {}'.format(url))

    # Parse the desired information from the result
    parser = SearchParser()
    parser.feed(response.body.decode('utf-8'))

    # Return the list of titles
    # Keep only the titles with the right type or, if the year is given, those
    # corresponding to that year.
    return [a for a in parser.results
        if a['type'] in title_types
        and (year is None or a['year'] == year or a['year'] == year - 1)]

