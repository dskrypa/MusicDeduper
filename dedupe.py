#!/usr/bin/env python2

from __future__ import print_function, division, unicode_literals

import time
import json
import logging
import argparse
from collections import OrderedDict, defaultdict, Counter

from lib.common import getFilteredPaths, path_usable_str
from lib.log_handling import LogManager, OutputManager
from lib.alchemy_db import AlchemyDatabase, DBTable
from lib.output_formatting import fTime, Printer, format_percent, format_output, OutputTable, OutputColumn
from lib.mp3_handling import MusicFile, MusicFileOpenException, NoTagVal, TagVersionMismatchException
from lib._constants import tag_name_map

"""
Notes:
- sketchy just indicates possibly invalid MPEG audio
"""

default_db_path = "/var/tmp/music_deduper.db"
preferred_version = "2.3.0"

info_columns = ["bitrate", "bitrate_kbps", "bitrate_mode", "channels", "encoder_info", "length", "sample_rate", "sketchy", "time"]
info_types = ["INT", "INT", "TEXT", "INT", "TEXT", "FLOAT", "INT", "BOOLEAN", "TEXT"]
db_columns = ["path", "modified", "size", "sha256", "audio_sha256", "tags"] + info_columns + ["v1", "v2", "tag_mismatches"]
db_types = ["TEXT", "INT", "INT", "TEXT", "TEXT", "TEXT"] + info_types + ["TEXT", "TEXT", "TEXT"]

# V1_Tags: {"TIT2":"Title", "TPE1":"Artist", "TALB":"Album", "TDRC":"Year", "COMM":"Comment", "TRCK":"Track", "TCON":"Genre"}

primary_tags = {"TIT2":"Title", "TPE1":"Artist", "TALB":"Album", "TDRC":"Year", "TRCK":"Track"}


def main():
    parser = argparse.ArgumentParser(description="Music collection deduper")
    sparsers = parser.add_subparsers(dest="action")

    parser1 = sparsers.add_parser("scan", help="Scan the given directory")
    parser1.add_argument("scan_dir", help="The directory to scan for music")
    parser2 = sparsers.add_parser("view", help="View current DB")
    parser2.add_argument("--tags", "-t", nargs="+", help="Only include MP3s with the given tags")

    parser3 = sparsers.add_parser("tagkeys", help="")
    #parser3.add_argument("scan_dir", help="The directory to scan for music")

    parser4 = sparsers.add_parser("report", help="")
    parser4.add_argument("report_name", choices=("mismatch", "unique", "dupes", "sketchy", "tag_popularity", "files_with_tag", "name_variations"), help="Name of report to run")
    parser4.add_argument("--analysis_mode", "-am", choices=("audio", "full"), default="full", help="")
    parser4.add_argument("--tag", "-t", help="Tag to find for files_with_tag report")

    for _parser in sparsers.choices.values() + [parser]:
        _parser.add_argument("--db_path", "-db", metavar="/path/to/music_db", default=default_db_path, help="DB location (default: %(default)s)")
        _parser.add_argument("--debug", "-d", action="store_true", default=False, help="Log additional debugging information (default: %(default)s)")
        _parser.add_argument("--verbose", "-v", action="store_true", default=False, help="Log more verbose information (default: %(default)s)")
    args = parser.parse_args()

    lm, log_path = LogManager.create_default_logger(args.debug, args.verbose)
    logging.info("Logging to: {}".format(log_path))

    if args.action == "scan":
        deduper = Deduper(lm, args.db_path)
        deduper.scan(args.scan_dir)
    elif args.action == "view":
        deduper = Deduper(lm, args.db_path)
        deduper.view(args.tags)
    elif args.action == "tagkeys":
        db = AlchemyDatabase(args.db_path, logger=lm)
        for row in db["music"].rows():
            for ver, tags in json.loads(row["tags"]).iteritems():
                if ver.startswith("2"):
                    print(row["path"], json.dumps(tags.keys()))
    elif args.action == "report":
        deduper = Deduper(lm, args.db_path)
        deduper.report(args.report_name, analysis_mode=args.analysis_mode, find_tag=args.tag)


class Deduper:
    def __init__(self, log_manager, db_path):
        self.lm = OutputManager(log_manager)
        self.db = AlchemyDatabase(db_path, logger=self.lm)
        self.music = DBTable(self.db, "music", zip(db_columns, db_types), "path")
        self.p = Printer("json-pretty")

    def dedupe(self):
        """
        Generate a deduplication plan
        """
        destinations = {"compilation": {}, "podcast": {}, "by_artist": {}, "problematic": {"tag_mismatch": {}, "missing_info": {}, "bad": {}}}
        placement_tags = {"albumArtist": "TPE2", "artist": "TPE1", "album": "TALB", "title": "TIT2", "": "", "": ""}

        for row in self.music:
            song = MusicFile(row["path"], row)

    def view(self, with_tags=None):
        p = Printer("table")
        if with_tags is None:
            p.pprint([row for row in self.music], include_header=True, add_bar=True)
        else:
            rows = []
            for row in self.music:
                orow = {}
                tags = json.loads(row["tags"])
                v1, v2 = row["v1"], row["v2"]

                for tid in with_tags:
                    orow[tid] = tags.get(v2, {}).get(tid, None)
                if reduce(lambda a, b: a or b, orow.values()):
                    orow["path"] = row["path"]
                    rows.append(orow)

            cols = [("path", OutputColumn("Path", (rows, "path"), True))]
            for tid in with_tags:
                cols.append((tid, OutputColumn(tid, (rows, tid), True)))
            tbl = OutputTable(cols)
            tbl.print_header(True)
            tbl.print_rows(rows)

    def report(self, report_name, *args, **kwargs):
        p = Printer("table")
        if report_name == "mismatch":
            cols = ["path", "tag", "v1", "v2", "v1_val", "v2_val"]
            report_rows = []
            for row in self.music:
                mismatches = json.loads(row["tag_mismatches"])
                if mismatches:
                    tags = json.loads(row["tags"])
                    v1, v2 = row["v1"], row["v2"]
                    for tid in mismatches:
                        report_row = {
                            "path": row["path"], "tag": tid, "v1": v1, "v2": v2,
                            "v1_val": tags[v1].get(tid, None), "v2_val": tags[v2].get(tid, None)
                        }
                        report_rows.append(OrderedDict([(k, report_row[k]) for k in cols]))
            p.pprint(report_rows, include_header=True, add_bar=True)
        elif report_name == "unique":
            for rows in self.analyze(*args, **kwargs).itervalues():
                if len(rows) == 1:
                    print(rows[0]["path"])
        elif report_name == "dupes":
            for sha256, rows in self.analyze(*args, **kwargs).iteritems():
                if len(rows) != 1:
                    print(sha256)
                    for row in rows:
                        print("\t" + row["path"])
        elif report_name == "sketchy":
            sketchy = [row for row in self.music if row["sketchy"]]
            if len(sketchy) > 0:
                p.pprint(sketchy, include_header=True, add_bar=True)
            else:
                print("Nothing sketchy!")
        elif report_name == "tag_popularity":
            count = 0
            all_tags = Counter()
            for row in self.music:
                count += 1
                tags = json.loads(row["tags"])
                if row["v2"] is not None:
                    vtags = tags[row["v2"]]
                elif row["v1"] is not None:
                    vtags = tags[row["v1"]]
                else:
                    continue
                all_tags.update(vtags.keys())

            print("Rows: {}".format(count))
            report = []
            cols = ["tag", "count", "percent"]
            for key in sorted(all_tags.keys()):
                row = {"tag": key, "count": all_tags[key], "percent": format_output(format_percent(all_tags[key], count), False, None, 6, "r")}
                report.append(OrderedDict([(k, row[k]) for k in cols]))
            p.pprint(report, include_header=True, add_bar=True)
        elif report_name == "files_with_tag":
            find_tag = kwargs["find_tag"].upper()
            count = 0
            for row in self.music:
                tags = json.loads(row["tags"])
                if row["v2"] is not None:
                    vtags = tags[row["v2"]]
                elif row["v1"] is not None:
                    vtags = tags[row["v1"]]
                else:
                    continue
                if find_tag in vtags:
                    count += 1
                    if count > 1:
                        print()
                    print(row["path"])
                    for tag, value in vtags.iteritems():
                        friendly = tag_name_map.get(tag, "[unknown]")
                        print("    [{} / {}]: {}".format(tag, friendly, value))
        elif report_name == "name_variations":
            # TODO: Improve variation detection (punctuation, equivalent chars (e.g., +/&/and), unicode normalization)

            artists = defaultdict(set)
            albums = defaultdict(set)
            for row in self.music:
                song = MusicFile(row["path"], row)
                for tid in ("TPE1", "TPE2"):
                    try:
                        artist = song.get_tag(tid, NoTagVal)
                    except TagVersionMismatchException as e:
                        self.lm.error("{}: {}".format(song.file_path, e))
                    else:
                        if artist is not NoTagVal:
                            try:
                                artists[path_usable_str(artist, True, True)].add(artist)
                            except ValueError as e:
                                self.lm.error("{}: artist '{}' [{}]".format(e, artist, song.file_path))

                try:
                    album = song.get_tag("TALB", NoTagVal)
                except TagVersionMismatchException as e:
                    self.lm.error("{}: {}".format(song.file_path, e))
                else:
                    if album is not NoTagVal:
                        try:
                            albums[path_usable_str(album, True, True)].add(album)
                        except ValueError as e:
                            self.lm.error("{}: album '{}' [{}]".format(e, album, song.file_path))

            print("Artist variations:")
            artist_variations = 0
            for artist_set in artists.itervalues():
                if len(artist_set) > 1:
                    artist_variations += 1
                    print(", ".join("'{}'".format(artist) for artist in artist_set))
            if artist_variations == 0:
                print("None!")

            print("Album variations:")
            album_variations = 0
            for album_set in albums.itervalues():
                if len(album_set) > 1:
                    album_variations += 1
                    print(", ".join("'{}'".format(album) for album in album_set))
            if album_variations == 0:
                print("None!")

    def analyze(self, analysis_mode):
        if analysis_mode not in ("full", "audio"):
            raise ValueError("mode can be full or audio, not {}".format(analysis_mode))

        hashkey = "sha256" if analysis_mode == "full" else "audio_sha256"
        analyzed = defaultdict(list)
        for row in self.music:
            analyzed[row[hashkey]].append(row)
        return analyzed

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
                        modified_changed = (db_file["modified"] != mf.modified)
                        size_changed = (db_file["size"] != mf.size)
                        if not (modified_changed or size_changed):
                            pm.record_skip("Skipping", file_path, "(already in db)")
                            continue

                        why = ["file updated" if modified_changed else None, "size changed" if size_changed else None]
                        why = " and ".join([reason for reason in why if reason is not None])
                        pm.record_message("Updating", file_path, "({})".format(why))

                    try:
                        info = mf.info
                        row = {
                            "path": file_path, "modified": mf.modified, "size": mf.size,
                            "tags": json.dumps(mf.tag_dict), "sha256": mf.full_hash, "audio_sha256": mf.audio_hash,
                            "v1": mf.v1_ver, "v2": mf.v2_ver, "tag_mismatches": json.dumps(mf.get_mismatch_keys())
                        }
                    except Exception as e:
                        pm.record_error("{}: {}".format(file_path, e))
                        logging.debug("{}:{}".format(e.__class__.__name__, e))
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
            processed = self.c - self.skipped
            rate = processed / dt if dt > 0 else 1
            remaining = fTime((self.total - processed) / rate) if (processed > 5) else "??:??:??"
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
