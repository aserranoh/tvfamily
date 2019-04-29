
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

import tornado.ioloop
import tornado.iostream
import tornado.web

import tvfamily.core
import tvfamily.httpserver
import tvfamily.webcommon
import tvfamily.webservice

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


class PlayHandler(tvfamily.webcommon.BaseHandler):
    '''Handler of the page to play a video.'''

    async def get(self):
        '''Serves the page with the video player.'''
        category = self.get_query_argument('category')
        imdb_id = self.get_query_argument('title')
        video_file = self.get_query_argument('video')
        title = await self._core.get_title(category, imdb_id)
        video = self._core.get_video_from_file(video_file)
        self.render('playmovie.html', category=category, title=title,
            video=video)


class SubtitlesHandler(tvfamily.webcommon.BaseHandler):
    '''Serves a vtt subtitles file.'''

    def get(self, filename):
        '''Send the subtitle filename to the client.'''
        with open(filename, 'r') as f:
            self.write(f.read())


class SettingsHandler(tvfamily.webcommon.BaseHandler):
    '''Show the settings page.'''

    def get(self):
        '''Show the settings page.'''
        self.render('settings.html',
            torrents_filters=self._core.get_torrents_filters(),
            settings=self._core.get_settings())


class SaveSettingsHandler(tvfamily.webcommon.BaseHandler):
    '''Save the settings.'''

    def post(self):
        '''Update the runtime settings in the core.'''
        # Cache expiracy
        cache_expiracy = int(self.get_body_argument('imdb_cache_expiracy'))
        # Torrents filters
        torrents_filters=self._core.get_torrents_filters()
        new_filters = [[v for v in f
            if self.get_body_argument(v, default=None) == 'on']
            for f in torrents_filters]
        # Build the new settings dictionary
        settings = {
            'imdb_cache_expiracy': cache_expiracy,
            'torrents_filters': new_filters,
        }
        self._core.update_settings(settings)
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
                (r'/', tornado.web.RedirectHandler, {'url': '/index.html'}),
                (r'/(index.html)', tornado.web.StaticFileHandler,
                    {'path': 'web'}),
                (r'/play', PlayHandler, d),
                (r'(.*?\.vtt)', SubtitlesHandler),
                (r'/(styles.css)', tornado.web.StaticFileHandler,
                    {'path': 'web'}),
                (r'/(.*?\.svg)', tornado.web.StaticFileHandler,
                    {'path': 'data'}),
                (r'/settings', SettingsHandler, d),
                (r'/save-settings', SaveSettingsHandler, d),
                ]
            ws = tvfamily.webservice.WebService(self._core)
            handlers.extend(ws.get_handlers())
            self.add_handlers(handlers)
            # Run the core's task scheduler
            tornado.ioloop.IOLoop.current().spawn_callback(
                self._core.run_scheduler)
        except (tvfamily.httpserver.HTTPServerError,
                tvfamily.core.CoreError) as e:
            raise ServerError(str(e))

