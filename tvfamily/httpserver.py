
'''httpserver.py - Implements the Web Server layer.

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

import random
import tornado.ioloop
import tornado.web

import tvfamily.core

__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'
__homepage__ = 'https://github.com/aserranoh/tvfamily'


SECRET_BITS = 128

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

    def get(self, category):
        '''Serve the list of medias of a given category page.

        category is the name of the current category.
        '''
        self.render('index.html',
            categories=self._core.get_categories(), current=category,
            titles=self._core.get_titles(category))

class TitleHandler(BaseHandler):
    '''Title main page.'''

    def get(self):
        '''Serves the page with the caracteristics of a title.'''
        category = self.get_query_argument('category')
        id = self.get_query_argument('id')
        title = self._core.get_title(category, id)
        if title.has_episodes():
            self._serve_episode(title)
        else:
            self._serve_movie(title)

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
        # Render the page
        self.render('episode.html',
            category=self.get_query_argument('category'), title=title,
            season=season, episode=episode)

    def _serve_movie(self, title):
        '''Serve the page movie.html.'''
        self.render('movie.html', title=title)

class PlayEpisodeHandler(BaseHandler):
    '''Handler of the page to play an episode of a series.'''

    def get(self):
        '''Serves the page with the video player.'''
        category = self.get_query_argument('category')
        title = self._core.get_title(category, self.get_query_argument('id'))
        season = int(self.get_query_argument('season'))
        episode = int(self.get_query_argument('episode'))
        video = title.get_episode(season, episode).get_video()
        stream = self._core.new_stream(video)
        self.render('playepisode.html', category=category, title=title,
            season=season, episode=episode, stream=stream)

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
    def get(self, stream_id):
        request_range = None
        range_header = self.request.headers.get('Range')
        stream = self._core.get_stream(int(stream_id))
        # Obtain the start, end and total size of the range to serve
        if range_header:
            # As per RFC 2616 14.16, if an invalid Range header is specified,
            # the request will be treated as if the header didn't exist.
            request_range = tornado.httputil._parse_request_range(range_header)
        if request_range:
            start, end = request_range
            size = stream.get_size()
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
        content = stream.get_content(start, end)
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


class HTTPServer(object):
    '''The HTTP server that serves the pages to the user.

    Constructor parameters:
      * options_file: the options file.
      * daemon: True if in daemon mode, False if in user mode.
    '''

    def __init__(self, options_file, daemon):
        self._core = tvfamily.core.Core(options_file, daemon)
        settings = {
            'cookie_secret': '{:x}'.format(random.getrandbits(SECRET_BITS)),
            'template_path': 'web',
            #'static_path': 'web',
            }
        handlers = [
            (r'/', RootHandler, dict(core=self._core)),
            (r'/categories/(.+)', CategoriesHandler, dict(core=self._core)),
            (r'/title', TitleHandler, dict(core=self._core)),
            (r'/play', PlayEpisodeHandler, dict(core=self._core)),
            (r'/stream/(\d+)', VideoHandler, dict(core=self._core)),
            (r'(.*?\.vtt)', SubtitlesHandler)
            ]
        self._app = tornado.web.Application(handlers, **settings)

    def run(self):
        '''Run the HTTP server and start processing requests.'''
        self._app.listen(int(self._core.get_options().server.port))
        tornado.ioloop.IOLoop.current().start()

