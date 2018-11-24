#!/usr/bin/env python

import signal
import tornado.ioloop
import tornado.web

PORT = 9999

class SimuIMDBPirate(object):
    '''Simulates the IMDB and PirateBay sites.'''

    def __init__(self):
        self._app = tornado.web.Application([
            (r'/top/(\d+)', tornado.web.StaticFileHandler,
                {'path': 'test/static'}),
        ])
        # Handle signals
        def signal_handler(signum, frame):
            tornado.ioloop.IOLoop.current().stop()
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def run(self):
        '''Run the HTTP server and start processing requests.'''
        self._app.listen(PORT)
        tornado.ioloop.IOLoop.current().start()

if __name__ == '__main__':
    server = SimuIMDBPirate()
    server.run()

