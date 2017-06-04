#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import print_function, division, unicode_literals

import os
import json
import logging
from io import BytesIO
from hashlib import sha256
from collections import defaultdict, namedtuple
from unicodedata import normalize
from operator import itemgetter

from cached_property import cached_property
from mutagen.id3._id3v1 import find_id3v1
from mutagen.mp3 import MP3, BitrateMode
from mutagen.id3 import ID3
import acoustid
from readchar import readchar

from _constants import tag_name_map, compilation_indicators
from log_handling import LogManager
from alchemy_db import AlchemyDatabase, DBTable

# V1_Tags: {"TIT2":"Title", "TPE1":"Artist", "TALB":"Album", "TDRC":"Year", "COMM":"Comment", "TRCK":"Track", "TCON":"Genre"}

"""
info_columns = ["bitrate", "bitrate_kbps", "bitrate_mode", "channels", "encoder_info", "length", "sample_rate", "sketchy", "time"]
db_columns = ["path", "modified", "size", "sha256", "audio_sha256", "tags"] + info_columns + ["v1", "v2", "tag_mismatches"]
"""

NoTagVal = (None,)
primary_tags = {"TIT2": "Title", "TPE1": "Artist", "TALB": "Album", "TDRC": "Year", "TRCK": "Track"}
default_replacement_db = "/var/tmp/music_deduper_tag_replacements.db"


class TagReplacementDB:
    _instance = None
    class __metaclass__(type):
        @property
        def instance(cls):
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def __init__(self, db_path=None):
        self.lm = LogManager.get_instance()
        self.db = AlchemyDatabase.get_db(db_path or default_replacement_db, logger=self.lm)

    def __getitem__(self, tag_id):
        if tag_id not in self.db:
            self.db.add_table(tag_id, [("original", "TEXT"), ("correct", "TEXT")], "original")
        return self.db[tag_id].simple


class MusicFile:
    info_copy_keys = ["bitrate", "bitrate_mode", "channels", "encoder_info", "length", "sample_rate", "sketchy"]
    bitrate_modes = {getattr(BitrateMode, attr).real: attr for attr in dir(BitrateMode) if attr.isupper()}
    db_attr_keymap = {"v1_ver": "v1", "v2_ver": "v2", "audio_hash": "audio_sha256", "full_hash": "sha256", "size": "size", "modified": "modified"}

    def __init__(self, file_path, dbrow=None):
        self.file_path = file_path
        self.tags_modified = False
        self.v1_ver = None
        self.v2_ver = None
        self.lm = LogManager.get_instance()
        self.tag_repl_db = TagReplacementDB.instance

        if dbrow is None:
            try:
                stat = os.stat(self.file_path)
            except Exception as e:
                raise MusicFileOpenException("Unable to open {}: {}".format(self.file_path, e), e)
            else:
                self.size = int(stat.st_size)
                self.modified = int(stat.st_mtime)
        else:
            RawInfo = namedtuple("RawInfo", self.info_copy_keys)
            self._raw_info = RawInfo(**{k: dbrow[k] for k in self.info_copy_keys})
            self.__dict__.update({attr: dbrow[key] for attr, key in self.db_attr_keymap.iteritems()})
            self.tag_dict = json.loads(dbrow["tags"])

    @cached_property
    def content(self):
        with open(self.file_path, "rb") as mfile:
            return BytesIO(mfile.read())

    @cached_property
    def mp3(self):
        return MP3(self.content)

    @cached_property
    def id3_versions(self):
        return tuple(self.tags.keys())

    @cached_property
    def audio_hash(self):
        self.content.seek(0)
        content = BytesIO(self.content.read())
        ID3().delete(content)
        content.seek(0)
        return sha256(content.read()).hexdigest()

    @cached_property
    def full_hash(self):
        self.content.seek(0)
        return sha256(self.content.read()).hexdigest()

    @cached_property
    def true_file(self):
        return ID3(self.file_path)

    @cached_property
    def _raw_info(self):
        return self.mp3.info

    @cached_property
    def info(self):
        raw_info = self._raw_info
        info = {key: getattr(raw_info, key) for key in self.info_copy_keys}
        info["bitrate_kbps"] = raw_info.bitrate // 1000
        try:
            info["bitrate_mode"] = raw_info.bitrate_mode
        except AttributeError:
            info["bitrate_mode"] = self.bitrate_modes[raw_info.bitrate_mode.real]
        info["bitrate_readable"] = "{} kbps {}".format(info["bitrate_kbps"], info["bitrate_mode"])
        info["time"] = self._ftime(raw_info.length)
        info["info"] = "{time} @ {bitrate_readable}, {sample_rate} Hz [{channels} channels, encoded by {encoder_info}]".format(**info)
        return info

    @cached_property
    def tags(self):
        if "tag_dict" in self.__dict__:
            del self.__dict__["tag_dict"]   #invalidate cached tag_dict

        if self.mp3.tags is None:
            return {}

        if self.mp3.tags.unknown_frames:
            unknown_frames = {frame[:4]: frame[4:] for frame in self.mp3.tags.unknown_frames}
            for ufid in unknown_frames:
                if ufid not in tag_name_map:
                    self.lm.warning("{}: Found unknown frames: {}".format(self.file_path, self.mp3.tags.unknown_frames))
                    break
            #raise UnknownFrameException("Found unknown frames: {}".format(self.mp3.tags.unknown_frames))

        tags = {}
        if self.mp3.tags.version[0] == 2:
            v1_tags = self._get_v1_tags()[0]
            if v1_tags is not None:
                tags["1.1"] = v1_tags
                self.v1_ver = "1.1"

        tag_dict = defaultdict(list)
        for tid, frame in self.mp3.tags.iteritems():
            if ":" in tid:                          #Unique IDs for frames that can occur more than once contain ":"
                tag_dict[type(frame).__name__].append(frame)
            else:
                tag_dict[tid] = frame
        tag_ver = ".".join(map(str, self.mp3.tags.version))
        tags[tag_ver] = tag_dict
        setattr(self, "v{}_ver".format(self.mp3.tags.version[0]), tag_ver)
        return tags

    def _get_v1_tags(self):
        return find_id3v1(self.content)

    @classmethod
    def tag_val(cls, frame):
        if type(frame).__name__ == "COMM":
            return frame.text
        else:
            return frame._pprint()

    @cached_property
    def tag_dict(self):
        """
        Generates a dict of tag IDs and representations of their values, based on the tag's _pprint() method (the non-
        private version returns the ID as well)

        View _pprint methods:
        for class in `egrep '\(Frame\):' _frames.py | awk '{print $2}'`; do echo class $class; clazz=`echo $class | sed -r 's/([\\(\\)])/\\\\\1/g'`; sed -nr "/class $clazz/,/class /p" _frames.py | head -n-1 | sed -nr '/_pprint/,/def /p'; done

        :return dict: mapping of id3_version:dict(frame_id:value(s))
        """
        tag_dict = {}
        for ver, tags in self.tags.iteritems():
            tag_dict[ver] = {}
            for key, value in tags.iteritems():
                if isinstance(value, list):
                    if len(value) == 1:
                        tag_dict[ver][key] = self.tag_val(value[0])
                    else:
                        tag_dict[ver][key] = [self.tag_val(val) for val in value]
                else:
                    tag_dict[ver][key] = self.tag_val(value)
        return tag_dict

    def tag_dict_by_id(self):
        tags_by_id = defaultdict(lambda: defaultdict(lambda: ""))
        for ver, tags in self.tag_dict.iteritems():
            for tagid, val in tags.iteritems():
                tags_by_id[tagid][ver] = val
        return tags_by_id

    def __getitem__(self, item):
        if len(self.tag_dict) < 1:
            raise KeyError(item)
        elif (self.v1_ver is None) or (self.v2_ver is None):
            return self.tag_dict[self.v1_ver or self.v2_ver][item]
        elif item not in self.tag_dict[self.v1_ver]:
            return self.tag_dict[self.v2_ver][item]
        elif item not in self.tag_dict[self.v2_ver]:
            return self.tag_dict[self.v1_ver][item]

        v1_val = self.tag_dict[self.v1_ver][item]
        v2_val = self.tag_dict[self.v2_ver][item]
        if (v1_val == v2_val) or (v2_val.startswith(v1_val)):
            return v2_val

        if item == "TRCK":
            if "/" in v2_val:
                try:
                    v1_value = int(v1_val)
                    v2_value = int(v2_val.split("/")[0])
                except ValueError:
                    pass
                else:
                    if v1_value == v2_value:
                        return v2_val
            else:
                try:
                    v1_value = int(v1_val)
                    v2_value = int(v2_val)
                except ValueError:
                    pass
                else:
                    if v1_value == v2_value:
                        return "{}".format(v2_value)

        for val in (v1_val, v2_val):
            try:
                return self.tag_repl_db[item][val]
            except KeyError:
                pass

        msg = "{}/{}:{{[{}]'{}' != [{}]'{}'}}".format(item, tag_name_map.get(item, "?"), self.v1_ver, v1_val, self.v2_ver, v2_val)
        raise TagVersionMismatchException(msg, v1_val, v2_val)

    def prompting_get_tag(self, tag_id, *args, **kwargs):
        """
        :param tag_id: ID of the tag to get
        :param default: Default value to use if the tag is not present
        """
        try:
            val = self.get_tag(tag_id, *args, **kwargs)
        except KeyError as e:
            if args:
                return args[0]
            elif "default" in kwargs:
                return kwargs["default"]
            raise e
        except TagVersionMismatchException as e:
            print("Pick a {}/{} tag version for {}".format(tag_id, tag_name_map.get(tag_id, "?"), self.file_path))
            print("[{}] {}".format(self.v1_ver, e.v1))
            print("[{}] {}".format(self.v2_ver, e.v2))
            print("[s] skip | [x] exit")
            inpt = None
            while not inpt:
                inpt = readchar()
                if (inpt == "x") or (ord(inpt) == 3):
                    raise KeyboardInterrupt()
                elif inpt in ("s", "S"):
                    raise e
                elif inpt not in ("1", "2"):
                    print("Invalid input; enter 1 or 2 to make a choice, s to skip, or x to exit")
                    inpt = None
            if inpt == "1":
                self.tag_repl_db[tag_id][e.v2] = e.v1
                return e.v1
            self.tag_repl_db[tag_id][e.v1] = e.v2
            return e.v2
        else:
            return val

    def get_tag(self, tag_id, *args, **kwargs):
        """
        :param tag_id: ID of the tag to get
        :param default: Default value to use if the tag is not present
        """
        try:
            val = self[tag_id]
        except KeyError as e:
            if args:
                return args[0]
            elif "default" in kwargs:
                return kwargs["default"]
            raise e
        else:
            return val

    def __contains__(self, item):
        try:
            self[item]
        except KeyError:
            return False
        except TagVersionMismatchException:
            pass
        return True

    @cached_property
    def compilation(self):
        if "TCMP" in self:
            return True

        # compare normalized artist/album names against compilation indicators
        # Write better normalization function based on unicode cookbooks

    def get_primary_tags(self):
        tags = {}
        mismatches = []
        for id, readable in primary_tags.iteritems():
            try:
                tags[readable] = self.get_tag_value(id)
            except TagVersionMismatchException as e:
                mismatches.append(e.args[0])

        if len(mismatches) > 0:
            raise TagVersionMismatchException(", ".join(mismatches))
        return tags

    def get_mismatch_keys(self):
        if (self.v1_ver is None) or (self.v2_ver is None):
            return []
        mismatches = []
        for tid, v1_val in self.tag_dict[self.v1_ver].iteritems():
            v2_val = self.tag_dict[self.v2_ver].get(tid, None)
            if (v2_val != v1_val) and (not isinstance(v2_val, unicode) or not v2_val.startswith(v1_val)):
                mismatches.append(tid)
        return mismatches

    @classmethod
    def _ftime(cls, seconds):
        if isinstance(seconds, (str, unicode)):
            return seconds
        m, s = divmod(abs(int(round(seconds))), 60)
        h, m = divmod(m, 60)
        return "{}{:02d}:{:02d}".format("{:02d}:".format(h) if h > 0 else "", m, s)

    def save_tags(self, keep_v1=True, v2_version=3):
        """

        :param keep_v1:
        :param v2_version:
        :return:
        """
        if v2_version not in (3, 4):
            raise ValueError("v2_version must be 3 or 4, not {}".format(v2_version))
        do_save = self.tags_modified
        id3_versions = self.get_id3_versions()

        if (v2_version == 3) and ("2.3.0" not in id3_versions):
            do_save = True
            self.true_file.update_to_v23()
        elif keep_v1 and ("1.1" not in id3_versions):
            do_save = True

        if do_save:
            logging.debug("Saving changes to {}".format(self.file_path))
            self.true_file.save(v1=1 if keep_v1 else 0, v2=v2_version)
        else:
            logging.debug("Not changed: {}".format(self.file_path))

    @cached_property
    def fingerprint(self):
        """
        :return tuple: duration, fingerprint
        """
        return acoustid.fingerprint_file(self.file_path)


def _normalize(val):
    if not val:
        return val
    elif isinstance(val, (str, unicode)):
        return val.lower().replace(" ", "")
    return val


"""
http://musicbrainz.org/ws/2/recording/24739ddc-22ac-4247-9b2c-edca45e40a23?fmt=json&inc=artist-credits+releases
acoustid results -> .results[].recordings[].id = musicbrainz recording id
"""


class AcoustidDB:
    lookup_meta = "recordings releasegroups"

    def __init__(self, db_path="/var/tmp/acoustid_info.db", apikey=None):
        if apikey is None:
            keyfile_path = os.path.expanduser("~/acoustid_apikey.txt")
            try:
                with open(keyfile_path, "r") as keyfile:
                    apikey = keyfile.read()
            except OSError as e:
                raise AcoustidKeyfileException("An API key is required; unable to find or read {}".format(keyfile_path))
        self.apikey = apikey

        self.lm = LogManager.get_instance()
        self.db = AlchemyDatabase.get_db(db_path, logger=self.lm)
        self.acoustids = DBTable(self.db, "acoustid_responses", [("id", "TEXT"), ("resp", "PickleType")], "id")
        self.artists = DBTable(self.db, "artists", [("id", "TEXT"), ("name", "TEXT"), ("album_ids", "PickleType")], "id")
        self.albums = DBTable(self.db, "albums", [("id", "TEXT"), ("title", "TEXT"), ("artist_ids", "PickleType"), ("types", "PickleType"), ("track_ids", "PickleType")], "id")
        self.tracks = DBTable(self.db, "tracks", [("id", "TEXT"), ("title", "TEXT"), ("duration", "INTEGER"), ("artist_ids", "PickleType"), ("album_ids", "PickleType")], "id")

    def _fetch_lookup(self, duration, fingerprint, meta=None):
        return acoustid.lookup(self.apikey, fingerprint, duration, meta or self.lookup_meta)

    def _lookup(self, duration, fingerprint):
        dbkey = json.dumps([duration, fingerprint])
        if dbkey in self.acoustids:
            #logging.debug("Found in Acoustid DB: ({}, {})".format(duration, fingerprint))
            return self.acoustids[dbkey]["resp"]
        #logging.debug("Not found in Acoustid DB - looking up: ({}, {})".format(duration, fingerprint))
        resp = self._fetch_lookup(duration, fingerprint)
        self.acoustids.insert([dbkey, resp])
        self._process_resp(resp)
        return resp

    def register(self, entity_type, entity_id, *args):
        try:
            if entity_id not in self.db[entity_type]:
                self.db[entity_type].insert([entity_id] + list(args))
        except KeyError:
            raise ValueError("Invalid entity table: {}".format(entity_type))

    def _process_resp(self, resp):
        for result in resp["results"]:
            logging.debug("Processing result {}".format(result["id"]))
            for recording in result["recordings"]:
                logging.debug("Processing recording {}".format(recording["id"]))
                artist_ids = set()
                for artist in recording["artists"]:
                    logging.debug("Processing artist {}".format(artist["id"]))
                    self.register("artists", artist["id"], artist["name"], set())
                    artist_ids.add(artist["id"])
                alb_ids = set()
                for album in recording["releasegroups"]:
                    logging.debug("Processing album {}".format(album["id"]))
                    alb_artist_ids = set()
                    for alb_artist in album.get("artists", {}):
                        logging.debug("Processing album artist {}".format(alb_artist["id"]))
                        self.register("artists", alb_artist["id"], alb_artist["name"], set())
                        self.artists[alb_artist["id"]]["album_ids"].add(album["id"])
                        alb_artist_ids.add(alb_artist["id"])

                    album_types = set()
                    if "type" in album:
                        album_types.add(album["type"])
                    if "secondarytypes" in album:
                        album_types.update(album["secondarytypes"])

                    if "title" in album:
                        self.register("albums", album["id"], album["title"], alb_artist_ids, album_types, set())
                        self.albums[album["id"]]["track_ids"].add(recording["id"])
                        alb_ids.add(album["id"])
                self.register("tracks", recording["id"], recording["title"], recording["duration"], artist_ids, alb_ids)

    def get_track(self, track_id):
        try:
            track = self.tracks[track_id]
        except KeyError:
            raise ValueError("Track ID not found: {}".format(track_id))
        resp = {k: track[k] for k in ("id", "title", "duration")}
        resp["artists"] = {aid: self.get_artist_name(aid) for aid in track["artist_ids"]}
        resp["albums"] = [self.get_album(aid) for aid in track["album_ids"]]
        return resp

    def get_album(self, album_id):
        try:
            album = self.albums[album_id]
        except KeyError:
            raise ValueError("Album ID not found: {}".format(album_id))
        resp = {k: album[k] for k in ("id", "title", "type")}
        resp["artists"] = {aid: self.get_artist_name(aid) for aid in album["artist_ids"]}
        return resp

    def get_artist_name(self, artist_id):
        try:
            return self.artists[artist_id]["name"]
        except KeyError:
            raise ValueError("Artist ID not found: {}".format(artist_id))

    def lookup(self, duration, fingerprint):
        results = self._lookup(duration, fingerprint)["results"]
        best = max(results, key=itemgetter("score"))

        """
        Score albums based on...
        album artist matches song artist: +100
        track count == 1: -25
        country == "US": + 10
        title contains remix or greatest hits: -25
        """

        best_ids = [rec["id"] for rec in best["recordings"]]
        if len(best_ids) > 1:
            logging.warning("Found multiple recordings in best result with score {}: {}".format(best["score"], ", ".join(best_ids)))

        return self.get_track(best_ids[0])


class AcoustidKeyfileException(Exception):
    pass


class MusicFileOpenException(Exception):
    pass


class UnknownFrameException(Exception):
    pass


class TagVersionMismatchException(Exception):
    def __init__(self, msg, v1=None, v2=None, *args, **kwargs):
        super(TagVersionMismatchException, self).__init__(msg, *args, **kwargs)
        self.v1 = v1
        self.v2 = v2


class NoTagsFoundException(Exception):
    pass
