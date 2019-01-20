
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
        except tornado.web.MissingArgumentError:
            self.write_error(msg="missing 'name' argument")
        except KeyError as e:
            self.write_error(msg=str(e))

class SetProfilePictureHandler(tvfamily.webcommon.BaseHandler):
    '''Set the picture for the given profile.'''

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

class GetTitleHandler(tvfamily.webcommon.BaseHandler):
    '''Serve the title information.'''

    def get(self):
        try:
            title_id = self.get_query_argument('id')
            title = self._core.get_title(title_id)
            self.write_json(title=title.todict())
        except (tornado.web.MissingArgumentError, KeyError) as e:
            self.write_error(msg=str(e))

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
            (r'/api/gettitle', GetTitleHandler, d),
        ]

