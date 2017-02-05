#!/usr/bin/env python2

from __future__ import division

import os
import codecs
import hashlib
import logging
import argparse
import tempfile
from enum import Enum   #Enum34 in Python 2

import eyeD3b as eyeD3  #A version of eyeD3 with a kludge added by me to make it support using a SpooledTemporaryFile

from lib.common import InputValidationException, getFilteredPaths, PerfTimer
from lib.log_handling import LogManager, OutputManager
from lib.sqlite3_db import Sqlite3Database, DBTable
from lib.output_formatting import fTime

open = codecs.open


class HashModes(Enum):
    AUDIO = 1; FULL = 2


def main():
    parser = argparse.ArgumentParser(description="Music collection deduper")
    parser.add_argument("scan_dir", help="The directory to scan for music")
    cmgroup = parser.add_argument_group("Compare Modes (required)", required=True)
    cmgroup.add_argument("-a", "--audio", help="Compare files based on a hash of the audio content (slower)", dest="hash_mode", action="store_const", const=HashModes.AUDIO)
    cmgroup.add_argument("-f", "--full", help="Compare files based on a hash of the entire file (faster)", dest="hash_mode", action="store_const", const=HashModes.FULL)
    parser.add_argument("--debug", "-d", action="store_true", default=False, help="Log additional debugging information (default: %(default)s)")
    parser.add_argument("--verbose", "-v", action="store_true", default=False, help="Log more verbose information (default: %(default)s)")
    args = parser.parse_args()

    lm, log_path = LogManager.create_default_logger(args.debug, args.verbose)
    logging.info("Logging to: {}".format(log_path))

    deduper = Deduper(args.hash_mode, lm)
    deduper.scan(args.scan_dir)


class Deduper:
    def __init__(self, hash_mode, log_manager):
        if hash_mode not in HashModes:
            raise InputValidationException("Invalid hash mode: {}".format(hash_mode))
        db_path = "/var/tmp/deduper_audio_hash.db" if hash_mode == HashModes.AUDIO else "/var/tmp/deduper_full_hash.db"
        self.db = Sqlite3Database(db_path)
        self.music = DBTable(self, "music", ["path", "modified", "size", "hash"], "path")
        self.hash_mode = hash_mode
        self.lm = OutputManager(log_manager)

    def hash(self, file_path):
        if os.path.splitext(file_path)[1] != ".mp3":
            raise InputValidationException("Skipping non-MP3: {}".format(file_path))
        elif self.hash_mode == HashModes.FULL:
            try:
                with open(file_path, "rb") as audio_file:
                    return hashlib.sha256(audio_file.read()).hexdigest()
            except (OSError, IOError):
                raise HashException("Unable to open file: {}".format(file_path))
        elif self.hash_mode == HashModes.AUDIO:
            try:
                tag = eyeD3.Tag()
                audio_content = tempfile.SpooledTemporaryFile()
                with open(file_path, "rb") as orig_file:
                    audio_content.write(orig_file.read())
                tag.link(audio_content)
                tag.remove(eyeD3.ID3_ANY_VERSION)
                audio_content.seek(0)
                return hashlib.sha256(audio_content.read()).hexdigest()
            except Exception as e:
                raise HashException("Unable to decode file: {}".format(file_path), e)
        else:
            raise NotImplementedError("hash() with mode {}".format(self.hash_mode))

    def scan(self, scan_dir):
        paths = getFilteredPaths(scan_dir, "mp3")
        t = len(paths)
        tl = str(len(str(t)))
        base_fmt = "[{{:7.2%}}|{{:{}d}}/{}]".format(tl, t)
        pfmt = base_fmt + " {} {} {}"
        spfmt = base_fmt + "[Elapsed: {}][Skipped: {:8,d}][Errors: {:8,d}][Rate: {:,.2f} files/sec][Remaining: ~{}]"
        skipped, errors, c = 0, 0, 0
        pt = PerfTimer()
        last_time = pt.elapsed()

        for file_path in paths:
            c += 1
            dt = pt.elapsed()
            rate = c / dt
            remaining = fTime((t - c) / rate)
            if (dt - last_time) > 0.33:
                last_time = dt
                self.lm.printf(spfmt, c / t, c, pt.elapsedf(), skipped, errors, rate, remaining, end=False, append=False)

            try:
                stat = os.stat(file_path)
            except Exception as e:
                errors += 1
                if isinstance(e, KeyboardInterrupt):
                    break
                elif isinstance(e, OSError):
                    self.lm.error("OSError on {}: {}".format(file_path, e))
                else:
                    self.lm.error("Unexpected {} on file: {}".format(type(e).__name__, file_path))
                continue
            else:
                file_size = int(stat.st_size)
                last_mod = int(stat.st_mtime)

            if file_path in self.music:
                db_file = self.music[file_path]
                if (db_file["modified"] == last_mod) and (db_file["size"] == file_size):
                    skipped += 1
                    self.lm.verbose(pfmt.format(c / t, c, "Skipping", file_path, "(already in db)"))
                    continue

            try:
                hash = self.hash(file_path)
            except Exception as e:
                errors += 1
                if isinstance(e, KeyboardInterrupt):
                    break
                elif isinstance(e, (InputValidationException, HashException)):
                    self.lm.error("{}: {}".format(file_path, e))
                else:
                    self.lm.error("Unexpected {} on file: {}".format(type(e).__name__, file_path))
                continue

            self.music.insert({"path": file_path, "modified": last_mod, "size": file_size, "hash": hash})

        fmt = "{{}}   {{:{}d}} ({{:.2%}})".format(tl)
        self.lm.printf("Done!", end=True, append=False)
        self.lm.printf("Processed: {:d}", t, end=True, append=False)
        self.lm.printf(fmt, "Skipped:", skipped, skipped / t, end=True, append=False)
        self.lm.printf(fmt, "Errors: ", errors, errors / t, end=True, append=False)
        self.lm.printf("Runtime: {}", pt.elapsedf(), end=True, append=False)


class HashException(Exception):
    pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
