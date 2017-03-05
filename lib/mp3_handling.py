#!/usr/bin/env python2

from __future__ import print_function, division, unicode_literals

import os
import logging
from io import BytesIO
from hashlib import sha256
from mutagen.id3._id3v1 import find_id3v1
from mutagen.mp3 import MP3, BitrateMode
from mutagen.id3 import ID3
from cached_property import cached_property
from collections import defaultdict

# V1_Tags: {"TIT2":"title", "TPE1":"Artist", "TALB":"Album", "TDRC":"Year", "COMM":"Comment", "TRCK":"Track", "TCON":"Genre"}


class MusicFile:
    info_copy_keys = ["bitrate", "channels", "encoder_info", "length", "sample_rate", "sketchy"]
    bitrate_modes = {getattr(BitrateMode, attr).real: attr for attr in dir(BitrateMode) if attr.isupper()}

    def __init__(self, file_path):
        self.file_path = file_path
        self.tags_modified = False
        try:
            stat = os.stat(self.file_path)
        except Exception as e:
            raise MusicFileOpenException("Unable to open {}: {}".format(self.file_path, e), e)
        else:
            self.size = int(stat.st_size)
            self.modified = int(stat.st_mtime)

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
    def info(self):
        raw_info = self.mp3.info
        info = {key: getattr(raw_info, key) for key in self.info_copy_keys}
        info["bitrate_kbps"] = raw_info.bitrate // 1000
        info["bitrate_mode"] = self.bitrate_modes[raw_info.bitrate_mode.real]
        info["bitrate_readable"] = "{} kbps {}".format(info["bitrate_kbps"], info["bitrate_mode"])
        info["time"] = self._ftime(raw_info.length)
        info["info"] = "{time} @ {bitrate_readable}, {sample_rate} Hz [{channels} channels, encoded by {encoder_info}]".format(**info)
        return info

    @cached_property
    def tags(self):
        if self.mp3.tags.unknown_frames:
            raise UnknownFrameException("Found unknown frames: {}".format(self.mp3.tags.unknown_frames))

        tags = {}
        if self.mp3.tags.version[0] == 2:
            v1_tags = self._get_v1_tags()[0]
            if v1_tags is not None:
                tags["1.1"] = v1_tags

        tag_dict = defaultdict(list)
        for tid, frame in self.mp3.tags.iteritems():
            if ":" in tid:                          #Unique IDs for frames that can occur more than once contain ":"
                tag_dict[type(frame).__name__].append(frame)
            else:
                tag_dict[tid] = frame
        tags[".".join(map(str, self.mp3.tags.version))] = tag_dict
        return tags

    def _get_v1_tags(self):
        return find_id3v1(self.content)

    def get_tag_dict(self):
        """
        Generates a dict of tag IDs and representations of their values, based on the tag's _pprint() method (the non-
        private version returns the ID as well)

        :return dict: mapping of id3_version:dict(frame_id:value(s))
        """
        tag_dict = {}
        for ver, tags in self.tags.iteritems():
            tag_dict[ver] = {}
            for key, value in tags.iteritems():
                if isinstance(value, list):
                    tag_dict[ver][key] = [val._pprint() for val in value]
                else:
                    tag_dict[ver][key] = value._pprint()
        return tag_dict

    @classmethod
    def _ftime(cls, seconds):
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


class MusicFileOpenException(Exception):
    pass


class UnknownFrameException(Exception):
    pass
