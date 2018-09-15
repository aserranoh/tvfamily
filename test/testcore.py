
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


class CoreTestCase(unittest.TestCase):
    '''Test the Core object.'''

    def test_top(self):
        videos_path = os.path.join(TEST_PATH, 'test_top')
        os.system('mkdir {}'.format(videos_path))
        options = {
            'plugins': {
                'path': os.path.join(ROOT_PATH, 'plugins'),
                'thepiratebay': {
                    'url': 'https://pirate.bet'
                }
            },
            'videos': {
                'path': videos_path
            }
        }
        tvfamily.core._USER_SETTINGS_FILE = os.path.join(
            videos_path, '.tvfamily.json')
        core = tvfamily.core.Core(options, False)
        @tornado.gen.coroutine
        def cor():
            medias = yield core.top('movies')
            return medias
        medias = tornado.ioloop.IOLoop.current().run_sync(cor)
        os.system('rm -r {}'.format(videos_path))

