
'''core.py - Implements the Core layer.

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

import datetime
import glob
import grp
import json
import os
import pwd
import re
import subprocess
import sys
import time
import tornado.gen

import tvfamily.imdb
import tvfamily.PTN

__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'
__homepage__ = 'https://github.com/aserranoh/tvfamily'


RE_KEY = re.compile(r'[^a-zA-Z]+')
TVFAMILY_UID = pwd.getpwnam('tvfamily').pw_uid
TVFAMILY_GID = grp.getgrnam('tvfamily').gr_gid
USER_SETTINGS_FILE = os.path.join(os.path.expanduser('~'), '.tvfamily')
SYSTEM_SETTINGS_FILE = '/var/lib/tvfamily/settings.json'
SETTINGS_DEFAULTS = {
    'imdb_cache_expiracy': 1,
}
SECONDS_IN_DAY = 3600 * 24


class CoreError(Exception): pass


class Core(object):
    '''Interface with the application core.'''

    def __init__(self, options, daemon):
        self._options = options
        # Build the application's logger
        self._logger = Logger()

        # Load the runtime settings
        if daemon:
            settings_file = SYSTEM_SETTINGS_FILE
            directory = os.path.dirname(settings_file)
            os.mkdirs(directory, exist_ok=True)
            os.chown(directory, 0, TVFAMILY_GID)
        else:
            settings_file = USER_SETTINGS_FILE
        self._settings = Settings(settings_file, SETTINGS_DEFAULTS)

        # Build the titles db
        # First, define the lists of categories
        try:
            self._titles_db = TitlesDB(
                categories=self._define_categories(),
                path=self._options.get_options()['videos']['path'])
        except AttributeError:
            # No videos.path defined
            self.error('no videos.path defined')
            raise

        # Switch to user tvfamily for security reasons
        if daemon:
            os.setgid(TVFAMILY_GID)
            os.setuid(TVFAMILY_UID)

    def _define_categories(self):
        '''Define the list of caterogies.'''
        categories = [
            Category('TV Series', TVSerie, ['tv_series', 'tv_miniseries'],
                self._settings),
            Category('Movies', Movie, ['feature'], self._settings),
            Category('Cartoon', TVSerie, ['tv_series', 'tv_miniseries'],
                self._settings),
        ]
        # Create the directories for the categories if they don't exist
        path = self._options.get_options()['videos']['path']
        for c in categories:
            category_path = os.path.join(path, c.key)
            if not os.path.exists(category_path):
                os.mkdir(category_path, mode=0o755)
                os.chown(category_path, TVFAMILY_UID, TVFAMILY_GID)
        return categories

    # Options functions

    def get_options(self):
        '''Return the application's options.'''
        return self._options.get_options()

    # Logging functions

    def error(self, msg):
        '''Log an error message msg.'''
        self._logger.error(msg)

    def info(self, msg):
        '''Log an info message msg.'''
        self._logger.info(msg)

    # Runtime settings functions

    def get_settings(self):
        '''Return the runtime settings.'''
        return self._settings

    def set_settings(self, settings):
        '''Set new values for the settings.'''
        self._settings.update(settings)

    # Functions to navigate through the titles

    def get_categories(self):
        '''Return the list of videos categories.'''
        return self._titles_db.get_categories()

    def get_titles(self, category):
        '''Return the list of titles of a given category.'''
        return self._titles_db.get_titles(category)

    def get_title(self, category, name):
        '''Return the title within category called name.'''
        return self._titles_db.get_title(category, name)


# TODO: implement logger functions
class Logger(object):
    '''Application logger.'''

    def error(self, msg):
        '''Logs an error message msg.'''
        print('error: {}'.format(msg), file=sys.stderr)

    def info(self, msg):
        '''Logs an info message msg.'''
        print('info: {}'.format(msg), file=sys.stderr)


class Settings(object):
    '''Store the runtime settings.'''

    def __init__(self, settings_file, defaults):
        self._settings_file = settings_file
        # If the settings file doesn't exist, create it with the default values
        try:
            with open(settings_file, 'r') as f:
                self._settings = json.loads(f.read())
        except IOError:
            self._settings = defaults.copy()
            self._save()

    def __getitem__(self, setting):
        '''Get a setting.'''
        return self._settings[setting]

    def update(self, settings):
        '''Update the settings.'''
        self._settings.update(settings)
        # Update the settings file
        self._save()

    def _save(self):
        '''Save the settings into the settings file.'''
        with open(self._settings_file, 'w') as f:
            f.write(json.dumps(self._settings))


class Category(object):
    '''Represents a video category.

    Constructor parameters:
      * name: Name (human readable) of the category.
      * title_class: Class of title to use to instantiate a title of this
          category.
    '''

    def __init__(self, name, title_class, imdb_type, settings):
        self.name = name
        self.key = RE_KEY.sub('_', name.lower())
        self.title_class = title_class
        self.imdb_type = imdb_type
        self.settings = settings

    def get_title(self, path):
        '''Return an instance for the title whose element is at path.
        '''
        try:
            return self.title_class(path, self.imdb_type,
                self.settings['imdb_cache_expiracy'])
        except TypeError:
            # The given file doesn't correspond to this category
            return None


class Video(object):
    '''Represents a video (movie or tv series episode).

    Constructor parameters:
      * path: path to the video file.
    '''

    _CHUNK_SIZE = 64 * 1024
    _EXTENSIONS = ['mp4', 'webm']
    _FFPROBE = ['ffprobe', '-v', 'error', '-show_entries',
        'stream=codec_type,codec_name:stream_tags=language,title:'
        'format=duration:format=duration', '-of', 'json']

    def __init__(self, path):
        self.path = path
        self._container = None
        self._subtitles = None

    def _get_video_info(self):
        '''Return information about the video in filename.'''
        p = subprocess.run(self._FFPROBE + [self.path], stdout=subprocess.PIPE)
        return json.loads(p.stdout.decode('utf-8'))

    @property
    def container(self):
        '''Return the video container.'''
        if not self._container:
            self._container = tvfamily.PTN.parse(
                os.path.basename(self.path))['container']
        return self._container

    def get_content(self, start=None, end=None):
        '''Return an iterator that generates the bytes from this video,
        from start to end, by chunks.
        '''
        read = 0
        to_read = self._CHUNK_SIZE
        with open(self.path, "rb") as f:
            start = start or 0
            f.seek(start)
            while end is None or start + read < end:
                if end and start + read + to_read > end:
                    to_read = end - start - read
                chunk = f.read(to_read)
                if chunk:
                    read += len(chunk)
                    yield chunk
                else:
                    if end is None:
                        return
                    assert start + read == end
                    return

    def get_duration(self):
        '''Return the duration of this video.'''
        info = self._get_video_info()
        return datetime.timedelta(seconds=float(info['format']['duration']))

    def get_mime_type(self):
        '''Return the mime type that corresponds to this video.'''
        return 'video/{}'.format(self.container)

    def get_size(self):
        '''Return the size of this video file.'''
        return os.path.getsize(self.path)

    def get_subtitles(self):
        '''Return the available subtitles for this video.'''
        filename = os.path.basename(self.path)
        basename = filename.rpartition('.')[0]
        pattern = os.path.join(
            os.path.dirname(self.path), glob.escape(basename) + '_*.vtt')
        return [Subtitle(f, len(basename)) for f in glob.iglob(pattern)]

    @classmethod
    def is_video(cls, path):
        '''Return True if the file in path corresponds to a video.'''
        return path.rpartition('.')[-1] in cls._EXTENSIONS


class Subtitle(object):
    '''Represents a subtitle for a video.

    Constructor parameters:
      * path: path to the subtitle file.
      * prefix_len: the lenght of the prefix in filename before the subtitle
          label and extension.
    '''

    def __init__(self, path, prefix_len):
        self.path = path
        self.label = os.path.basename(
            self.path)[prefix_len + 1:].rpartition('.')[0]


class Title(object):
    '''Base class for every type of media (movies, tv series, ...).

    Constructor parameters:
      * path: directory that contains this title (list of components)
      * imdb_type: type of this title in the IMDB database.
    '''

    def __init__(self, path, imdb_type, cache_expiracy):
        self.path = path
        self.imdb_type = imdb_type
        self._cache_expiracy = cache_expiracy
        # Load the title attrs if present
        try:
            with open(self.attrs_filename, 'r') as f:
                self._attrs = json.loads(f.read())
        except IOError:
            self._attrs = {}

    @property
    def filename(self):
        return os.path.basename(self.path)

    @property
    def plot(self):
        '''Return the plot of this title.'''
        return self._attrs['plot']

    @property
    def poster_url(self):
        '''Return the poster URL.'''
        return self._attrs['poster_url']

    @tornado.gen.coroutine
    def get_imdb_title(self):
        '''Return an IMDBTitle instance for this title.'''
        if 'imdb_id' not in self._attrs:
            # We don't have the IMDB index, then first we have to
            # search the item
            title = (yield tvfamily.imdb.search(
                self.title, self.imdb_type, self.year))[0]
        else:
            title = tvfamily.imdb.IMDBTitle(self._attrs)
        return title

    def save_attrs(self):
        '''Save the title attributes in the cache file.'''
        with open(self.attrs_filename, 'w') as f:
            f.write(json.dumps(self._attrs))

    @tornado.gen.coroutine
    def fetch(self):
        '''Fetch the attributes from IMDB.'''
        title = yield self.get_imdb_title()
        # Fetch all the attributes
        yield title.fetch()
        self._attrs.update(title.attrs)
        # Update the timestamp of the general attrs
        self._attrs['timestamp'] = time.time()
        # Save the attributes in the file
        self.save_attrs()

    def check_cache(self, element):
        '''Check if the database cache has expired.
        Raises KeyError if the timestamp cannot be found in the database or
        ValueError if the cache has expired.
        '''
        # If self._cache_expiracy is < 0, the cache never expires
        if self._cache_expiracy == 0:
            # Always fetch
            raise ValueError()
        elif self._cache_expiracy > 0:
            exp_time_in_seconds = self._cache_expiracy * SECONDS_IN_DAY
            if time.time() - element['timestamp'] > exp_time_in_seconds:
                raise ValueError()

    @tornado.gen.coroutine
    def get_attr(self, attr):
        '''Return the attribute attr.'''
        try:
            self.check_cache(self._attrs)
            a = self._attrs[attr]
        except (KeyError, ValueError):
            # The attribute is not present yet or it has expired
            # Fetch it from IMDB
            yield self.fetch()
            a = self._attrs[attr]
        return a

    @property
    def title(self):
        movie_info = tvfamily.PTN.parse(os.path.basename(self.path))
        return movie_info['title']

    @property
    def year(self):
        movie_info = tvfamily.PTN.parse(os.path.basename(self.path))
        return movie_info.get('year')


class TVSerie(Title):
    '''Represents a TV Serie.'''

    def __init__(self, path, imdb_type, cache_expiracy):
        super(TVSerie, self).__init__(path, imdb_type, cache_expiracy)
        # TV Series must be directories (that contain the episodes)
        if not os.path.isdir(path):
            raise TypeError("path doesn't correspond to a tv serie")
        self.path = path
        self._episodes = None

    def _add_episodes(self):
        '''Search the episodes for this tv serie.'''
        self._episodes = {}
        for filename in os.listdir(self.path):
            if Video.is_video(filename):
                # This file is a video, extract season and episode numbers
                # and create the episode instance
                episode_info = tvfamily.PTN.parse(filename)
                season_n = episode_info['season']
                episode_n = episode_info['episode']
                # Add the episode to the dictionary of episodes
                try:
                    self._episodes[season_n][episode_n] = filename
                except KeyError:
                    self._episodes[season_n] = {episode_n: filename}

    @property
    def attrs_filename(self):
        return self.path + '.json'

    def get_episode(self, season, episode):
        '''Return the given episode of this tv series.'''
        if self._episodes is None:
            self._add_episodes()
        return Episode(self, season, episode,
            os.path.join(self.path, self._episodes[season][episode]))

    def get_episodes(self, season):
        '''Return the list of avaliable episodes of a given season for this
        title.
        '''
        if self._episodes is None:
            self._add_episodes()
        return sorted(self._episodes[season].keys())

    @tornado.gen.coroutine
    def fetch_season(self, season):
        '''Fetch the attributes of a season from IMDB.'''
        title = yield self.get_imdb_title()
        # Fetch the season attributes
        yield title.fetch_season(season)
        try:
            seasons = self._attrs['seasons']
            seasons.update(title.attrs['seasons'])
        except KeyError:
            seasons = self._attrs['seasons'] = title.attrs['seasons']
        s = seasons[str(season)]
        # Update the timestamp for this season
        s['timestamp'] = time.time()
        # Save the attributes in the file
        self.save_attrs()

    @tornado.gen.coroutine
    def get_episode_attr(self, season, episode, attr):
        '''Return an attribute of the given episode of the given season of this
        tv_series.
        '''
        try:
            # The season index must be a string because in json all the keys
            # are strings
            s = self._attrs['seasons'][str(season)]
            # Check the timestamp for this season
            self.check_cache(s)
        except (KeyError, ValueError):
            # This season episodes is not cached or the cache has expired
            yield self.fetch_season(season)
            s = self._attrs['seasons'][str(season)]
        return s[str(episode)][attr]

    def get_seasons(self):
        '''Return the seasons available for this title.'''
        if self._episodes is None:
            self._add_episodes()
        return sorted(self._episodes.keys())

    def has_episodes(self):
        '''Return True if this title has episodes, so True for TVSeries.'''
        return True


class Episode(object):
    '''Represents an episode of a tv serie.

    Parameters:
      * title: reference to the title that contains this episode.
      * season: season number.
      * episode: episode number.
      * path: path to the video file (list of components)
      * filename: video file name.
    '''

    _DEFAULT_ATTRS = {'still': '/tvfamily.svg', 'plot': 'No plot.',
        'air_date': 'No air date', 'rating': 'Unrated', 'title': 'No title'}

    def __init__(self, title, season, episode, path):
        self._title = title
        self.season = season
        self.episode = episode
        self._video = Video(path)

    @tornado.gen.coroutine
    def get_attr(self, attr):
        '''Return the attribute attr.'''
        try:
            a = yield self._title.get_episode_attr(
                self.season, self.episode, attr)
        except (tornado.curl_httpclient.CurlError, KeyError):
            a = self._DEFAULT_ATTRS[attr]
        return a

    def get_video(self):
        '''Return the video associated with this episode.'''
        return self._video


class Movie(Title):
    '''Represents a movie.'''

    def __init__(self, path, imdb_type, cache_expiracy):
        super(Movie, self).__init__(path, imdb_type, cache_expiracy)
        filename = os.path.basename(path)
        # Check that the movie is of an accepted type
        if not Video.is_video(path):
            raise TypeError("path doesn't correspond to a movie")
        self.path = path
        self._video = Video(path)

    @property
    def attrs_filename(self):
        return self.path.rsplit('.', 1)[0] + '.json'

    def has_episodes(self):
        '''Return True if this title has episodes, so False for Movies.'''
        return False

    @property
    def title(self):
        movie_info = tvfamily.PTN.parse(os.path.basename(self.path))
        return movie_info['title']

    def get_video(self):
        '''Return the video associated with this movie.'''
        return self._video


class TitlesDB(object):
    '''Titles database.

    Constructor parameters:
      * categories: list of categories to organize the movies.
      * path: location where the videos are.
    '''

    def __init__(self, categories, path):
        self._categories = categories
        self._dict_categories = dict((c.key, c) for c in categories)
        self._root_path = path

    def get_categories(self):
        '''Return the list of categories.'''
        for c in self._categories:
            yield c

    def get_title(self, category, name):
        '''Return the title within the given category and called name.'''
        filename = os.path.join(self._root_path, category, name)
        return self._dict_categories[category].get_title(filename)

    def get_titles(self, category):
        '''Return the list of titles of a given category.'''
        category_path = os.path.join(self._root_path, category)
        for f in sorted(os.listdir(category_path)):
            filename = os.path.join(category_path, f)
            t = self._dict_categories[category].get_title(filename)
            if t:
                yield t

