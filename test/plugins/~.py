
import tornado.gen

import tvfamily.torrent

@tornado.gen.coroutine
def top(category, options):
    return [tvfamily.torrent.Torrent('torrent1', '', '', 1, 1)]

