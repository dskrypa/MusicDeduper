#!/usr/bin/env python2

from __future__ import print_function, division

import time
import json
import logging
import argparse

from lib.common import InputValidationException, getFilteredPaths
from lib.log_handling import LogManager, OutputManager
from lib.alchemy_db import AlchemyDatabase, DBTable
from lib.output_formatting import fTime, Printer, print_tiered
from lib.mp3_handling import MusicFile, MusicFileOpenException, TagExtractionException


default_db_path = "/var/tmp/music_deduper.db"

info_columns = ["bitrate", "bitrate_kbps", "bitrate_mode", "channels", "encoder_info", "length", "sample_rate", "sketchy", "time"]
info_types = ["INT", "INT", "TEXT", "INT", "TEXT", "FLOAT", "INT", "BOOLEAN", "TEXT"]
db_columns = ["path", "modified", "size", "sha256", "audio_sha256", "tags"] + info_columns
db_types = ["TEXT", "INT", "INT", "TEXT", "TEXT", "TEXT"] + info_types


def main():
    parser = argparse.ArgumentParser(description="Music collection deduper")
    sparsers = parser.add_subparsers(dest="action")

    parser1 = sparsers.add_parser("scan", help="Scan the given directory")
    parser1.add_argument("scan_dir", help="The directory to scan for music")
    parser2 = sparsers.add_parser("view", help="View current DB")

    for _parser in sparsers.choices.values() + [parser]:
        _parser.add_argument("--debug", "-d", action="store_true", default=False, help="Log additional debugging information (default: %(default)s)")
        _parser.add_argument("--verbose", "-v", action="store_true", default=False, help="Log more verbose information (default: %(default)s)")
    args = parser.parse_args()

    lm, log_path = LogManager.create_default_logger(args.debug, args.verbose)
    logging.info("Logging to: {}".format(log_path))

    if args.action == "scan":
        deduper = Deduper(lm)
        deduper.scan(args.scan_dir)
    elif args.action == "view":
        p = Printer("table")
        db = AlchemyDatabase(default_db_path, logger=lm)
        p.pprint([row for row in db["music"].rows()], include_header=True, add_bar=True)


class Deduper:
    def __init__(self, log_manager):
        self.lm = OutputManager(log_manager)
        self.db = AlchemyDatabase(default_db_path, logger=self.lm)
        self.music = DBTable(self.db, "music", zip(db_columns, db_types), "path")
        self.p = Printer("json-pretty")

    def scan(self, scan_dir):
        paths = getFilteredPaths(scan_dir, "mp3")
        with ProgressMonitor(paths, self.lm) as pm:
            for file_path in paths:
                try:
                    pm.incr()
                    try:
                        mf = MusicFile(file_path)
                    except MusicFileOpenException as e:
                        pm.record_error(e)
                        continue

                    if file_path in self.music:
                        db_file = self.music[file_path]
                        last_modified_changed = (db_file["modified"] != mf.modified)
                        size_changed = (db_file["size"] != mf.size)
                        if not (last_modified_changed or size_changed):
                            pm.record_skip("Skipping", file_path, "(already in db)")
                            continue
                        why = "file updated" if last_modified_changed else ""
                        if size_changed:
                            why += " and " if (len(why) != 0) else ""
                            why += "size changed"
                        pm.record_message("Updating", file_path, "({})".format(why))

                    try:
                        info = mf.get_info()
                        row = {
                            "path": file_path, "modified": mf.modified, "size": mf.size,
                            "tags": json.dumps(mf.get_tag_dict()),
                            "sha256": mf.get_full_hash(),
                            "audio_sha256": mf.get_audio_hash()
                        }
                    except TagExtractionException as e:
                        pm.record_error("Error extracting tag information from {} [{}].  Tags:".format(file_path, info["info"]))
                        print_tiered(mf.get_tags())
                        break
                    except Exception as e:
                        pm.record_error("{}: {}".format(file_path, e))
                        continue
                    else:
                        row.update({key: info[key] for key in info_columns})
                        self.music.insert(row)
                except KeyboardInterrupt:
                    break


class ProgressMonitor:
    def __init__(self, to_be_processed, log_manager):
        self.lm = log_manager
        if isinstance(to_be_processed, (list, dict)):
            self.total = len(to_be_processed)
        else:
            try:
                self.total = int(to_be_processed)
            except Exception:
                raise TypeError("expected number, list, or dict; found {}".format(type(to_be_processed)))
        self.tl = str(len(str(self.total)))
        self.base_fmt = "[{{:7.2%}}|{{:{}d}}/{}]".format(self.tl, self.total)
        self.pfmt = self.base_fmt + " {} {} {}"
        self.spfmt = self.base_fmt + "[Elapsed: {}][Skipped: {:8,d}][Errors: {:8,d}][Rate: {:,.2f} files/sec][Remaining: ~{}]"
        self.skipped, self.errors, self.c = 0, 0, 0
        self.start = time.time()
        self.last_time = self.elapsed()

    def elapsed(self, since=None):
        sinceTime = self.start if (since is None) else since
        return time.time() - sinceTime

    def elapsedf(self, since=None):
        return fTime(self.elapsed(since))

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        fmt = "{{}}   {{:{}d}} ({{:.2%}})".format(self.tl)
        self.lm.printf("Done!", end=True, append=False)
        self.lm.printf("Processed: {:d}", self.c, end=True, append=False)
        self.lm.printf(fmt, "Skipped:", self.skipped, self.skipped / self.c, end=True, append=False)
        self.lm.printf(fmt, "Errors: ", self.errors, self.errors / self.c, end=True, append=False)
        self.lm.printf("Runtime: {}", self.elapsedf(), end=True, append=False)

    def incr(self):
        self.c += 1
        dt = self.elapsed()
        if (dt - self.last_time) > 0.33:
            rate = self.c / dt if dt > 0 else 1
            remaining = fTime((self.total - self.c) / rate)
            self.last_time = dt
            self.lm.printf(self.spfmt, self.c / self.total, self.c, self.elapsedf(), self.skipped, self.errors, rate, remaining, end=False, append=False)

    def record_error(self, *args, **kwargs):
        self.errors += 1
        self.lm.error(*args, **kwargs)

    def record_skip(self, *args, **kwargs):
        self.skipped += 1
        self.record_message(*args, **kwargs)

    def record_message(self, *args, **kwargs):
        self.lm.verbose(self.pfmt.format(self.c / self.total, self.c, *args, **kwargs))


class HashException(Exception):
    pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
    except Exception as e:
        logging.exception(e)
