#!/usr/bin/env python2

from __future__ import print_function, division, unicode_literals

import logging
import argparse
from collections import OrderedDict


if not __file__.endswith(".py"):    #Git bash on windows doesn't properly detect when this file is symlinked
    import os
    import sys
    from subprocess import Popen, PIPE
    from unidecode import unidecode
    p = Popen(["stat", os.path.abspath(__file__)], stdout=PIPE, stderr=PIPE)
    stdout, stderr = p.communicate()
    exit_code = p.wait()
    try:
        __relpath = unidecode(stdout.splitlines()[0].decode("utf-8")).split("->")[1].split("'")[1]
    except IndexError:
        pass
    else:
        __filepath = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), __relpath))
        sys.path.append(os.path.dirname(__filepath))

from lib._constants import tag_name_map
from lib.common import DefaultOrderedDict
from lib.log_handling import LogManager
from lib.output_formatting import Printer
from lib.mp3_handling import MusicFile, AcoustidDB

unset = (None,)


def main():
    parser = argparse.ArgumentParser(description="MP3 Info Viewer")
    parser.add_argument("file_path", help="Path to an MP3 file")
    parser.add_argument("--lookup", "-l", action="count", help="Lookup file information from AcoustID (-ll to display all hits)")
    parser.add_argument("--format", "-f", choices=Printer.formats, default="yaml", help="Output format")
    parser.add_argument("--debug", "-d", action="store_true", default=False, help="Log additional debugging information (default: %(default)s)")
    parser.add_argument("--verbose", "-v", action="store_true", default=False, help="Log more verbose information (default: %(default)s)")
    args = parser.parse_args()

    lm = LogManager.create_default_stream_logger(args.debug, args.verbose)
    mf = MusicFile(args.file_path)

    show_songinfo(mf, args.format)

    if args.lookup:
        p = Printer(args.format if args.format != "table" else "yaml")
        acoustid_db = AcoustidDB()
        if args.lookup > 1:
            p.pprint(acoustid_db._lookup(*mf.fingerprint))
        else:
            p.pprint(acoustid_db.lookup(*mf.fingerprint))


def show_songinfo(mf, format):
    info = dict(mf.info)
    info["bitrate"] = info["bitrate_readable"]
    for k in ("bitrate_kbps", "bitrate_mode", "bitrate_readable", "info"):
        del info[k]

    if format != "table":
        p = Printer(format)
        p.pprint(OrderedDict([("File Info", info), ("ID3 Tags", mf.tag_dict)]))
    else:
        p = Printer("yaml")
        p.pprint(OrderedDict([("File Info", info)]))

        print()
        rows = []
        for tagid, tag in mf.tag_dict_by_id().iteritems():
            row = DefaultOrderedDict(lambda: "")
            row["Tag ID"] = tagid
            row["Tag Name"] = tag_name_map.get(tagid, "?")
            last_val = unset
            for ver in sorted(tag.keys(), key=lambda k: k[0]):
                row[ver] = tag[ver]
                if last_val is unset:
                    row["=?="] = ""
                    last_val = tag[ver]
                else:
                    same_val = last_val == tag[ver]
                    row["=?="] = "==" if same_val else "!="
            rows.append(row)
        Printer("table").pprint(rows, include_header=True, add_bar=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
    except Exception as e:
        logging.exception(e)