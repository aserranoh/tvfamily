
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
import importlib
import json
import logging
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


_RE_KEY = re.compile(r'[^a-zA-Z]+')

# tvfamily user and group ids
_TVFAMILY_UID = pwd.getpwnam('tvfamily').pw_uid
_TVFAMILY_GID = grp.getgrnam('tvfamily').gr_gid

# Settings file if the application is launched in non daemon (user) mode
_USER_SETTINGS_FILE = os.path.join(os.path.expanduser('~'), '.tvfamily.json')

# Settings file if the application is launched in daemon mode
_SYSTEM_SETTINGS_FILE = '/var/lib/tvfamily/settings.json'

# Defaults values for the settings
_SETTINGS_DEFAULTS = {
    # Expiracy for the IMDB cached data, in seconds (1 day)
    'imdb_cache_expiracy': 24 * 3600,
    # Torrents types filters
    'torrents_filters': [
        ['DVD-Rip', 'HDTV', 'WEB-DL', 'WEBRip', 'Blu-ray'],
        ['H.264'],
        None
    ]
}


class CoreError(Exception): pass


class Core(object):
    '''Interface with the application core.'''

    def __init__(self, options, daemon):
        self._options = options
        self._load_settings(daemon)
        self._build_torrent_engine()
        self._build_titles_db(daemon)

        # Switch to user tvfamily for security reasons
        if daemon:
            os.setgid(_TVFAMILY_GID)
            os.setuid(_TVFAMILY_UID)

    def _load_settings(self, daemon):
        '''Load the runtime settings.'''
        if daemon:
            settings_file = _SYSTEM_SETTINGS_FILE
            directory = os.path.dirname(settings_file)
            os.mkdirs(directory, exist_ok=True)
            os.chown(directory, 0, _TVFAMILY_GID)
        else:
            settings_file = _USER_SETTINGS_FILE
        self._settings = Settings(settings_file, _SETTINGS_DEFAULTS)

    def _build_torrent_engine(self):
        '''Instantiate the TorrentEngine object.'''
        try:
            # Get the path to the plugins directory
            plugins_path = self._options['plugins']['path']
            self._torrent_engine = TorrentEngine(plugins_path)
        except KeyError:
            # No plugins.path defined
            msg = 'no plugins.path defined'
            logging.error(msg)
            raise CoreError(msg)

    def _build_titles_db(self, daemon):
        '''Instantiate the TitlesDB object.'''
        try:
            path = self._options['videos']['path']
            # Define the lists of categories
            categories = self._define_categories(path, daemon)
            self._titles_db = TitlesDB(categories=categories, path=path)
        except KeyError:
            # No videos.path defined
            msg = 'no videos.path defined'
            logging.error(msg)
            raise CoreError(msg)

    def _define_categories(self, path, daemon):
        '''Define the list of caterogies.'''
        categories = [
            Category('TV Series', TVSerie, ['TV Series', 'TV Mini-Series'],
                path, self._settings),
            Category('Movies', Movie, ['Movie'], path, self._settings),
            Category('Cartoon', TVSerie, ['TV Series', 'TV Mini-Series'],
                path, self._settings),
        ]
        # Create the directories for the categories if they don't exist
        path = self._options['videos']['path']
        for c in categories:
            category_path = os.path.join(path, c.key)
            if not os.path.exists(category_path):
                os.mkdir(category_path, mode=0o755)
                if daemon:
                    os.chown(category_path, _TVFAMILY_UID, _TVFAMILY_GID)
        return categories

    # Runtime settings functions

    def get_settings(self):
        '''Return the runtime settings.'''
        return self._settings

    def update_settings(self, settings):
        '''Set new values for the settings.'''
        self._settings.update(settings)

    # Functions to navigate through the titles

    def get_categories(self):
        '''Return the list of videos categories.'''
        return self._titles_db.get_categories()

    def get_title(self, category, name):
        '''Return the title within category called name.'''
        return self._titles_db.get_title(category, name)

    @tornado.gen.coroutine
    def top(self, category):
        '''Return the top list of medias of a given category.'''
        # First, get the top list of torrents
        torrents = yield self._torrent_engine.top(
            category, self._options, self._settings['torrents_filters'])
        medias = yield self._titles_db.get_medias_from_torrents(
            torrents, category)
        return medias

    # Torrent related functions

    def get_torrents_filters(self):
        '''Return the list of quality, codec and resolution possible values.'''
        return self._torrent_engine.get_filter_values()


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


class Category(object):
    '''Represents a title category.'''

    def __init__(self, name, title_class, imdb_type, path, settings):
        # The name of the category (the value shown in the web site)
        self.name = name
        # The subclass of the titles of this category (to instantiate them)
        self.title_class = title_class
        # IMDB types associated with this category (to perform searches in
        # IMDB).
        self.imdb_type = imdb_type
        # Root path where all the videos and metadata are stored
        self.path = path
        # Global settings
        self.settings = settings
        # Machine-form version of the name of this category, used for directory
        # paths and urls.
        self.key = _RE_KEY.sub('_', name.lower())

    def get_title(self, imdb_title):
        '''Return an instance of a title in this category.'''
        cache_expiracy = self.settings['imdb_cache_expiracy']
        category_path = os.path.join(self.path, self.key)
        return self.title_class(imdb_title, category_path, cache_expiracy)

    def is_valid(self, torrent):
        '''Return True if the torrent is valid for this category of videos.'''
        return self.title_class.is_valid(torrent)


class Title(object):
    '''Base class for every type of media (movies, tv series, ...).'''

    def __init__(self, imdb_title, path, cache_expiracy=0):
        # A representation of the title in the IMDB database
        if isinstance(imdb_title, str):
            self._imdb_title = tvfamily.imdb.IMDBTitle(imdb_title)
        else:
            self._imdb_title = imdb_title
        # The path where the videos and metadata will be stored
        self._path = path
        # Value of expiracy of the cached IMDB data
        self._cache_expiracy = cache_expiracy
        # Load the cached IMDB data if present
        try:
            with open(self._cached_file, 'r') as f:
                self._imdb_title._attrs.update(json.loads(f.read()))
        except IOError: pass

    @property
    def _cached_file(self):
        return os.path.join(self._path, self._imdb_title.id + '.json')

    @property
    def name(self):
        return self._imdb_title['title']

    @property
    def poster_url(self):
        return self._imdb_title['poster_url']

    @property
    def rating(self):
        return self._imdb_title['rating']

    @tornado.gen.coroutine
    def fetch(self):
        '''Fetch the attributes from IMDB.'''
        # Check the cache
        try:
            self.check_cache(self._imdb_title._attrs)
        except (ValueError, KeyError):
            # The IMDB data must be fetched
            yield self._imdb_title.fetch()
            # Update the timestamp of the general IMDB data
            self._imdb_title._attrs['timestamp'] = time.time()
            # Save the IMDB data to the file
            self.save_imdb_data()

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
            if time.time() - element['timestamp'] > self._cache_expiracy:
                raise ValueError()

    def save_imdb_data(self):
        '''Save the IMDB data to the cache file.'''
        try:
            with open(self._cached_file, 'w') as f:
                f.write(json.dumps(self._imdb_title._attrs))
        except IOError: pass


class TVSerie(Title):
    '''Represents a TV Serie.'''

    """def get_episode(self, season, episode):
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
        return sorted(self._episodes[season].keys())"""

    def get_media(self, torrent):
        '''Return this tv series' episode related to the torrent.'''
        season = torrent.name_info['season']
        episode = torrent.name_info['episode'] 
        return Episode(self, season, episode)

    @classmethod
    def is_valid(cls, torrent):
        '''Return True if torrent contains a valid TV Series episode.'''
        return 'season' in torrent.name_info and 'episode' in torrent.name_info

    @tornado.gen.coroutine
    def fetch_season(self, season):
        '''Fetch the attributes of a season from IMDB.'''
        # Check the cache
        try:
            self.check_cache(self._imdb_title['seasons'][str(season)])
        except (ValueError, KeyError):
            # The IMDB data must be fetched
            yield self._imdb_title.fetch_season(season)
            # Update the timestamp for this season
            s = self._imdb_title['seasons'][str(season)]
            s['timestamp'] = time.time()
            # Save the IMDB data to the file
            self.save_imdb_data()

    """def get_seasons(self):
        '''Return the seasons available for this title.'''
        if self._episodes is None:
            self._add_episodes()
        return sorted(self._episodes.keys())"""


class Episode(object):
    '''Represents an episode of a tv serie.'''

    def __init__(self, title, season, episode):
        self.title = title
        self.season = season
        self.episode = episode

    def __eq__(self, other):
        '''Two episodes are the same if they are from the same title and
        are the same episode (same season and episode numbers).
        '''
        return (self.title._imdb_title.id == other.title._imdb_title.id
            and self.season == other.season and self.episode == other.episode)

    def __hash__(self):
        return hash((self.title._imdb_title.id, self.season, self.episode))

    def __str__(self):
        return '{} {}x{:02d}'.format(
            self.title.name, self.season, self.episode)

    @tornado.gen.coroutine
    def fetch(self):
        '''Fetch the information for this episode.'''
        yield self.title.fetch_season(self.season)

    @property
    def rating(self):
        try:
            db_season = self.title._imdb_title['seasons'][str(self.season)]
            db_episode = db_season[str(self.episode)]
            rating = db_episode['rating']
        except KeyError:
            rating = None
        return rating

    """def get_video(self):
        '''Return the video associated with this episode.'''
        return self._video"""


class Movie(Title):
    '''Represents a movie.'''

    def __eq__(self, other):
        '''Two movies are the same if they are the same title.'''
        return self.title._imdb_title.id == other.title._imdb_title.id

    def __hash__(self):
        return hash(self.title._imdb_title.id)

    def __str__(self):
        return self.name

    def get_media(self, torrent):
        '''Return itself.'''
        return self

    @classmethod
    def is_valid(cls, torrent):
        '''Return True if torrent contains a valid Movie.'''
        return True

    @property
    def title(self):
        return self

    """@classmethod
    def get_video(self):
        '''Return the video associated with this movie.'''
        return self._video"""


class TitlesDB(object):
    '''Titles database.'''

    # Name of the file that holds the mapping between torrent titles and IMDB
    # ids
    _IMDB_ID_CACHE = 'torrents2imdb.json'

    def __init__(self, categories, path):
        self._categories = categories
        self._dict_categories = dict((c.key, c) for c in categories)
        self._root_path = path
        # Database that maps torrents titles to IMDB ids
        self._torrents_to_imdb = None

    def get_categories(self):
        '''Return the list of categories.'''
        return self._categories

    @tornado.gen.coroutine
    def get_medias_from_torrents(self, torrents, category):
        '''Return a list of medias from a list of torrents.'''
        # Preliminary filter of torrents (for example, complete seasons)
        category = self._dict_categories[category]
        torrents = [t for t in torrents if category.is_valid(t)]
        # Get the list of titles
        titles = yield [self._fetch_title(t, category) for t in torrents]
        # Discard the titles not found
        titles = [t for t in titles if t is not None]
        # Get the media corresponding to each title
        medias = [title.get_media(torrent)
            for title, torrent in zip(titles, torrents)]
        # Remove repeated medias (keep its order)
        set_medias = set()
        final_medias = []
        for m in medias:
            if m not in set_medias:
                final_medias.append(m)
                set_medias.add(m)
        # Fetch the media IMDB data (in case of, for example, episodes,
        # fetch its individual information)
        yield [m.fetch() for m in final_medias]
        return final_medias

    @tornado.gen.coroutine
    def _fetch_title(self, torrent, category):
        '''Retrieves a title from the torrent name.'''
        # Search for the IMDB id in the cache
        try:
            imdb_id = self._get_imdb_id_from_torrent(torrent)
            # ID found, build the Title instance
            title = category.get_title(imdb_id)
        except KeyError:
            # ID not found in the cache, perform a search in the imdb site
            results = yield tvfamily.imdb.search(torrent.name_info['title'],
                category.imdb_type, torrent.name_info.get('year'))
            if len(results):
                title = category.get_title(results[0])
                self._set_imdb_id_from_torrent(torrent, results[0].id)
            else:
                title = None
                year = torrent.name_info.get('year')
                logging.warning("title not found in IMDB: '{} {}'".format(
                    torrent.name_info['title'],
                    '({})'.format(year) if year is not None else ''))
        # Fetch the IMDB data from the title
        if title is not None:
            yield title.fetch()
        return title

    def _load_torrents_to_imdb(self):
        '''Load the database that maps torrent titles to imdb ids from its
        file.
        '''
        cache_file = os.path.join(self._root_path, self._IMDB_ID_CACHE)
        try:
            with open(cache_file, 'r') as f:
                self._torrents_to_imdb = json.loads(f.read())
        except IOError:
            self._torrents_to_imdb = {}

    def _save_torrents_to_imdb(self):
        '''Write the torrents to imdb ids mapping to its file.'''
        cache_file = os.path.join(self._root_path, self._IMDB_ID_CACHE)
        with open(cache_file, 'w') as f:
            f.write(json.dumps(self._torrents_to_imdb))

    def _get_imdb_id_from_torrent(self, torrent):
        '''Return an IMDB id from a torrent name.'''
        # Load the database if necessary
        if self._torrents_to_imdb is None:
            self._load_torrents_to_imdb()
        # Get the key from the torrent name
        k = self._get_torrent_key(torrent)
        # A KeyError may be raisen if the key for this torrent is not yet
        # in the dictionary
        return self._torrents_to_imdb[k]

    def _get_torrent_key(self, torrent):
        '''Return a key to be used in the torrents_to_imdb database.'''
        k = torrent.name_info['title'].lower()
        try:
            k = '{}.{}'.format(k, str(torrent.name_info['year']))
        except KeyError: pass
        return k

    def _set_imdb_id_from_torrent(self, torrent, imdb_id):
        '''Set a pair torrent-IMDB id.'''
        k = self._get_torrent_key(torrent)
        self._torrents_to_imdb[k] = imdb_id
        self._save_torrents_to_imdb()


class TorrentEngine(object):
    '''Manages the plugins that interface with the torrents sites.
    Interface with the torrents sites (via the different plugins).
    '''

    _QUALITY_VALUES = ['Cam', 'Telesync', 'Screener', 'DVD-Rip', 'HDTV',
        'WEB-DL', 'WEBRip', 'Blu-ray']
    _CODEC_VALUES = ['XviD', 'H.264', 'H.265']
    _RESOLUTION_VALUES = ['720p', '1080p']

    _RE_QUALITY = [
        re.compile(r'(?:HD)?CAM|CamRip', re.I),
        re.compile(r'(?:HD-?)?TS|telesync', re.I),
        re.compile(r'DvDScr', re.I),
        re.compile(r'DVDRip|DVDRIP', re.I),
        re.compile(r'(?:PPV\.)?[HP]DTV|hdtv', re.I),
        re.compile(r'(?:PPV )?WEB-?DL(?: DVDRip)?|HDRip', re.I),
        re.compile(r'W[EB]BRip', re.I),
        re.compile(r'B[DR]Rip|BluRay', re.I),
    ]
    _RE_CODEC = [
        re.compile(r'xvid', re.I),
        re.compile(r'[hx]\.?264', re.I),
        re.compile(r'[hx]\.?265', re.I),
    ]
    _RE_RESOLUTION = [
        re.compile(r'720p', re.I),
        re.compile(r'1080p', re.I),
    ]

    _FILTER_QUALITY = dict(zip(_QUALITY_VALUES, _RE_QUALITY))
    _FILTER_CODEC = dict(zip(_CODEC_VALUES, _RE_CODEC))
    _FILTER_RESOLUTION = dict(zip(_RESOLUTION_VALUES, _RE_RESOLUTION))

    def __init__(self, plugins_path):
        # Path to the plugins files
        self._plugins_path = plugins_path
        # List of plugins (modules) sorted by name
        self._plugins = []

    @tornado.gen.coroutine
    def top(self, category, options, filter=None):
        '''For each plugin call its top operation. Join all the results lists
        in a single one and then sort it by number of seeders.
        filter is a tuple of lists ([qualities], [codecs], [resolutions]) with
        the accepted values for quality, codec and resolution. A None in place
        of one of the three lists means that all values are accepted.
        '''
        self._reload_plugins()
        results = yield [self._plugin_method_wrapper(p.top, category, options)
            for p in self._plugins]
        torrents = []
        for r in results:
            if r is not None:
                torrents.extend(self._filter(r, filter))
        torrents.sort(key=lambda x: x.seeders, reverse=True)
        return torrents

    def _filter(self, torrents, filter):
        '''Filter a list of torrents according to its values of quality, codec
        and resolution.
        '''
        if filter is None:
            l = torrents
        else:
            l = self._filter_by_attr(
                torrents, filter[0], 'quality', self._FILTER_QUALITY)
            l = self._filter_by_attr(l, filter[1], 'codec', self._FILTER_CODEC)
            l = self._filter_by_attr(
                l, filter[2], 'resolution', self._FILTER_RESOLUTION)
        return l

    def _filter_by_attr(self, torrents, filter, attr, dictionary):
        '''Filter a list of torrents by a given attribute.'''
        if filter is None:
            l = torrents
        else:
            l = []
            for t in torrents:
                for f in filter:
                    value = t.name_info.get(attr)
                    if value is None or dictionary[f].match(value):
                        l.append(t)
                        break
        return l

    def _reload_plugins(self):
        '''Called before each operation. Load new modules in self._plugins_path
        and unload the removed ones.
        '''
        plugins = []
        # List the current plugins in the directory and sort it by name
        # Return if the list of plugins cannot be read
        try:
            plugins_files = sorted([x for x in os.listdir(self._plugins_path)
                if x.endswith('.py') and not x.startswith('~')])
        except IOError:
            return
        plugins_names = [x.__name__ for x in self._plugins]
        # Add a sentinel to the current plugins names list
        plugins_names.append('~')
        i, j = 0, 0
        while i < len(plugins_files):
            new_plugin_name = plugins_files[i].rsplit('.', 1)[0]
            if new_plugin_name == plugins_names[j]:
                # This plugin is already loaded
                plugins.append(self._plugins[j])
                i, j = i + 1, j + 1
            elif new_plugin_name < plugins_names[j]:
                # This plugin is new, load it
                spec = importlib.util.spec_from_file_location(new_plugin_name,
                    os.path.join(self._plugins_path, plugins_files[i]))
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                plugins.append(m)
                i += 1
            else:
                # A plugin not used anymore
                j += 1
        self._plugins = plugins

    @tornado.gen.coroutine
    def _plugin_method_wrapper(self, method, *args):
        '''Wrapper to call a method of a plugin and avoid exception
        propagation.
        '''
        try:
            result = yield method(*args)
        except Exception as e:
            logging.error("in '{}.{}': {}".format(
                method.__module__, method.__name__, e))
            result = None
        return result

    def get_filter_values(self):
        '''Return the quality, codec and resolution filter values.'''
        return (self._QUALITY_VALUES, self._CODEC_VALUES,
            self._RESOLUTION_VALUES)

