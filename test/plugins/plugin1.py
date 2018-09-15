
import tornado.gen

import tvfamily.torrent

@tornado.gen.coroutine
def top(category, options):
    if category == 'movies':
        return [tvfamily.torrent.Torrent('torrent1', '', '', 1, 1)]
    else:
        raise ValueError('test error')

