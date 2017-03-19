#!/usr/bin/env python2

from __future__ import print_function, division, unicode_literals

import os
import json
import logging
from io import BytesIO
from hashlib import sha256
from cached_property import cached_property
from collections import defaultdict, namedtuple
from mutagen.id3._id3v1 import find_id3v1
from mutagen.mp3 import MP3, BitrateMode
from mutagen.id3 import ID3

from _constants import tag_name_map, compilation_indicators
from log_handling import LogManager

# V1_Tags: {"TIT2":"Title", "TPE1":"Artist", "TALB":"Album", "TDRC":"Year", "COMM":"Comment", "TRCK":"Track", "TCON":"Genre"}

"""
info_columns = ["bitrate", "bitrate_kbps", "bitrate_mode", "channels", "encoder_info", "length", "sample_rate", "sketchy", "time"]
db_columns = ["path", "modified", "size", "sha256", "audio_sha256", "tags"] + info_columns + ["v1", "v2", "tag_mismatches"]
"""

NoTagVal = (None,)
primary_tags = {"TIT2":"Title", "TPE1":"Artist", "TALB":"Album", "TDRC":"Year", "TRCK":"Track"}


class MusicFile:
    info_copy_keys = ["bitrate", "channels", "encoder_info", "length", "sample_rate", "sketchy"]
    bitrate_modes = {getattr(BitrateMode, attr).real: attr for attr in dir(BitrateMode) if attr.isupper()}
    db_attr_keymap = {"v1_ver": "v1", "v2_ver": "v2", "audio_hash": "audio_sha256", "full_hash": "sha256", "size": "size", "modified": "modified"}

    def __init__(self, file_path, dbrow=None):
        self.file_path = file_path
        self.tags_modified = False
        self.v1_ver = None
        self.v2_ver = None
        self.lm = LogManager.get_instance()

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
        if v1_val == v2_val:
            return v2_val

        msg = "{}/{}:{{[{}]'{}' != [{}]'{}'}}".format(item, tag_name_map.get(item, "?"), self.v1_ver, v1_val, self.v2_ver, v2_val)
        raise TagVersionMismatchException(msg)

    def get_tag(self, tag_id, *args):
        try:
            val = self[tag_id]
        except KeyError as e:
            if args:
                return args[0]
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


def _normalize(val):
    if not val:
        return val
    elif isinstance(val, (str, unicode)):
        return val.lower().replace(" ", "")
    return val


class MusicFileOpenException(Exception):
    pass


class UnknownFrameException(Exception):
    pass


class TagVersionMismatchException(Exception):
    pass


class NoTagsFoundException(Exception):
    pass
