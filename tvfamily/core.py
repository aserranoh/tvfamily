
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

import glob
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

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


class Core(object):
    '''Interface with the application core.

    Constructor parameters:
      * options_file: the options file.
      * daemon: True if in daemon mode, False if in user mode.
    '''

    def __init__(self, options_file, daemon):
        # Load the application's options from the file
        self._options = Options(options_file)

        # Build the application's logger
        self._logger = Logger()

        # Build the titles db
        # First, define the lists of categories
        try:
            self._titles_db = TitlesDB(
                categories=self._define_categories(),
                path=self._options.get_root_option().videos.path)
        except AttributeError:
            # No videos.path defined
            self.error('no videos.path defined')
            raise

        # Build the streams manager
        self._streams_manager = StreamsManager()

    def _define_categories(self):
        '''Define the list of caterogies.'''
        return [
            Category('TV Series', TVSerie),
            Category('Movies', Movie),
            #Category('Cartoon'),
        ]

    # Options functions

    def get_options(self):
        '''Return the application's options.'''
        return self._options.get_root_option()

    # Logging functions

    def error(self, msg):
        '''Log an error message msg.'''
        self._logger.error(msg)

    def info(self, msg):
        '''Log an info message msg.'''
        self._logger.info(msg)

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

    # Functions to manage streams

    def new_stream(self, video):
        '''Create a new stream to watch a video.'''
        return self._streams_manager.new_stream(video)

    def get_stream(self, stream_id):
        '''Return the stream identified by stream_id.'''
        return self._streams_manager.get_stream(stream_id)


class Option(object):
    '''Stores a tree of options.

    The suboptions are accessible trough the attributes of this instance.
    '''

    def __init__(self):
        self._has_subopts = False

    def add_suboption(self, name, value):
        '''Add a suboption called name and with value.

        Value may be a string or an Option object (so that the options are
        nested). The suboption will be accessible through the attributes of
        the parent option.
        '''
        setattr(self, name, value)
        self._has_subopts = True

    def has_suboptions(self):
        '''Return True if this option has any suboptions.'''
        return self._has_subopts


class Options(object):
    '''Manages configuration options.

    Constructor parameters:
      * options_file: the XML file that contains the options.
    '''

    _DEFAULT_OPTIONS = '''<?xml version="1.0"?>
<tvfamily-options>
  <server port="8888"/>
</tvfamily-options>
'''

    def __init__(self, options_file):
        try:
            # Try to read the options from the options file
            tree = ET.parse(options_file).getroot()
        except:
            # If the options file cannot be read, use the default options
            tree = ET.fromstring(self._DEFAULT_OPTIONS)
        self._root = Option()
        for child in tree:
            self._build_option(self._root, child)

    def _build_option(self, parent, xml):
        '''Recursively build the tree of options from an xml tree.
        Insert the new option as a child of the parent option.
        '''
        o = Option()
        # Add the attributes of the xml node to the option
        for attrib, value in xml.attrib.items():
            o.add_suboption(attrib, value)
        # Add the children of the xml node to the option
        for child in xml:
            self._build_option(o, child)
        # If the option has any attributes, add it to the parent
        if o.has_suboptions():
            parent.add_suboption(xml.tag, o)
        # If the option has not any suboption, add the text of the xml node
        # as the option
        else:
            parent.add_suboption(xml.tag, xml.text)

    def get_root_option(self):
        '''Return the root option that contains the hierarchy of optopns.'''
        return self._root


# TODO: implement logger functions
class Logger(object):
    '''Application logger.'''

    def error(self, msg):
        '''Logs an error message msg.'''
        print('error: {}'.format(msg), file=sys.stderr)

    def info(self, msg):
        '''Logs an info message msg.'''
        print('info: {}'.format(msg), file=sys.stderr)


class Category(object):
    '''Represents a video category.

    Constructor parameters:
      * name: Name (human readable) of the category.
      * title_class: Class of title to use to instantiate a title of this
          category.
    '''

    def __init__(self, name, title_class):
        self.name = name
        self.key = RE_KEY.sub('_', name.lower())
        self.title_class = title_class

    def get_title(self, path):
        '''Return an instance for the title whose element is at path.
        '''
        try:
            return self.title_class(path)
        except TypeError:
            # The given file doesn't correspond to this category
            return None


class Video(object):
    '''Represents a video (movie or tv series episode).

    Constructor parameters:
      * path: path to the video file.
    '''

    _EXTENSIONS = ['.mp4']

    def __init__(self, path):
        self.path = path
        self._container = None
        self._subtitles = None

    def get_container(self):
        '''Return the container type of this video file.'''
        if not self._container:
            self._container = tvfamily.PTN.parse(
                os.path.basename(self.path))['container']
        return self._container

    def get_size(self):
        '''Return the size of this video file.'''
        return os.path.getsize(self.path)

    def get_subtitles(self):
        '''Return the available subtitles for this video.'''
        filename = os.path.basename(self.path)
        basename = filename.rpartition('.')[0]
        pattern = os.path.join(
            os.path.dirname(self.path), glob.escape(basename) + '_*.vtt')
        for f in glob.iglob(pattern):
            yield Subtitle(f, len(basename))

    @classmethod
    def is_video(cls, path):
        '''Return True if the file in path corresponds to a video.'''
        for e in cls._EXTENSIONS:
            if path.endswith(e):
                return True
        return False


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
      * id: id of this title in the database.
      * path: directory that contains this title (list of components)
    '''

    def __init__(self, path):
        self.path = path


class TVSerie(Title):
    '''Represents a TV Serie.

    Constructor parameters:
      * path: the path to the TV Show (a list of components).
      * title: the name of the title.
      * id: id of this title in the database.
    '''

    def __init__(self, path):
        super(TVSerie, self).__init__(path)
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
    def filename(self):
        return os.path.basename(self.path)

    def get_episode(self, season, episode):
        '''Return the given episode of this tv series.'''
        if self._episodes is None:
            self._add_episodes()
        return Episode(season, episode,
            os.path.join(self.path, self._episodes[season][episode]))

    def get_episodes(self, season):
        '''Return the list of avaliable episodes of a given season for this
        title.
        '''
        if self._episodes is None:
            self._add_episodes()
        return sorted(self._episodes[season].keys())

    def get_seasons(self):
        '''Return the seasons available for this title.'''
        if self._episodes is None:
            self._add_episodes()
        return sorted(self._episodes.keys())

    def has_episodes(self):
        '''Return True if this title has episodes, so True for TVSeries.'''
        return True

    @property
    def title(self):
        return os.path.basename(self.path)


class Episode(object):
    '''Represents an episode of a tv serie.

    Parameters:
      * season: season number.
      * episode: episode number.
      * path: path to the video file (list of components)
      * filename: video file name.
    '''

    def __init__(self, season, episode, path):
        self.season = season
        self.episode = episode
        self._video = Video(path)

    def get_video(self):
        '''Return the video associated with this episode.'''
        return self._video


class Movie(Title):
    '''Represents a movie.

    Constructor parameters:
      * path: path to the movie.
    '''

    def __init__(self, path):
        super(Movie, self).__init__()
        filename = os.path.basename(path)
        # Check that the movie is of an accepted type
        found = False
        for e in self._MOVIE_EXTENSIONS:
            if filename.endswith(e):
                found = True
                break
        if not found:
            raise TypeError("path doesn't correspond to a movie")
        # Get the name of the movie from its file name
        movie_info = tvfamily.PTN.parse(filename)
        self._filename_title = movie_info['title']


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


class StreamsManager(object):
    '''Contains the streams currently being reproduced.'''

    def __init__(self):
        self._streams = {}
        self._next_stream_id = 0

    def get_stream(self, stream_id):
        '''Return the stream identified by stream_id.'''
        return self._streams[stream_id]

    def new_stream(self, video):
        '''Create a new stream from a video and return it.'''
        container = video.get_container()
        if container in ['mp4', 'webm']:
            stream = FileStream(self._next_stream_id, video)
        else:
            raise NotImplementedError()
        self._streams[stream.id] = stream
        self._next_stream_id += 1
        return stream


class FileStream(object):
    '''A video stream straight from a file.

    Constructor parameters:
      * id: identifier for this stream.
      * video: source file for this stream.
    '''

    _CHUNK_SIZE = 64 * 1024

    def __init__(self, id, video):
        self.id = id
        self._video = video

    def get_content(self, start=None, end=None):
        '''Return an iterator that generates the bytes from this video,
        from start to end, by chunks.
        '''
        read = 0
        to_read = self._CHUNK_SIZE
        with open(self._video.path, "rb") as f:
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

    def get_mime_type(self):
        '''Return the mime type that corresponds to this video.'''
        return 'video/{}'.format(self._video.get_container())

    def get_size(self):
        '''Return the size of the video file.'''
        return self._video.get_size()

