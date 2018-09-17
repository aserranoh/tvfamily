
import os
import sys
import unittest
import tornado.gen

TEST_PATH = os.path.dirname(sys.argv[0])
ROOT_PATH = os.path.join(TEST_PATH, '..')

sys.path.insert(0, ROOT_PATH)
import tvfamily.core

# Select libcurl implementation for HTTP requests
tornado.httpclient.AsyncHTTPClient.configure(
    "tornado.curl_httpclient.CurlAsyncHTTPClient")

VIDEOS_PATH = os.path.join(TEST_PATH, 'test_top')
OPTIONS = {
    'plugins': {
        'path': os.path.join(ROOT_PATH, 'plugins'),
        'thepiratebay': {
            'url': 'https://pirate.bet'
        }
    },
    'videos': {
        'path': VIDEOS_PATH
    }
}


class CoreTestCase(unittest.TestCase):
    '''Test the Core object.'''

    def test_settings(self):
        os.system('mkdir {}'.format(VIDEOS_PATH))
        settings_file = os.path.join(TEST_PATH, 'settings.json')
        tvfamily.core._USER_SETTINGS_FILE = settings_file
        core = tvfamily.core.Core(OPTIONS, False)
        s = core.get_settings()
        s['imdb_cache_expiracy']
        core = tvfamily.core.Core(OPTIONS, False)
        x = {'imdb_cache_expiracy': 0}
        core.update_settings(x)
        s = core.get_settings()
        self.assertEqual(s['imdb_cache_expiracy'], 0)
        self.assertEqual(len(core.get_torrents_filters()), 3)
        os.system('rm -r {} {}'.format(VIDEOS_PATH, settings_file))

    def test_top(self):
        os.system('mkdir {}'.format(VIDEOS_PATH))
        tvfamily.core._USER_SETTINGS_FILE = os.path.join(
            VIDEOS_PATH, '.tvfamily.json')
        core = tvfamily.core.Core(OPTIONS, False)
        @tornado.gen.coroutine
        def cor():
            medias = yield core.top('movies')
            return medias
        medias = tornado.ioloop.IOLoop.current().run_sync(cor)
        os.system('rm -r {}'.format(VIDEOS_PATH))

