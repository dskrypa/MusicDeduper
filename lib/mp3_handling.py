#!/usr/bin/env python2

from __future__ import print_function, division

import os
from io import BytesIO
from hashlib import sha256
from mutagen.id3._id3v1 import find_id3v1
from mutagen.mp3 import MP3, BitrateMode
from mutagen.id3 import ID3

# V1_Tags: {"TIT2":"title", "TPE1":"Artist", "TALB":"Album", "TDRC":"Year", "COMM":"Comment", "TRCK":"Track", "TCON":"Genre"}


class MusicFile:
    info_copy_keys = ["bitrate", "channels", "encoder_info", "length", "sample_rate", "sketchy"]
    bitrate_modes = {getattr(BitrateMode, attr).real: attr for attr in dir(BitrateMode) if attr.isupper()}

    def __init__(self, file_path):
        self.file_path = file_path
        self.content = None
        self.mp3 = None
        self.tags = None
        self.audio_hash = None
        self.full_hash = None
        self.info = None
        try:
            stat = os.stat(self.file_path)
        except Exception as e:
            raise MusicFileOpenException("Unable to open {}: {}".format(self.file_path, e), e)
        else:
            self.size = int(stat.st_size)
            self.modified = int(stat.st_mtime)

    def get_content(self):
        if self.content is None:
            with open(self.file_path, "rb") as mfile:
                self.content = BytesIO(mfile.read())
        return self.content

    @classmethod
    def ftime(cls, seconds):
        m, s = divmod(abs(int(round(seconds))), 60)
        h, m = divmod(m, 60)
        return "{}{:02d}:{:02d}".format("{:02d}:".format(h) if h > 0 else "", m, s)

    def get_summary(self):
        return {"info": self.get_info(), "tags": self.get_tags()}

    def get_mp3(self):
        if self.mp3 is None:
            self.mp3 = MP3(self.get_content())
        return self.mp3

    def get_info(self):
        if self.info is None:
            raw_info = self.get_mp3().info
            info = {key: getattr(raw_info, key) for key in self.info_copy_keys}
            info["bitrate_kbps"] = raw_info.bitrate // 1000
            info["bitrate_mode"] = self.bitrate_modes[raw_info.bitrate_mode.real]
            info["bitrate_readable"] = "{} kbps {}".format(info["bitrate_kbps"], info["bitrate_mode"])
            info["time"] = self.ftime(raw_info.length)
            info["info"] = "{time} @ {bitrate_readable}, {sample_rate} Hz [{channels} channels, encoded by {encoder_info}]".format(**info)
            self.info = info
        return self.info

    @classmethod
    def extract_tag_value(cls, tag):
        if hasattr(tag, "text"):
            text = tag.text
            if not isinstance(text, list):
                raise TagExtractionException("Unexpected text field content type ({}) for tag: {{}}".format(type(text)), tag)
            elif len(text) > 1:
                raise TagExtractionException("Unexpected text field list length ({}) for tag: {{}}".format(len(text)), tag)
            return unicode(text[0])
        elif type(tag).__name__ == "APIC":
            return "{} ({}, '{}')".format(tag.mime, tag.type, tag.desc)
        raise TagExtractionException("No known extractable content for tag: {}", tag)

    def get_tag_dict(self):
        tag_dict = {}
        for ver, tags in self.get_tags().iteritems():
            tag_dict[ver] = {}
            for key, value in tags.iteritems():
                if isinstance(value, list):
                    tag_dict[ver][key] = [self.extract_tag_value(val) for val in value]
                else:
                    tag_dict[ver][key] = self.extract_tag_value(value)
        return tag_dict

    def get_tags(self):
        if self.tags is None:
            mp3 = self.get_mp3()
            tags = {}
            if mp3.tags.version[0] == 2:
                v1_tags = self._get_v1_tags()[0]
                if v1_tags is not None:
                    tags["1.1"] = v1_tags
            latest_dict = {}
            for tag in mp3.tags:
                tlist = mp3.tags.getall(tag)
                latest_dict[tag] = tlist[0] if (len(tlist) == 1) else tlist
            tags[".".join(map(str, mp3.tags.version))] = latest_dict
            self.tags = tags
        return self.tags

    def _get_v1_tags(self):
        return find_id3v1(self.get_content())

    def get_audio_hash(self):
        if self.audio_hash is None:
            self.get_content()
            self.content.seek(0)
            content = BytesIO(self.content.read())
            ID3().delete(content)
            content.seek(0)
            self.audio_hash = sha256(content.read()).hexdigest()
        return self.audio_hash

    def get_full_hash(self):
        if self.full_hash is None:
            self.get_content()
            self.content.seek(0)
            self.full_hash = sha256(self.content.read()).hexdigest()
        return self.full_hash


class MusicFileOpenException(Exception):
    pass


class TagExtractionException(Exception):
    def __init__(self, msg, tag, *args, **kwargs):
        self.tag = tag
        super(TagExtractionException, self).__init__(msg.format(tag[:150]), *args, **kwargs)
