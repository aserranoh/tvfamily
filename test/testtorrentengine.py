
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


class TorrentEngineTestCase(unittest.TestCase):
    '''Test the TorrentEngine object.'''

    def test_no_plugins_dir(self):
        t = tvfamily.core.TorrentEngine('nodir')
        @tornado.gen.coroutine
        def cor():
            torrents = yield t.top('movies', {})
            return torrents
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        self.assertEqual(l, [])

    def test_plugins(self):
        t = tvfamily.core.TorrentEngine(os.path.join(TEST_PATH, 'plugins'))
        @tornado.gen.coroutine
        def cor():
            torrents = yield t.top('movies', {})
            return torrents
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        self.assertEqual(len(l), 2)
        self.assertEqual(l[0].name, 'torrent2')
        self.assertEqual(l[1].name, 'torrent1')
        self.assertEqual(len(t._plugins), 2)
        # Force a reload of the plugins
        self.assertEqual(len(l), 2)
        self.assertEqual(l[0].name, 'torrent2')
        self.assertEqual(l[1].name, 'torrent1')
        self.assertEqual(len(t._plugins), 2)
        # Temporary remove a plugin
        os.system('mv {} {}'.format(
            os.path.join(TEST_PATH, 'plugins', 'plugin1.py'),
            os.path.join(TEST_PATH, 'plugins', '~plugin1.py')))
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0].name, 'torrent2')
        self.assertEqual(len(t._plugins), 1)
        os.system('mv {} {}'.format(
            os.path.join(TEST_PATH, 'plugins', '~plugin1.py'),
            os.path.join(TEST_PATH, 'plugins', 'plugin1.py')))

    def test_plugin_exception(self):
        t = tvfamily.core.TorrentEngine(os.path.join(TEST_PATH, 'plugins'))
        @tornado.gen.coroutine
        def cor():
            torrents = yield t.top('tv_shows', {})
            return torrents
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        self.assertEqual(len(l), 1)
        self.assertEqual(l[0].name, 'torrent2')

    def test_filter(self):
        te = tvfamily.core.TorrentEngine
        t = te(os.path.join(ROOT_PATH, 'plugins'))
        @tornado.gen.coroutine
        def cor():
            options = {'plugins': {'thepiratebay': {
                'url': 'https://pirate.bet'}}}
            torrents = yield t.top('movies', options,
                filter=(['WEB-DL', 'Blu-ray'], ['H.264'], None))
            return torrents
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        for x in l:
            q = x.name_info.get('quality')
            c = x.name_info.get('codec')
            r = x.name_info.get('resolution')
            self.assertTrue((q is None
                or te._FILTER_QUALITY['Blu-ray'].match(q)
                or te._FILTER_QUALITY['WEB-DL'].match(q))
                and (c is None or te._FILTER_CODEC['H.264'].match(c)))

    def test_list_filters(self):
        t = tvfamily.core.TorrentEngine(os.path.join(ROOT_PATH, 'plugins'))
        f = t.get_filter_values()
        expected = (t._QUALITY_VALUES, t._CODEC_VALUES, t._RESOLUTION_VALUES)
        for x, e in zip(f, expected):
            self.assertEqual(x, e)

