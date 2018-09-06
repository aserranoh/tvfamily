
import os
import sys
import unittest
import tornado.gen

TEST_PATH = os.path.dirname(sys.argv[0])
ROOT_PATH = os.path.join(TEST_PATH, '..')

sys.path.insert(0, ROOT_PATH)
import tvfamily.imdb


class IMDBTestCase(unittest.TestCase):
    '''Test the IMDB API.'''

    def test_imdb_movies_no_year(self):
        @tornado.gen.coroutine
        def cor():
            titles = yield tvfamily.imdb.search('spider-man', ['Movie'])
            return titles
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        self.assertGreater(len(l), 0)
        for t in l:
            self.assertEqual(t['type'], 'Movie')

    def test_imdb_movies_year(self):
        @tornado.gen.coroutine
        def cor():
            titles = yield tvfamily.imdb.search(
                'spider-man', ['Movie'], year=2002)
            return titles
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        self.assertGreater(len(l), 0)
        for t in l:
            self.assertEqual(t['type'], 'Movie')
            self.assertEqual(t['year'], 2002)
        # Get the attributes of the first hit in the search list
        title = l[0]
        tornado.ioloop.IOLoop.current().run_sync(title.fetch)

    def test_imdb_tv_series(self):
        @tornado.gen.coroutine
        def cor():
            titles = yield tvfamily.imdb.search('the expanse', ['TV Series'])
            return titles
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        self.assertGreater(len(l), 0)
        for t in l:
            self.assertEqual(t['type'], 'TV Series')
        # Get the attributes of the first hit in the search list
        title = l[0]
        tornado.ioloop.IOLoop.current().run_sync(title.fetch)

    def test_imdb_tv_series_finished(self):
        @tornado.gen.coroutine
        def cor():
            titles = yield tvfamily.imdb.search(
                'buffy the vampire slayer', ['TV Series'])
            return titles
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        self.assertGreater(len(l), 0)
        for t in l:
            self.assertEqual(t['type'], 'TV Series')
        # Get the attributes of the first hit in the search list
        title = l[0]
        tornado.ioloop.IOLoop.current().run_sync(title.fetch)

    def test_imdb_tv_series_seasons(self):
        @tornado.gen.coroutine
        def cor():
            titles = yield tvfamily.imdb.search('stargate sg-1', ['TV Series'])
            return titles
        l = tornado.ioloop.IOLoop.current().run_sync(cor)
        self.assertGreater(len(l), 0)
        # Get the attributes of the first hit in the search list
        title = l[0]
        @tornado.gen.coroutine
        def cor_season():
            yield title.fetch_season(2)
        tornado.ioloop.IOLoop.current().run_sync(cor_season)
        season = title['seasons']['2']
        for i in range(22):
            self.assertIn(str(i + 1), season)

    def test_imdb_wrong_type(self):
        @tornado.gen.coroutine
        def cor():
            titles = yield tvfamily.imdb.search('spider-man', ['wrongtype'])
            return titles
        self.assertRaises(ValueError,
            tornado.ioloop.IOLoop.current().run_sync, cor)

