
'''webservice.py - Implements the Web Service layer.

Copyright 2018 2019 Antonio Serrano Hernandez

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

import json
import tornado.web

import tvfamily.core
import tvfamily.webcommon

__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 2019 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'
__homepage__ = 'https://github.com/aserranoh/tvfamily'

# Profiles handlers

class GetProfilesHandler(tvfamily.webcommon.BaseHandler):
    '''Return the profiles list.'''

    def get(self):
        self.write_json(profiles=[p.name for p in self._core.get_profiles()])

class GetProfilePictureHandler(tvfamily.webcommon.BaseHandler):
    '''Return the picture for the given profile.'''

    def get(self):
        try:
            name = self.get_query_argument('name')
            self.set_header('Content-Type', 'image/png')
            pic = self._core.get_profile_picture(name)
            if pic is not None:
                self.write(pic.read())
                pic.close()
            else:
                self.write(b'')
        except (tornado.web.MissingArgumentError, KeyError):
            self.clear()
            self.set_status(400)
            self.finish('<html><body>Error</body></html>')

class SetProfilePictureHandler(tvfamily.webcommon.BaseHandler):
    '''Set the picture for the given profile.'''

    def get(self):
        try:
            name = self.get_query_argument('name')
            try:
                self._core.set_profile_picture(name)
                self.write_json(code=0)
            except (KeyError) as e:
                self.write_error(msg=str(e))
        except tornado.web.MissingArgumentError:
            self.write_error(msg="missing 'name' argument")
        except KeyError:
            self.write_error(msg='malformed request')

    def post(self):
        try:
            name = self.get_query_argument('name')
            pic = self.request.files['file'][0]['body']
            try:
                self._core.set_profile_picture(name, pic)
                self.write_json(code=0)
            except (KeyError, IOError) as e:
                self.write_error(msg=str(e))
        except tornado.web.MissingArgumentError:
            self.write_error(msg="missing 'name' argument")
        except KeyError:
            self.write_error(msg='malformed request')

class CreateProfileHandler(tvfamily.webcommon.BaseHandler):
    '''Create a new profile.'''

    def get(self):
        try:
            name = self.get_query_argument('name')
            self._core.create_profile(name)
            self.write_json(code=0)
        except tornado.web.MissingArgumentError:
            self.write_error(msg="missing 'name' argument")
        except ValueError as e:
            self.write_error(msg=str(e))

    def post(self):
        try:
            name = self.get_query_argument('name')
            pic = self.request.files['file'][0]['body']
            try:
                self._core.create_profile(name, pic)
                self.write_json(code=0)
            except IOError as e:
                self.write_error(msg=str(e))
        except tornado.web.MissingArgumentError:
            self.write_error(msg="missing 'name' argument")
        except KeyError as e:
            self.write_error(msg='malformed request')
        except ValueError as e:
            self.write_error(msg=str(e))

class DeleteProfileHandler(tvfamily.webcommon.BaseHandler):
    '''Delete a profile.'''

    def get(self):
        try:
            name = self.get_query_argument('name')
            self._core.delete_profile(name)
            self.write_json(code=0)
        except tornado.web.MissingArgumentError:
            self.write_error(msg="missing 'name' argument")
        except KeyError as e:
            self.write_error(msg=str(e))

class GetCategoriesHandler(tvfamily.webcommon.BaseHandler):
    '''Return the categories list.'''

    def get(self):
        self.write_json(categories=self._core.get_categories())

class GetTopHandler(tvfamily.webcommon.BaseHandler):
    '''Return the top list of medias of a given category.'''

    def get(self):
        try:
            category = self.get_query_argument('category')
            profile = self.get_query_argument('profile')
            medias = self._core.top(profile, category)
            self.write_json(top=[m.todict() for m in medias])
        except (tornado.web.MissingArgumentError,
                tvfamily.core.CoreError, KeyError) as e:
            self.write_error(msg=str(e))

class GetPosterHandler(tvfamily.webcommon.BaseHandler):
    '''Return the poster of a given title.'''

    def get(self):
        try:
            title_id = self.get_query_argument('id')
            self.set_header('Content-Type', 'image/jpg')
            pic = self._core.get_poster(title_id)
            if pic is not None:
                self.write(pic.read())
                pic.close()
            else:
                t = self._core.get_title(title_id)
                self.redirect(t.get_poster_url())
        except (tornado.web.MissingArgumentError, KeyError):
            self.clear()
            self.set_status(400)
            self.finish('<html><body>Error</body></html>')

class SearchHandler(tvfamily.webcommon.BaseHandler):
    '''Search a title.'''

    async def get(self):
        try:
            category = self.get_query_argument('category')
            text = self.get_query_argument('text')
            titles = await self._core.search(category, text)
            self.write_json(search=[t.todict() for t in titles])
        except Exception as e:
            self.write_error(msg=str(e))

class GetTitleHandler(tvfamily.webcommon.BaseHandler):
    '''Serve the title information.'''

    def get(self):
        try:
            title_id = self.get_query_argument('id')
            title = self._core.get_title(title_id)
            self.write_json(title=title.todict())
        except (tornado.web.MissingArgumentError, KeyError) as e:
            self.write_error(msg=str(e))

class GetMediaStatusHandler(tvfamily.webcommon.BaseHandler):

    def get(self):
        try:
            title_id = self.get_query_argument('id')
            season = episode = None
            try:
                season = int(self.get_query_argument('season'))
                episode = int(self.get_query_argument('episode'))
            except tornado.web.MissingArgumentError:
                pass
            status = self._core.get_media_status(
                title_id, season, episode)
            self.write_json(status=status.todict())
        except (tornado.web.MissingArgumentError, KeyError) as e:
            self.write_error(msg=str(e))

class DownloadHandler(tvfamily.webcommon.BaseHandler):

    def get(self):
        try:
            profile = self.get_query_argument('profile')
            title_id = self.get_query_argument('id')
            season = episode = None
            try:
                season = int(self.get_query_argument('season'))
                episode = int(self.get_query_argument('episode'))
            except tornado.web.MissingArgumentError:
                pass
            self._core.download(profile, title_id, season, episode)
            self.write_json(code=0)
        except (tornado.web.MissingArgumentError, KeyError) as e:
            self.write_error(msg=str(e))

class GetVideoHandler(tvfamily.webcommon.BaseHandler):
    '''Serves a video in chunks.'''

    def compute_etag(self):
        return None

    @classmethod
    def get_content_version(cls, abspath):
        return 1

    @classmethod
    def _get_cached_version(cls, abs_path):
        return None

    async def get(self):
        # Obtain the video to play
        try:
            title_id = self.get_query_argument('id')
            season = episode = None
            try:
                season = int(self.get_query_argument('season'))
                episode = int(self.get_query_argument('episode'))
            except tornado.web.MissingArgumentError:
                pass
            video = self._core.get_video(title_id, season, episode)
        except (tornado.web.MissingArgumentError, KeyError) as e:
            self.write_error(msg=str(e))
            return
        request_range = None
        range_header = self.request.headers.get('Range')
        size = video.get_size()
        # Obtain the start, end and total size of the range to serve
        if range_header:
            # As per RFC 2616 14.16, if an invalid Range header is specified,
            # the request will be treated as if the header didn't exist.
            request_range = tornado.httputil._parse_request_range(range_header)
        if request_range:
            start, end = request_range
            if (start is not None and start >= size) or end == 0:
                # As per RFC 2616 14.35.1, a range is not satisfiable only: if
                # the first requested byte is equal to or greater than the
                # content, or when a suffix with length 0 is specified
                self.set_status(416)  # Range Not Satisfiable
                self.set_header("Content-Type", "text/plain")
                self.set_header("Content-Range", "bytes */%s" % (size, ))
                return
            if start is not None and start < 0:
                start += size
            if end is not None and end > size:
                # Clients sometimes blindly use a large range to limit their
                # download size; cap the endpoint at the actual file size.
                end = size
            self.set_status(206)
            self.set_header('Content-Range',
                tornado.httputil._get_content_range(start, end, size))
        else:
            start = end = None
        self.set_header('Content-Type', 'video/mp4')
        self.set_header('Accept-Ranges', 'bytes')
        self.set_header('Content-Length', str(size))
        # Serve the content
        content = video.get_content(start, end)
        for chunk in content:
            self.write(chunk)
            try:
                await self.flush()
            except tornado.iostream.StreamClosedError: pass

class WebService(object):
    '''Represents the web service API.'''

    def __init__(self, core):
        self._core = core

    def get_handlers(self):
        d = {'core': self._core}
        return [
            (r'/api/getprofiles', GetProfilesHandler, d),
            (r'/api/getprofilepicture', GetProfilePictureHandler, d),
            (r'/api/setprofilepicture', SetProfilePictureHandler, d),
            (r'/api/createprofile', CreateProfileHandler, d),
            (r'/api/deleteprofile', DeleteProfileHandler, d),
            (r'/api/getcategories', GetCategoriesHandler, d),
            (r'/api/gettop', GetTopHandler, d),
            (r'/api/getposter', GetPosterHandler, d),
            (r'/api/search', SearchHandler, d),
            (r'/api/gettitle', GetTitleHandler, d),
            (r'/api/getmediastatus', GetMediaStatusHandler, d),
            (r'/api/download', DownloadHandler, d),
            (r'/api/getvideo', GetVideoHandler, d),
        ]

