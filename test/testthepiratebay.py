
import os
import sys
import unittest
import tornado.gen
import tornado.httpclient

TEST_PATH = os.path.dirname(sys.argv[0])
ROOT_PATH = os.path.join(TEST_PATH, '..')

sys.path.insert(0, os.path.join(ROOT_PATH, 'plugins'))
sys.path.insert(0, ROOT_PATH)
import tvfamily.core
import thepiratebay

# Select libcurl implementation for HTTP requests
tornado.httpclient.AsyncHTTPClient.configure(
    "tornado.curl_httpclient.CurlAsyncHTTPClient")


class ThePirateBayTestCase(unittest.TestCase):
    '''Test the ThePirateBay plugin.'''

    def test_thepiratebay_movies(self):
        @tornado.gen.coroutine
        def cor():
            options = {'plugins': {'thepiratebay': {
                'url': 'https://pirate.bet'}}}
            torrents = yield thepiratebay.top('movies', options)
            return torrents
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        self.assertEqual(len(l), 200)
        for t in l:
            self.assertIsInstance(t.seeders, int)
            self.assertIsInstance(t.leechers, int)
            fields = t.size.split('\xa0')
            self.assertIsInstance(float(fields[0]), float)
            self.assertIn(fields[1], ['GiB', 'MiB'])

    def test_thepiratebay_tv_series(self):
        @tornado.gen.coroutine
        def cor():
            options = {'plugins': {'thepiratebay': {
                'url': 'https://pirate.bet'}}}
            torrents = yield thepiratebay.top('tv_series', options)
            return torrents
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        self.assertEqual(len(l), 200)
        for t in l:
            self.assertIsInstance(t.seeders, int)
            self.assertIsInstance(t.leechers, int)
            fields = t.size.split('\xa0')
            self.assertIsInstance(float(fields[0]), float)
            self.assertIn(fields[1], ['GiB', 'MiB'])

