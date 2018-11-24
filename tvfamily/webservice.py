
'''webservice.py - Implements the Web Service layer.

Copyright 2018 Antonio Serrano Hernandez

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
__copyright__ = 'Copyright (C) 2018 Antonio Serrano Hernandez'
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

class GetProfileImageHandler(tvfamily.webcommon.BaseHandler):
    '''Return the image for the given profile.'''

    def get(self):
        try:
            name = self.get_query_argument('name')
            self.set_header('Content-Type', 'image/png')
            img = self._core.get_profile_image(name)
            self.write(img.read())
            img.close()
        except tornado.web.MissingArgumentError:
            self.write_error(msg="missing 'name' argument")
        except KeyError as e:
            self.write_error(msg=str(e))

class SetProfileImageHandler(tvfamily.webcommon.BaseHandler):
    '''Set the image for the given profile.'''

    _ACCEPTED_MIME_TYPES = ['image/png', 'image/jpg']

    def post(self):
        try:
            name = self.get_query_argument('name')
            img = self.request.files['file'][0]
            mime = img['content_type']
            body = img['body']
            if body and mime not in self._ACCEPTED_MIME_TYPES:
                self.write_error(
                    msg='image format {} not supported'.format(mime))
            else:
                try:
                    self._core.set_profile_image(name, body)
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
        self.write_json(
            categories=[c.name for c in self._core.get_categories()])

class GetTopHandler(tvfamily.webcommon.BaseHandler):
    '''Return the top list of medias of a given category.'''

    async def get(self):
        try:
            category = self.get_query_argument('category')
            medias = await self._core.top(category)
            self.write_json(top=[m.todict() for m in medias])
        except tornado.web.MissingArgumentError:
            self.write_error(msg="missing 'category' argument")
        except tvfamily.CoreError as e:
            self.write_error(msg=str(e))

class GetTitleHandler(tvfamily.webcommon.BaseHandler):
    '''Serve the title information.'''

    async def get(self):
        category = self.get_query_argument('category')
        imdb_id = self.get_query_argument('title')
        title = await self._core.get_title(category, imdb_id)
        self.write(json.dumps(title.tojson()))


class WebService(object):
    '''Represents the web service API.'''

    def __init__(self, core):
        self._core = core

    def get_handlers(self):
        d = {'core': self._core}
        return [
            (r'/api/getprofiles', GetProfilesHandler, d),
            (r'/api/getprofileimage', GetProfileImageHandler, d),
            (r'/api/setprofileimage', SetProfileImageHandler, d),
            (r'/api/createprofile', CreateProfileHandler, d),
            (r'/api/deleteprofile', DeleteProfileHandler, d),
            (r'/api/getcategories', GetCategoriesHandler, d),
            (r'/api/gettop', GetTopHandler, d),
        ]

