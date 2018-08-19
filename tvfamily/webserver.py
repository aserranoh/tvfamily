
'''webserver.py - Implements the Web Server layer.

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

import tornado.web

import tvfamily.core
import tvfamily.httpserver

__script__ = 'tvfamily'
__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'
__homepage__ = 'https://github.com/aserranoh/tvfamily'


VERSION_STRING = '''\
%(prog)s {version}
{copyright}
License GPLv3+: GNU GPL version 3 or later <http://gnu.org/licenses/gpl.html>
This is free software: you are free to change and redistribute it.
There is NO WARRANTY, to the extent permitted by law.\
'''.format(version=__version__, copyright=__copyright__)

HELP_EPILOG = '''\
Report bugs to: {email}
{prog} home page: {homepage}
'''.format(email=__email__, prog=__script__, homepage=__homepage__)

SETTINGS = {'template_path': 'web'}


class ServerError(Exception): pass


class BaseHandler(tornado.web.RequestHandler):
    '''Base class to iplement a http request handler.'''

    def initialize(self, core=None):
        '''Pass the core of the application to the handlers.

        Parameters:
          * core: the core of the tvfamily application.
        '''
        self._core = core

class RootHandler(BaseHandler):
    '''Root page's handler.'''

    def get(self):
        '''Serve the root page.

        The root page must redirect to the list of media of the first
        category.
        '''
        category = next(self._core.get_categories())
        self.redirect('/categories/{}'.format(category.key))

class CategoriesHandler(BaseHandler):
    '''Index page's handler (list of medias of a category).'''

    @tornado.gen.coroutine
    def get(self, category):
        '''Serve the list of medias of a given category page.

        category is the name of the current category.
        '''
        # Get the title's posters
        posters = yield [t.get_attr('poster_url')
            for t in self._core.get_titles(category)]
        self.render('index.html',
            categories=self._core.get_categories(), current=category,
            titles=self._core.get_titles(category), posters=posters)

class TitleHandler(BaseHandler):
    '''Title main page.'''

    @tornado.gen.coroutine
    def get(self):
        '''Serves the page with the caracteristics of a title.'''
        category = self.get_query_argument('category')
        id = self.get_query_argument('id')
        title = self._core.get_title(category, id)
        if title.has_episodes():
            yield self._serve_episode(title)
        else:
            yield self._serve_movie(title)

    @tornado.gen.coroutine
    def _serve_episode(self, title):
        '''Serve the page episode.html.'''
        # Get the season number
        try:
            season = int(self.get_query_argument('season'))
        except tornado.web.MissingArgumentError:
            season = title.get_seasons()[0]
        # Get the episode number
        try:
            episode = int(self.get_query_argument('episode'))
        except tornado.web.MissingArgumentError:
            episode = title.get_episodes(season)[0]
        # Get title attributes
        poster = yield title.get_attr('poster_url')
        plot = yield title.get_attr('plot')
        genre = yield title.get_attr('genre')
        air_year = yield title.get_attr('air_year')
        end_year = yield title.get_attr('end_year')
        end_year = '' if not end_year else str(end_year)
        rating = yield title.get_attr('rating')
        # Get episode attributes
        e = title.get_episode(season, episode)
        still = yield e.get_attr('still')
        episode_plot = yield e.get_attr('plot')
        episode_air_date = yield e.get_attr('air_date')
        episode_rating = yield e.get_attr('rating')
        episode_title = yield e.get_attr('title')
        # Render the page
        self.render('episode.html',
            category=self.get_query_argument('category'), title=title,
            episode=e, poster=poster, plot=plot, genre=', '.join(genre),
            air_year=str(air_year), end_year=end_year, rating=rating,
            still=still, episode_plot=episode_plot,
            episode_air_date=episode_air_date, episode_rating=episode_rating,
            episode_title=episode_title)

    @tornado.gen.coroutine
    def _serve_movie(self, title):
        '''Serve the page movie.html.'''
        # Get title attributes
        poster = yield title.get_attr('poster_url')
        air_year = yield title.get_attr('air_year')
        genre = yield title.get_attr('genre')
        rating = yield title.get_attr('rating')
        plot = yield title.get_attr('plot')
        # Render the page
        self.render('movie.html', title=title, poster=poster,
            air_year=str(air_year), genre=', '.join(genre), rating=rating,
            category=self.get_query_argument('category'), plot=plot)

class PlayHandler(BaseHandler):
    '''Handler of the page to play a video.'''

    def get(self):
        '''Serves the page with the video player.'''
        category = self.get_query_argument('category')
        title = self._core.get_title(category, self.get_query_argument('id'))
        if title.has_episodes():
            self._play_episode(title, category)
        else:
            self._play_movie(title, category)

    def _play_episode(self, title, category):
        '''Play an episode.'''
        season = int(self.get_query_argument('season'))
        episode = int(self.get_query_argument('episode'))
        self.render('playepisode.html', category=category, title=title,
            season=season, episode=episode)

    def _play_movie(self, title, category):
        '''Play a movie.'''
        self.render('playmovie.html', category=category, title=title)

class VideoHandler(BaseHandler):
    '''Serves a video in chunks.'''

    def compute_etag(self):
        return None

    @classmethod
    def get_content_version(cls, abspath):
        return 1

    @classmethod
    def _get_cached_version(cls, abs_path):
        return None

    @tornado.gen.coroutine
    def get(self):
        request_range = None
        range_header = self.request.headers.get('Range')
        q = self.get_query_argument
        title = self._core.get_title(q('category'), q('id'))
        if title.has_episodes():
            video = title.get_episode(
                int(q('season')), int(q('episode'))).get_video()
        else:
            video = title.get_video()
        # Obtain the start, end and total size of the range to serve
        if range_header:
            # As per RFC 2616 14.16, if an invalid Range header is specified,
            # the request will be treated as if the header didn't exist.
            request_range = tornado.httputil._parse_request_range(range_header)
        if request_range:
            start, end = request_range
            size = video.get_size()
            if (start is not None and start >= size) or end == 0:
                # As per RFC 2616 14.35.1, a range is not satisfiable only: if
                # the first requested byte is equal to or greater than the
                # content, or when a suffix with length 0 is specified
                self.set_status(416)  # Range Not Satisfiable
                self.set_header("Content-Type", "text/plain")
                self.set_header("Content-Range", "bytes */%s" % (size, ))
                return
            if start is not None and start < 0:
                start += size
            if end is not None and end > size:
                # Clients sometimes blindly use a large range to limit their
                # download size; cap the endpoint at the actual file size.
                end = size
            self._set_headers(start, end, size)
        else:
            start = end = None
        # Serve the content
        content = video.get_content(start, end)
        for chunk in content:
            self.write(chunk)
            yield tornado.gen.Task(self.flush)

    def _set_headers(self, start, end, size):
        '''Set the headers for the response. start, end and size are the
        attributes for the Content-Range header.
        '''
        # Partial Content
        self.set_status(206)
        self.set_header('Content-Type', 'video/mp4')
        self.set_header('Accept-Ranges', 'bytes')
        self.set_header('Content-Range',
            tornado.httputil._get_content_range(start, end, size))


class SubtitlesHandler(BaseHandler):
    '''Serves a vtt subtitles file.'''

    def get(self, filename):
        '''Send the subtitle filename to the client.'''
        with open(filename, 'r') as f:
            self.write(f.read())


class SettingsHandler(BaseHandler):
    '''Show the settings page.'''

    def get(self):
        '''Show the settings page.'''
        self.render('settings.html', settings=self._core.get_settings())


class SaveSettingsHandler(BaseHandler):
    '''Save the settings.'''

    def post(self):
        cache_expiracy = int(self.get_body_argument('imdb_cache_expiracy'))
        settings = {
            'imdb_cache_expiracy': cache_expiracy,
        }
        self._core.set_settings(settings)
        self.redirect('/')


class WebServer(tvfamily.httpserver.HTTPServer):
    '''The HTTP server that serves the pages to the user.'''

    def __init__(self):
        try:
            tvfamily.httpserver.HTTPServer.__init__(self, name='tvfamily',
                description='Multimedia Server using HTML5.',
                version=VERSION_STRING, epilog=HELP_EPILOG, settings=SETTINGS)
            self._core = tvfamily.core.Core(self.options, self.daemonize)
            d = {'core': self._core}
            handlers = [
                (r'/', RootHandler, d),
                (r'/categories/(.+)', CategoriesHandler, d),
                (r'/title', TitleHandler, d),
                (r'/play', PlayHandler, d),
                (r'/stream', VideoHandler, d),
                (r'(.*?\.vtt)', SubtitlesHandler),
                (r'/(styles.css)', tornado.web.StaticFileHandler,
                    dict(path='web')),
                (r'/(.*?\.svg)', tornado.web.StaticFileHandler,
                    dict(path='data')),
                (r'/settings', SettingsHandler, d),
                (r'/save-settings', SaveSettingsHandler, d),
                ]
            self.add_handlers(handlers)
        except (tvfamily.httpserver.HTTPServerError,
                tvfamily.core.CoreError) as e:
            raise ServerError(str(e))

