
import os
import sys
import time
import unittest
import tornado.gen

TEST_PATH = os.path.dirname(sys.argv[0])
ROOT_PATH = os.path.join(TEST_PATH, '..')

sys.path.insert(0, ROOT_PATH)
import tvfamily.imdb
import tvfamily.core
import tvfamily.torrent

# Select libcurl implementation for HTTP requests
tornado.httpclient.AsyncHTTPClient.configure(
    "tornado.curl_httpclient.CurlAsyncHTTPClient")


class TitlesDBTestCase(unittest.TestCase):
    '''Test the TorrentEngine object.'''

    def test_torrents_to_imdb(self):
        os.system('rm {}'.format(
            os.path.join(TEST_PATH, tvfamily.core.TitlesDB._IMDB_ID_CACHE)))
        db = tvfamily.core.TitlesDB([], TEST_PATH)
        t = tvfamily.torrent.Torrent(
            'Ant-Man and The Wasp-rarbg.mkv', '', '', 1, 1)
        self.assertRaises(KeyError, db._get_imdb_id_from_torrent, t)
        db._save_torrents_to_imdb()
        db._torrents_to_imdb = None
        self.assertRaises(KeyError, db._get_imdb_id_from_torrent, t)
        os.system('rm {}'.format(os.path.join(TEST_PATH, db._IMDB_ID_CACHE)))
        t2 = tvfamily.torrent.Torrent(
            'Ant-Man and The Wasp.2018-rarbg.mkv', '', '', 1, 1)
        self.assertRaises(KeyError, db._get_imdb_id_from_torrent, t2)
        db._set_imdb_id_from_torrent(t, 'tt12345')
        self.assertEqual(len(db._torrents_to_imdb), 1)
        db._set_imdb_id_from_torrent(t2, 'tt12346')
        self.assertEqual(len(db._torrents_to_imdb), 2)
        id1 = db._get_imdb_id_from_torrent(t)
        self.assertEqual(id1, 'tt12345')
        id2 = db._get_imdb_id_from_torrent(t2)
        self.assertEqual(id2, 'tt12346')

    def test_title(self):
        imdb_title = tvfamily.imdb.IMDBTitle('tt12345')
        title = tvfamily.core.Title(imdb_title, TEST_PATH)
        title = tvfamily.core.Title('tt12345', TEST_PATH)
        @tornado.gen.coroutine
        def cor_search():
            results = yield tvfamily.imdb.search('The Expendables', ['Movie'])
            return results[0]
        imdb_title = tornado.ioloop.IOLoop.current().run_sync(cor_search)
        title = tvfamily.core.Title(imdb_title, TEST_PATH)
        tornado.ioloop.IOLoop.current().run_sync(title.fetch)
        self.assertTrue(title.poster_url.startswith('http'))
        title = tvfamily.core.Title(imdb_title, TEST_PATH, 60)
        tornado.ioloop.IOLoop.current().run_sync(title.fetch)
        title = tvfamily.core.Title(imdb_title, TEST_PATH, 0.1)
        time.sleep(1)
        tornado.ioloop.IOLoop.current().run_sync(title.fetch)
        os.system('rm {}'.format(title._cached_file))

    def test_medias_from_torrents(self):
        settings = {'imdb_cache_expiracy': 24 * 3600}
        categories = [
            tvfamily.core.Category(
                'Movies', tvfamily.core.Movie, ['Movie'], TEST_PATH, settings),
            tvfamily.core.Category(
                'TV Series', tvfamily.core.TVSerie,
                ['TV Series', 'TV Mini-Series'], TEST_PATH, settings)
        ]
        db = tvfamily.core.TitlesDB(categories, TEST_PATH)
        engine = tvfamily.core.TorrentEngine(
            os.path.join(ROOT_PATH, 'plugins'))
        options = {'plugins': {'thepiratebay': {'url': 'https://pirate.bet'}}}
        @tornado.gen.coroutine
        def cor():
            c = categories[0].key
            torrents = yield engine.top(c, options)
            medias = yield db.get_medias_from_torrents(torrents, c)
            return medias
        medias = tornado.ioloop.IOLoop.current().run_sync(cor)
        s = [str(m) for m in medias]
        medias = tornado.ioloop.IOLoop.current().run_sync(cor)
        @tornado.gen.coroutine
        def cor2():
            c = categories[1].key
            torrents = yield engine.top(c, options)
            medias = yield db.get_medias_from_torrents(torrents, c)
            return medias
        medias = tornado.ioloop.IOLoop.current().run_sync(cor2)
        s = [str(m) for m in medias]
        os.system('rm {}'.format(os.path.join(TEST_PATH, '*.json')))

    def test_categories(self):
        settings = {'imdb_cache_expiracy': 24 * 3600}
        categories = [
            tvfamily.core.Category(
                'Movies', tvfamily.core.Movie, ['Movie'], TEST_PATH, settings),
            tvfamily.core.Category(
                'TV Series', tvfamily.core.TVSerie,
                ['TV Series', 'TV Mini-Series'], TEST_PATH, settings)
        ]
        db = tvfamily.core.TitlesDB(categories, TEST_PATH)
        self.assertEqual(db.get_categories(), categories)

