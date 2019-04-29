
'''core.py - Implements the Core layer.

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

import datetime
import glob
import grp
import importlib
import io
import json
import logging
import os
import PIL.Image
import pwd
import re
import sys
import time
import tornado.gen

import tvfamily.imdb
import tvfamily.PTN
import tvfamily.torrent

__author__ = 'Antonio Serrano Hernandez'
__copyright__ = 'Copyright (C) 2018 2019 Antonio Serrano Hernandez'
__version__ = '0.1'
__license__ = 'GPL'
__maintainer__ = 'Antonio Serrano Hernandez'
__email__ = 'toni.serranoh@gmail.com'
__status__ = 'Development'
__homepage__ = 'https://github.com/aserranoh/tvfamily'


# tvfamily user and group ids
_TVFAMILY_UID = pwd.getpwnam('tvfamily').pw_uid
_TVFAMILY_GID = grp.getgrnam('tvfamily').gr_gid

_DAEMON_DATA_PATH = '/var/lib/tvfamily'
_USER_DATA_PATH = os.path.join(os.path.expanduser('~'), '.tvfamily')
# TODO: put the real static path
#STATIC_PATH = '/usr/share/tvfamily'
STATIC_PATH = os.path.join(os.path.dirname(sys.argv[0]), '..', 'data')

# Defaults values for the user settings
_SETTINGS_DEFAULTS = {
    # Expiracy for the IMDB cached data, in seconds (1 day)
    'imdb_cache_expiracy': 24 * 3600,
    # Torrents types filters
    'torrents_filters': [
        ['DVD-Rip', 'HDTV', 'WEB-DL', 'WEBRip', 'Blu-ray'],
        ['H.264'],
        ['720p', '1080p'],
        [],
    ]
}


class CoreError(Exception): pass


class Core(object):
    '''Interface with the application core.'''

    def __init__(self, options, daemon):
        self._options = options
        logging.basicConfig(level=logging.INFO)
        if daemon:
            data_path = _DAEMON_DATA_PATH
        else:
            data_path = _USER_DATA_PATH
        # Make sure data_path exists and has the correct permissions
        self._create_data_path(data_path, daemon)
        self._options = options
        self._profiles_manager = ProfilesManager(data_path, STATIC_PATH)
        self._build_titles_db(data_path, daemon)
        self._torrent_engine = TorrentEngine(data_path, options)
        self._scheduler = TaskScheduler(options['server']['tasks_interval'],
            self._titles_db, self._torrent_engine, data_path)

        # Switch to user tvfamily for security reasons
        if daemon:
            os.setgid(_TVFAMILY_GID)
            os.setuid(_TVFAMILY_UID)

    def _create_data_path(self, data_path, daemon):
        '''Create the data_path if it doesn't exist yet.'''
        if not os.path.isdir(data_path):
            os.mkdir(data_path)
        if daemon:
            os.chown(directory, 0, _TVFAMILY_GID)

    def _build_titles_db(self, data_path, daemon):
        '''Instantiate the TitlesDB object.'''
        try:
            videos_path = self._options['videos']['path']
            # Define the lists of categories
            categories = self._define_categories()
            self._titles_db = TitlesDB(categories, videos_path, data_path)
        except KeyError:
            # No videos.path defined
            msg = 'no videos.path defined'
            logging.error(msg)
            raise CoreError(msg)

    def _define_categories(self):
        '''Define the list of caterogies.'''
        return [Category(*c) for c in [
            ('TV Series', ['TV Series', 'TV Mini-Series']),
            ('Movies', ['Movie'])
        ]]

    # Profile functions

    def get_profiles(self):
        '''Return the list of profiles.'''
        return self._profiles_manager.get_profiles()

    def get_profile_picture(self, name):
        '''Return the picture for the given profile.'''
        return self._profiles_manager.get_profile_picture(name)

    def set_profile_picture(self, name, picture=None):
        '''Set a new profile picture for the given profile.'''
        self._profiles_manager.set_profile_picture(name, picture)

    def create_profile(self, name, picture=None):
        '''Create a new profile.'''
        self._profiles_manager.create_profile(name, picture)

    def delete_profile(self, name):
        '''Delete a profile.'''
        self._profiles_manager.delete_profile(name)

    # Functions to list the medias

    def get_categories(self):
        '''Return the list of videos categories.'''
        return self._titles_db.get_categories_names()

    def top(self, profile, category):
        '''Return the top list of medias of a given category.'''
        # Get the user settings
        settings = self._profiles_manager[profile].settings
        filters = settings['torrents_filters']
        # Get the top list of torrents
        category = self._titles_db.get_category(category)
        torrents = self._torrent_engine.top(category, filters)
        return self._titles_db.get_medias_from_torrents(torrents)

    def get_poster(self, imdb_id):
        '''Return the poster of a given title.'''
        return self._titles_db.get_poster(imdb_id)

    async def search(self, category, text):
        '''Search titles by name in IMDB.'''
        return (await self._titles_db.search(category, text))

    def get_title(self, imdb_id):
        '''Return the title with the given imdb_id.'''
        return self._titles_db.get_title(imdb_id)

    def get_media_status(self, imdb_id, season=None, episode=None):
        '''Return the status of a given media (downloaded, downloading or
        missing).
        '''
        if self._titles_db.has_file(imdb_id, season, episode):
            return MediaStatus(MediaStatus.DOWNLOADED)
        else:
            status = self._torrent_engine.get_file_status(
                imdb_id, season, episode)
            if status:
                return status
            else:
                return MediaStatus(MediaStatus.MISSING)

    # Scheduler functions

    async def run_scheduler(self):
        '''Start the scheduler.'''
        await self._scheduler.run()

    # Torrent related functions

    """def get_torrents_filters(self):
        '''Return the list of quality, codec and resolution possible values.'''
        return self._torrent_engine.get_filter_values()"""

    # Video related methods

    def get_video(self, imdb_id, season=None, episode=None):
        '''Return a Video object from a title_id.'''
        return self._titles_db.get_video(imdb_id, season, episode)

    """async def get_video_from_media(self, media):
        '''Search a video in the local machine corresponding to this media
        (a movie or a tv episode).
        '''
        return (await self._titles_db.get_video_from_media(media))"""


class ProfilesManager(object):
    '''Manage the user profiles.'''

    _PROFILES_DIR = 'profiles'
    _PROFILES_FILE = 'profiles.json'
    _PROFILE_PICTURE_SIZE = (256, 256)

    def __init__(self, data_dir, static_dir):
        self._profiles_path = os.path.join(data_dir, self._PROFILES_DIR)
        # Make sure the self._profiles_path exists
        self._create_profiles_path()
        try:
            self._load()
        except IOError:
            self._profiles = {}

    def __getitem__(self, name):
        '''Return a profile given its name.'''
        try:
            return self._profiles[name]
        except KeyError:
            raise KeyError("profile '{}' not found".format(name))

    def _create_profiles_path(self):
        '''Create the profiles path if it doesn't exist yet.'''
        if not os.path.isdir(self._profiles_path):
            os.mkdir(self._profiles_path)

    def _get_profiles_file(self):
        '''Return the full path of the profiles JSON file.'''
        return os.path.join(self._profiles_path, self._PROFILES_FILE)

    def _load(self):
        '''Load the profiles from the file.'''
        with open(self._get_profiles_file(), 'r') as f:
            self._profiles = dict((p['name'], UserProfile(**p))
                for p in json.loads(f.read()))

    def get_profiles(self):
        '''Return the list of profiles.'''
        return sorted(self._profiles.values(), key=lambda p: p.name)

    def get_profile_picture(self, name):
        '''Return the picture for the given profile.'''
        if name not in self._profiles:
            raise KeyError("profile '{}' not found".format(name))
        picture_path = os.path.join(self._profiles_path, name + '.png')
        try:
            return open(picture_path, 'rb')
        except IOError:
            return None

    def set_profile_picture(self, name, picture=None):
        '''Set a new picture for the given profile.'''
        if name not in self._profiles:
            raise KeyError("profile '{}' not found".format(name))
        if not picture:
            # Default picture selected. Delete previous picture, if any
            try:
                picture_path = os.path.join(self._profiles_path, name + '.png')
                os.unlink(picture_path)
            except OSError: pass
        else:
            self._save_profile_picture(name, picture)

    def create_profile(self, name, picture=None):
        '''Create a new profile with the given name.'''
        if name not in self._profiles:
            if picture:
                self._save_profile_picture(name, picture)
            self._profiles[name] = UserProfile(name)
            self._save()
        else:
            raise ValueError('a profile with this name already exists')

    def _save_profile_picture(self, name, picture):
        '''Save a picture to be used as a profile picture.'''
        # First try to open it with pillow
        try:
            pic = PIL.Image.open(io.BytesIO(picture))
        except IOError:
            raise IOError('profile picture format unsupported')
        # Resize it to 256x256
        pic = pic.resize(self._PROFILE_PICTURE_SIZE)
        # Save the new picture
        try:
            picture_path = os.path.join(self._profiles_path, name + '.png')
            pic.save(picture_path)
        except IOError as e:
            raise IOError('cannot write profile picture: {}'.format(e))

    def delete_profile(self, name):
        '''Delete the profile with the given name.'''
        try:
            # Delete the profile picture if any
            picture_path = os.path.join(self._profiles_path, name + '.png')
            try:
                os.unlink(picture_path)
            except OSError:
                pass
            del self._profiles[name]
            self._save()
        except KeyError:
            raise KeyError("profile '{}' not found".format(name))

    def _save(self):
        '''Save the profiles into the file.'''
        try:
            with open(self._get_profiles_file(), 'w') as f:
                f.write(json.dumps([p.todict()
                    for p in self._profiles.values()]))
        except IOError as e:
            logging.warning('cannot save profiles: {}'.format(e))


class UserProfile(object):
    '''Store information about the user profile.'''

    def __init__(self, name, settings=_SETTINGS_DEFAULTS):
        self.name = name
        self.settings = settings

    def todict(self):
        '''Return a dictionary with this object's information.'''
        return {'name': self.name, 'settings': self.settings}


class Category(object):
    '''Represents a title category.'''

    _RE_KEY = re.compile(r'[^a-zA-Z]+')

    def __init__(self, name, imdb_type):
        # The name of the category (the value shown in the web site)
        self.name = name
        # IMDB types associated with this category (to perform searches in
        # IMDB).
        self.imdb_type = imdb_type

    def get_id(self):
        '''Return a canonical form of this category's name.'''
        return self._RE_KEY.sub('_', self.name.lower())


class TitlesDB(object):
    '''Titles database.'''

    # Name of the file that holds the mapping between torrent titles and IMDB
    # ids
    TORRENTS_TO_IMDB_FILE = 'torrents2titles.json'

    # Name of the titles not found file
    TITLES_NOT_FOUND_FILE = 'notfound.json'

    # Name of the IMDBTitle database files
    TITLE_DB_FILE = 'db.json'

    # Accepted videos
    VIDEO_EXTENSIONS = ['mp4']

    def __init__(self, categories, videos_path, data_path):
        self._categories = dict((c.name, c) for c in categories)
        self._root_path = videos_path
        # Give the videos path to the Title class
        self._data_path = data_path
        self._load_torrents_to_imdb()
        self._load_titles_not_found()

    def _get_torrents_to_imdb_file(self):
        '''Return torrents to imdb id file.'''
        return os.path.join(self._data_path, self.TORRENTS_TO_IMDB_FILE)

    def _get_titles_not_found_file(self):
        '''Return the titles not found file.'''
        return os.path.join(self._data_path, self.TITLES_NOT_FOUND_FILE)

    def get_category(self, category):
        '''Return a category by its name.'''
        return self._categories[category]

    def get_categories_names(self):
        '''Return a list with the names of the categories.'''
        return sorted(self._categories.keys())

    def get_medias_from_torrents(self, torrents):
        '''Return a list of medias from a list of torrents.'''
        # Get the list of titles
        titles = [self._get_title_from_torrent_cached(t)
            for t in torrents]
        # Discard the titles not found
        titles_torrents = [(tit, tor) for tit, tor in zip(titles, torrents)
            if tit is not None]
        # Get the media corresponding to each title
        medias = [title.get_media(torrent)
            for title, torrent in titles_torrents]
        # Remove repeated medias and null ones (keep its order)
        set_medias = set()
        final_medias = []
        for m in medias:
            if m is not None:
                if m not in set_medias:
                    final_medias.append(m)
                    set_medias.add(m)
        return final_medias

    def _get_title_from_torrent_cached(self, torrent):
        '''Retrieves a title from the torrent name.'''
        try:
            torrent_key = self._get_torrent_key(torrent)
            imdb_id = self._torrents_to_imdb[torrent_key]
            # ID found, build the Title instance
            title = self.get_title(imdb_id)
        except KeyError:
            title = None
        return title

    async def fetch_title_from_torrent(self, torrent, category):
        '''Fetch a title from a torrent.'''
        # Get the title
        imdb_title = await self._get_title_from_torrent(torrent, category)
        if imdb_title is not None:
            await self._imdb_title_fetch_and_save(imdb_title)
        return imdb_title

    async def _imdb_title_fetch_and_save(
            self, imdb_title, fetch_pictures=True):
        '''Fetch the information of an imdb title and store it.'''
        # Fetch the IMDB data from the title
        # title_path is the destination where to save the images
        title_path = self._get_title_path(imdb_title.id)
        self._create_db_path(title_path)
        await imdb_title.fetch(title_path if fetch_pictures else None)
        # Save the dbs to disk
        self._save_imdb_title(imdb_title, title_path)

    async def _get_title_from_torrent(self, torrent, category):
        '''Retrieves a title from the torrent name.'''
        imdb_title = None
        try:
            torrent_key = self._get_torrent_key(torrent)
            imdb_id = self._torrents_to_imdb[torrent_key]
            # ID found, build the Title instance
            imdb_title = tvfamily.imdb.IMDBTitle(imdb_id)
        except KeyError:
            # ID not found in the cache
            # If it is in the 'not found' list, don't look any further
            if torrent_key not in self._titles_not_found:
                results = await tvfamily.imdb.search(
                    torrent.name_info['title'], category.imdb_type,
                    torrent.name_info.get('year'))
                if len(results):
                    imdb_title = results[0]
                    self._torrents_to_imdb[torrent_key] = results[0].id
                else:
                    # Put the key in the 'not found' list
                    self._titles_not_found.add(torrent_key)
        return imdb_title

    def _load_imdb_title(self, imdb_id):
        '''Load an IMDBTitle info from its id.'''
        db_path = os.path.join(self._root_path, imdb_id, self.TITLE_DB_FILE)
        with open(db_path, 'r') as f:
            attrs = json.loads(f.read())
        return tvfamily.imdb.IMDBTitle(imdb_id, attrs)

    def _create_db_path(self, title_path):
        '''Create the path to store the information of a title.'''
        if not os.path.exists(title_path):
            os.mkdir(title_path)

    def _save_imdb_title(self, imdb_title, title_path):
        '''Save the IMDB info to disk.'''
        db_path = os.path.join(title_path, self.TITLE_DB_FILE)
        try:
            with open(db_path, 'w') as f:
                f.write(json.dumps(imdb_title._attrs))
        except IOError: pass

    def _get_title_path(self, title_id):
        '''Return the path where the information of a title is stored.'''
        return os.path.join(self._root_path, title_id)

    def _load_torrents_to_imdb(self):
        '''Load the database that maps torrent titles to imdb ids from its
        file.
        '''
        try:
            with open(self._get_torrents_to_imdb_file(), 'r') as f:
                self._torrents_to_imdb = json.loads(f.read())
        except IOError:
            self._torrents_to_imdb = {}

    def _save_torrents_to_imdb(self):
        '''Write the torrents to imdb ids mapping to its file.'''
        with open(self._get_torrents_to_imdb_file(), 'w') as f:
            f.write(json.dumps(self._torrents_to_imdb))

    def _get_torrent_key(self, torrent):
        '''Return a key to be used in the torrents_to_imdb database.'''
        k = torrent.name_info['title'].lower()
        try:
            k = '{}.{}'.format(k, str(torrent.name_info['year']))
        except KeyError: pass
        return k

    def get_title(self, imdb_id):
        '''Return a title given its imdb_id.'''
        try:
            return Title(self._load_imdb_title(imdb_id))
        except IOError:
            raise KeyError('title with imdb_id {} not found'.format(imdb_id))

    def get_poster(self, imdb_id):
        '''Return a file descriptor to the poster image for this title.'''
        title = self.get_title(imdb_id)
        title_path = os.path.join(self._root_path, title.imdb_title.id)
        base_name = title.get_poster_url().rpartition('/')[-1]
        try:
            f = open(os.path.join(title_path, base_name), 'rb')
        except IOError:
            base_name = title.get_poster_url_small().rpartition('/')[-1]
            try:
                f = open(os.path.join(title_path, base_name), 'rb')
            except IOError:
                f = None
        return f

    def _load_titles_not_found(self):
        '''Load the list of titles not found in IMDB.'''
        try:
            with open(self._get_titles_not_found_file(), 'r') as f:
                self._titles_not_found = set(json.loads(f.read()))
        except IOError:
            self._titles_not_found = set()

    def _save_titles_not_found(self):
        '''Write the list of titles not found in IMDB to its file.'''
        with open(self._get_titles_not_found_file(), 'w') as f:
            f.write(json.dumps(list(self._titles_not_found)))

    def save_databases(self):
        '''Save databases to disk.'''
        self._save_torrents_to_imdb()
        self._save_titles_not_found()

    async def search(self, category, text):
        '''Search titles by name in IMDB.'''
        category = self._categories[category]
        results = await tvfamily.imdb.search(text, category.imdb_type)
        await tornado.gen.multi(
            [self._imdb_title_fetch_and_save(x, False) for x in results])
        titles = [Title(x) for x in results]
        return titles

    def has_video(self, title_id, season=None, episode=None):
        '''Return True if the file for this media is downloaded.'''
        return self.get_video(title_id, season, episode) is not None

    def get_video(self, imdb_id, season=None, episode=None):
        '''Return the video in the local machine, if any, for this media.'''
        path = self._get_title_path(imdb_id)
        if os.path.exists(path):
            if len(self.VIDEO_EXTENSIONS) == 1:
                videos_wilcard = '*.{}'.format(self.VIDEO_EXTENSIONS[0])
            else:
                videos_wilcard = '*.{{{}}}'.format(
                    ','.join[self.VIDEO_EXTENSIONS])
            videos = glob.glob(os.path.join(path, videos_wilcard))
            video = None
            if videos:
                if season is None or episode is None:
                    video = Video(videos[0])
                else:
                    for v in videos:
                        info = tvfamily.PTN.parse(os.path.basename(v))
                        try:
                            s, e = info['season'], info['episode']
                            if s == season and e == episode:
                                video = Video(v)
                                break
                        except KeyError:
                            pass
        else:
            raise KeyError('Unknown media')
        return video


class Video(object):
    '''Represents a video (movie or tv series episode).'''

    _CHUNK_SIZE = 64 * 1024

    def __init__(self, path):
        self.path = path

    """@property
    def container(self):
        '''Return the video container.'''
        if not self._container:
            self._container = tvfamily.PTN.parse(
                os.path.basename(self.path))['container']
        return self._container"""

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

    """def get_mime_type(self):
        '''Return the mime type that corresponds to this video.'''
        return 'video/{}'.format(self.container)"""

    def get_size(self):
        '''Return the size of this video file.'''
        return os.path.getsize(self.path)

    """def get_subtitles(self):
        '''Return the available subtitles for this video.'''
        filename = os.path.basename(self.path)
        basename = filename.rpartition('.')[0]
        pattern = os.path.join(
            os.path.dirname(self.path), glob.escape(basename) + '_*.vtt')
        return [Subtitle(f, len(basename)) for f in glob.iglob(pattern)]

    @classmethod
    def is_video(cls, path):
        '''Return True if the file in path corresponds to a video.'''
        return path.rpartition('.')[-1] in cls._EXTENSIONS"""


"""class Subtitle(object):
    '''Represents a subtitle for a video.'''

    def __init__(self, path, prefix_len):
        self.path = path
        self.label = os.path.basename(
            self.path)[prefix_len + 1:].rpartition('.')[0]"""


class Title(object):
    '''Represents a title (a movie or tv series).'''

    videos_path = None

    def __init__(self, imdb_title):
        self.imdb_title = imdb_title
        if self.imdb_title['type'] in Movie.TYPES:
            self.type = Movie(self)
        else:
            self.type = TVSerie(self)

    def __eq__(self, other):
        '''Two episodes are the same if they are from the same title and
        are the same episode (same season and episode numbers).
        '''
        return self.imdb_title.id == other.imdb_title.id

    def __hash__(self):
        return hash(self.imdb_title.id)

    def get_air_year(self):
        return self.imdb_title['air_year']

    def get_end_year(self):
        try:
            return self.imdb_title['end_year']
        except KeyError:
            return None

    def get_genre(self):
        return self.imdb_title['genre']

    def get_media(self, torrent):
        '''Return the media that represents this torrent.'''
        return self.type.get_media(torrent)

    def get_plot(self):
        return self.imdb_title.get('plot')

    def get_poster_url(self):
        return self.imdb_title['poster_url']

    def get_poster_url_small(self):
        return self.imdb_title['poster_url_small']

    def get_rating(self):
        return self.imdb_title.get('rating')

    def get_title(self):
        return self.imdb_title['title']

    def todict(self):
        '''Return a dictionary with some of the attributes of this instance.'''
        d = {'title': self.get_title(), 'title_id': self.imdb_title.id,
            'rating': self.get_rating(), 'air_year': self.get_air_year(),
            'end_year': self.get_end_year(), 'genre': self.get_genre(),
            'plot': self.get_plot()}
        d.update(self.type.todict())
        return d


class TVSerie(object):
    '''Represents a TV Serie.'''

    TYPES = ['TV Series', 'TV Mini-Series']

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

    def __init__(self, title):
        self.title = title

    def get_media(self, torrent):
        '''Return this tv series' episode related to the torrent.'''
        try:
            season = torrent.name_info['season']
            episode = torrent.name_info['episode']
            # Verify that this season and episode exists
            e = self.title.imdb_title['seasons'][str(season)][str(episode)]
            return Episode(self.title, season, episode)
        except KeyError:
            return None

    """def has_episodes(self):
        '''Always return True (a tv series has episodes).'''
        return True

    def get_seasons(self):
        '''Return the seasons available for this title.'''
        if self._episodes is None:
            self._add_episodes()
        return sorted(self._episodes.keys())"""

    def todict(self):
        # Add season and episode number fields to each episode
        seasons = self.title.imdb_title['seasons']
        for sn, episodes in seasons.items():
            for en, e in episodes.items():
                e['season'] = int(sn)
                e['episode'] = int(en)
        return {'seasons': self.title.imdb_title['seasons']}


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
        return (self.title == other.title
            and self.season == other.season and self.episode == other.episode)

    def __hash__(self):
        return hash((self.title.imdb_title.id, self.season, self.episode))

    """def __str__(self):
        return '{} {}x{:02d}'.format(
            self.title.get_title(), self.season, self.episode)"""

    """def get_rating(self):
        try:
            db_season = self.title._imdb_title['seasons'][str(self.season)]
            db_episode = db_season[str(self.episode)]
            rating = db_episode['rating']
        except KeyError:
            rating = None
        return rating"""

    def todict(self):
        '''Return a dictionary with some of the attributes of this instance.'''
        d = self.title.todict()
        d.update({'season': self.season, 'episode': self.episode})
        return d


class Movie(object):
    '''Represents a movie.'''

    TYPES = ['Movie']

    def __init__(self, title):
        self.title = title

    def get_media(self, torrent):
        '''Return itself.'''
        return self.title

    def todict(self):
        return {}

    """def get_duration(self):
        return self._imdb_title['duration']

    def has_episodes(self):
        '''Always return False (a movie doesn't have episodes).'''
        return False

    def get_all_videos_paths(self):
        '''Return all the videos in the same path than this movie.'''
        videos = [os.path.join(self.path, f) for f in os.listdir(self.path)]
        return [f for f in videos if Video.is_video(f)]

    def get_video(self, path):
        '''Return the local video corresponding to this movie.'''
        return Video(path)"""


class MediaStatus(object):
    '''Return the on disk status of a media.'''

    DOWNLOADED = 0
    DOWNLOADING = 1
    MISSING = 2

    def __init__(self, status, progress=None):
        self.status = status
        self.progress = progress

    def todict(self):
        return {'status': self.status, 'progress': self.progress}


class TorrentEngine(object):
    '''Manages the plugins that interface with the torrents sites.
    Interface with the torrents sites (via the different plugins).
    '''

    _QUALITY_VALUES = ['Cam', 'Telesync', 'Telecine', 'Screener', 'DVD-Rip',
        'HDTV', 'WEB-DL', 'WEBRip', 'Blu-ray']
    _CODEC_VALUES = ['XviD', 'H.264', 'H.265']
    _RESOLUTION_VALUES = ['720p', '1080p']
    _3D_VALUES = ['3D']

    _RE_QUALITY = [
        re.compile(r'(?:HD)?CAM|CamRip', re.I),
        re.compile(r'(?:HD-?)?TS|telesync', re.I),
        re.compile(r'(?:HD-?)?TC|telecine', re.I),
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

    def __init__(self, data_path, options):
        self.data_path = data_path
        # Path to the plugins files
        self._plugins_path = options['plugins']['path']
        # List of plugins (modules) sorted by name
        self._plugins = []
        # Global options
        self._options = options

    def top(self, category, filters):
        '''Return the filtered list of top torrents for a given category.

        The list of torrents is extracted from the cached file.
        '''
        filename = self._get_torrents_list_file(category)
        try:
            with open(filename, 'r') as f:
                torrents = [tvfamily.torrent.Torrent(**t)
                    for t in json.loads(f.read())]
        except IOError:
            torrents = []
        # Filter and sort the list of torrents
        return sorted(self._filter(torrents, filters),
            key=lambda x: x.seeders, reverse=True)

    def _get_torrents_list_file(self, category):
        '''Return the name of the file that contains the list of torrents of
        a given category.
        '''
        return os.path.join(
            self.data_path, 'torrents-{}.json'.format(category.get_id()))

    def _filter(self, torrents, filters):
        '''Filter a list of torrents according to its values of quality, codec,
        resolution and 3D.
        '''
        if filters is None:
            l = torrents
        else:
            quality, codec, resolution, _3d = filters
            l = self._filter_from_attr(
                torrents, quality, 'quality', self._FILTER_QUALITY)
            l = self._filter_from_attr(l, codec, 'codec', self._FILTER_CODEC)
            l = self._filter_from_attr(
                l, resolution, 'resolution', self._FILTER_RESOLUTION)
            l = [t for t in l if _3d is None
                or not t.name_info.get('3d', False) or '3D' in _3d]
        return l

    def _filter_from_attr(self, torrents, filter, attr, dictionary):
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

    async def fetch_top(self, category):
        '''Fetch the top list of torrents for a given category.'''
        self._reload_plugins()
        results = await tornado.gen.multi([self._plugin_method_wrapper(
            p.top, category.name, self._options) for p in self._plugins])
        # Flatten the list of torrents
        torrents = []
        for r in results:
            if r is not None:
                torrents.extend(r)
        # Dump the list of torrents into a file
        if torrents:
            filename = self._get_torrents_list_file(category)
            with open(filename, 'w') as f:
                f.write(json.dumps([t.todict() for t in torrents]))
        return torrents

    def _reload_plugins(self):
        '''Called before each operation. Load new modules in plugins_path
        and unload the removed ones.
        '''
        try:
            plugins = []
            # Get the plugins path
            plugins_path = self._options['plugins']['path']
            # List the current plugins in the directory and sort it by name
            # Return if the list of plugins cannot be read
            plugins_files = sorted([x for x in os.listdir(plugins_path)
                if x.endswith('.py') and not x.startswith('~')])
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
                    plugin_file = os.path.join(plugins_path, plugins_files[i])
                    # TODO: Error loading this plugin
                    spec = importlib.util.spec_from_file_location(
                        new_plugin_name, plugin_file)
                    m = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(m)
                    plugins.append(m)
                    i += 1
                else:
                    # A plugin not used anymore
                    j += 1
        except KeyError:
            logging.error('cannot reload torrent plugins: '
                'plugins path not defined')
        except IOError as e:
            logging.error('cannot list plugins in {}: {}'.format(
                plugins_path, e))
        self._plugins = plugins

    async def _plugin_method_wrapper(self, method, *args):
        '''Wrapper to call a method of a plugin and avoid exception
        propagation.
        '''
        try:
            result = await method(*args)
        except Exception as e:
            logging.error("in '{}.{}': {}".format(
                method.__module__, method.__name__, e))
            result = None
        return result

    def get_filter_values(self):
        '''Return the quality, codec and resolution filter values.'''
        return (self._QUALITY_VALUES, self._CODEC_VALUES,
            self._RESOLUTION_VALUES, self._3D_VALUES)

    async def search(self, query):
        '''Search torrents by string.'''
        self._reload_plugins()
        results = await tornado.gen.multi(
            [self._plugin_method_wrapper(p.search, query, self._options)
            for p in self._plugins])
        torrents = []
        for r in results:
            if r is not None:
                torrents.extend(self._filter(r))
        torrents.sort(key=lambda x: x.seeders, reverse=True)
        return torrents

    def get_file_status(self, imdb_id, season=None, episode=None):
        '''Return the downloading status of a file.'''
        return None


class TaskScheduler(object):
    '''Executes periodic tasks.'''

    TITLES_TORRENTS_FILE = 'titles2torrents.json'

    def __init__(self, interval, titles_db, torrents_engine, data_path):
        self.interval = datetime.timedelta(seconds=interval)
        self.titles_db = titles_db
        self.torrents_engine = torrents_engine
        self.data_path = data_path

    async def run(self):
        next_execution = datetime.datetime.now()
        while 1:
            start = time.time()
            # Execute tasks here (_fetch_torrents is a cascade task)
            """await self._fetch_top_torrents()
            # End tasks
            self.titles_db.save_databases()"""
            logging.info('finished tasks in {} seconds'.format(
                int(time.time() - start)))
            # Compute the next execution time
            next_execution += self.interval
            # Compute the time to sleep
            sleep_interval = next_execution - datetime.datetime.now()
            await tornado.gen.sleep(sleep_interval.total_seconds())

    async def _fetch_top_torrents(self):
        '''Fetch the top lists of torrents for all the categories.'''
        categories = [self.titles_db.get_category(c)
            for c in self.titles_db.get_categories_names()]
        torrents = await tornado.gen.multi(
            [self._fetch_torrents_of_category(c) for c in categories])

    async def _fetch_torrents_of_category(self, category):
        '''Fetch the list of torrents for a given category.'''
        # Fetch list of torrents
        torrents = await self.torrents_engine.fetch_top(category)
        # Then fetch the title that corresponds to each torrent
        await tornado.gen.multi(
            [self.titles_db.fetch_title_from_torrent(t, category)
            for t in torrents])

