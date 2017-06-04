
from __future__ import print_function, division, unicode_literals

import sys
import math
import codecs
import json
import pprint
import yaml
import csv
from collections import OrderedDict
from termcolor import colored
from cachetools import cached
from enum import Enum
from cStringIO import StringIO

from common import InputValidationException


_uout = codecs.getwriter("utf8")(sys.stdout)
_uerr = codecs.getwriter("utf8")(sys.stderr)


def uprint(msg):
    _uout.write(msg + "\n")


def err_uprint(msg):
    _uerr.write(msg + "\n")


def err_print(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)
    

def readable_bytes(file_size):
    units = zip(["B ", "KB", "MB", "GB", "TB", "PB"], [0, 2, 2, 2, 2, 2])
    try:
        exp = min(int(math.log(file_size, 1024)), len(units) - 1) if file_size > 0 else 0
    except TypeError as e:
        print("Invalid file size: '{}'".format(file_size))
        raise e
    unit, dec = units[exp]
    return "{{:,.{}f}} {}".format(dec, unit).format(file_size / 1024 ** exp)

    
def fTime(seconds, show_millis=False):
    full = seconds
    seconds = int(seconds)
    millis = full - seconds
    x = "-" if seconds < 0 else ""
    m, s = divmod(abs(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    x = "{}{}d".format(x, d) if d > 0 else x
    s = "{:07.4f}".format(s + millis) if show_millis else "{:02d}".format(s)
    return "{}{:02d}:{:02d}:{}".format(x, h, m, s)

    
def format_output(text, should_color, color_str, width=None, justify=None):
    if width is not None:
        padding = " " * (width - len(text))
        j = justify[0].upper() if justify is not None else "L"
        text = text + padding if j == "L" else padding + text
    if should_color:
        return colored(text, color_str)
    return text

    
def format_percent(num, div):
    return "{:,.2%}".format(num / div) if div > 0 else "--.--%"
    

def format_tiered(obj):
    lines = []
    if isinstance(obj, dict):
        if len(obj) < 1:
            return format_tiered("{}")
        kw = max(len(k) for k in obj)
        pad = " " * kw
        
        key_list = obj.keys() if isinstance(obj, OrderedDict) else sorted(obj.keys())
        for k in key_list:
            fk = k.ljust(kw)
            sub_objs = format_tiered(obj[k])
            for i in range(len(sub_objs)):
                if i == 0:
                    try:
                        lines.append(u"{}:  {}".format(fk, sub_objs[i]))
                    except UnicodeDecodeError as e:
                        err_print(e)
                        err_print(fk)
                        err_print(sub_objs[i])
                else:
                    lines.append(u"{}   {}".format(pad, sub_objs[i]))
    elif isinstance(obj, list):
        if len(obj) < 1:
            return format_tiered("[]")
        kw = len(str(len(obj)))
        pad = " " * kw
        fmt = u"[{{:>{}}}]:  {{}}".format(kw)
        for i in range(len(obj)):
            sub_objs = format_tiered(obj[i])
            for j in range(len(sub_objs)):
                if j == 0:
                    lines.append(fmt.format(i, sub_objs[j]))
                else:
                    lines.append(u" {}    {}".format(pad, sub_objs[j]))
    else:
        try:
            lines.append(str(obj))
        except UnicodeEncodeError as e:
            lines.append(obj)
    return lines
    
    
def print_tiered(obj):
    for line in format_tiered(obj):
        try:
            print(line)
        except UnicodeEncodeError as e:
            uprint(line)
    
    
def _clean_unicode(obj):
    if isinstance(obj, dict):
        return {_clean_unicode(k): _clean_unicode(v) for k, v in obj.iteritems()}
    elif isinstance(obj, list):
        return [_clean_unicode(v) for v in obj]
    elif isinstance(obj, unicode):
        return str(obj)
    else:
        return obj


class Printer:
    formats = ["json", "json-pretty", "text", "yaml", "pprint", "csv", "table"]
    
    def __init__(self, output_format):
        if output_format is None or output_format in Printer.formats:
            self.output_format = output_format
        else:
            raise InputValidationException("Invalid output format: {} (valid options: {})".format(output_format, Printer.formats))

    def pformat(self, content, *args, **kwargs):
        if self.output_format == "json":
            return json.dumps(content)
        elif self.output_format == "json-pretty":
            return json.dumps(content, sort_keys=True, indent=4)
        elif self.output_format == "text":
            return "\n".join(format_tiered(content))
        elif self.output_format == "yaml":
            if isinstance(content, dict) or kwargs.pop("force_single_yaml", False):
                formatted = yaml.dump(_clean_unicode(content), explicit_start=True, default_flow_style=False)
            else:
                formatted = yaml.dump(_clean_unicode(content), explicit_start=True)
            if formatted.endswith("...\n"):
                formatted = formatted[:-4]
            if formatted.endswith("\n"):
                formatted = formatted[:-1]
            return formatted
        elif self.output_format == "pprint":
            return pprint.pformat(content)
        elif self.output_format in ("csv", "table"):
            kwargs["mode"] = getattr(OutputTableModes, self.output_format.upper())
            try:
                return OutputTable.auto_format_rows(content, *args, **kwargs)
            except AttributeError:
                raise InputValidationException("Invalid content format to be formatted as a {}".format(self.output_format))
        else:
            return content

    def pprint(self, content, *args, **kwargs):
        if self.output_format == "text":
            print_tiered(content)
        elif self.output_format in ("csv", "table"):
            kwargs["mode"] = getattr(OutputTableModes, self.output_format.upper())
            try:
                OutputTable.auto_print_rows(content, *args, **kwargs)
            except AttributeError:
                raise InputValidationException("Invalid content format to be formatted as a {}".format(self.output_format))
        else:
            print(self.pformat(content, *args, **kwargs))


class OutputColumn:
    def __init__(self, title, width, display=False, align="", ftype=""):
        self.title = title
        if isinstance(width, (dict, list, set)):
            self.width = max(len(unicode(obj)) for obj in width)
        elif isinstance(width, tuple):
            i, k = width
            if isinstance(i, dict):
                self.width = max(len(unicode(e[k])) for e in i.itervalues())
            elif isinstance(i, list):
                self.width = max(len(unicode(e[k])) for e in i)
            else:
                raise InputValidationException("Invalid input type: {}".format(type(i)))
        else:
            self.width = width
        self.width = max(self.width, len(self.title))
        self.display = display
        self.align = align
        self.ftype = ftype


class OutputTableModes(Enum):
    TABLE = 0; CSV = 1


class OutputTable:
    def __init__(self, columns=None, mode=OutputTableModes.TABLE):
        self.csv_writer = None
        if mode not in OutputTableModes:
            raise InputValidationException("Invalid output mode: {}".format(mode))
        self.mode = mode
        if columns is not None:
            self.columns = OrderedDict(columns)
        else:
            self.columns = OrderedDict()
    
    def __getitem__(self, key):
        return self.columns[key]
    
    def __setitem__(self, key, val):
        self.columns[key] = val

    def _prep_csv_writer(self):
        if self.csv_writer is None:
            self.csv_writer = csv.DictWriter(sys.stdout, self.display_keys())

    @classmethod
    def auto_print_rows(cls, rows, include_header=False, add_bar=False, contains_unicode=False, sort=False, sort_by=None, mode=OutputTableModes.TABLE):
        if isinstance(rows, dict):
            rows = [row for row in rows.itervalues()]
        tbl = OutputTable([(k, OutputColumn(k, (rows, k), True)) for k in rows[0].keys()], mode)
        if include_header:
            tbl.print_header(add_bar, contains_unicode)
        tbl.print_rows(rows, sort, sort_by)

    @classmethod
    def auto_format_rows(cls, rows, include_header=False, add_bar=False, sort=False, sort_by=None, mode=OutputTableModes.TABLE):
        if isinstance(rows, dict):
            rows = [row for row in rows.itervalues()]
        tbl = OutputTable([(k, OutputColumn(k, (rows, k), True)) for k in rows[0].keys()], mode)
        output_rows = tbl.format_rows(rows, sort, sort_by)
        if include_header:
            if add_bar:
                output_rows.insert(0, tbl.get_bar())
            output_rows.insert(0, tbl.get_header_row())
        return output_rows

    def enable_keys(self, keys):
        for k in keys:
            self.columns[k].display = True

    def disable_keys(self, keys):
        for k in keys:
            self.columns[k].display = False

    @cached({})
    def display_keys(self):
        return [k for k in self.columns if self.columns[k].display]

    @cached({})
    def display_headers(self):
        return {k: self.columns[k].title for k in self.display_keys()}
    
    @cached({})
    def get_header_format(self):
        return "  ".join(["{{0[{}]:{}{}}}".format(k, self.columns[k].align, self.columns[k].width) for k in self.display_keys()])

    def get_header_row(self):
        return self.get_header_format().format(self.display_headers())
        
    @cached({})
    def get_format(self):
        return "  ".join(["{{0[{}]:{}{}{}}}".format(k, self.columns[k].align, self.columns[k].width, self.columns[k].ftype) for k in self.display_keys()])

    def print_header(self, add_bar=False, contains_unicode=False):
        if self.mode == OutputTableModes.CSV:
            self.print_row(self.display_headers())
        elif self.mode == OutputTableModes.TABLE:
            if contains_unicode:
                uprint(self.get_header_row())
            else:
                print(self.get_header_row())
            if add_bar:
                self.print_bar()

    def get_bar(self):
        if self.mode == OutputTableModes.TABLE:
            return "-" * len(self.get_header_row())
        return None

    def print_bar(self):
        if self.mode == OutputTableModes.TABLE:
            print(self.get_bar())
    
    def format_row(self, row_dict):
        if self.mode == OutputTableModes.CSV:
            si = StringIO()
            csv.DictWriter(si, self.display_keys()).writerow({k: row_dict[k] for k in self.display_keys()})
            return si.getvalue()
        elif self.mode == OutputTableModes.TABLE:
            try:
                return self.get_format().format(row_dict).rstrip()
            except ValueError:
                return self.get_header_format().format(row_dict).rstrip()

    def print_row(self, row_dict):
        if self.mode == OutputTableModes.CSV:
            self._prep_csv_writer()
            self.csv_writer.writerow({k: row_dict[k] for k in self.display_keys()})
        elif self.mode == OutputTableModes.TABLE:
            print(self.format_row(row_dict))

    def _prep_rows(self, rows, sort=False, sort_by=None):
        if isinstance(rows, dict):
            rows = [row for row in rows.itervalues()]

        if sort_by is not None:
            rows = sorted(rows, key=lambda r: r[sort_by])
        elif sort:
            rows = sorted(rows)

        if self.mode == OutputTableModes.CSV:
            keys = self.display_keys()
            rows = [{k: row[k] for k in keys} for row in rows]
        return rows

    def format_rows(self, rows, sort=False, sort_by=None):
        rows = self._prep_rows(rows, sort, sort_by)
        if self.mode == OutputTableModes.CSV:
            si = StringIO()
            csv.DictWriter(si, self.display_keys()).writerows(rows)
            return si.getvalue().splitlines()
        elif self.mode == OutputTableModes.TABLE:
            return [self.format_row(row) for row in rows]

    def print_rows(self, rows, sort=False, sort_by=None):
        try:
            if self.mode == OutputTableModes.CSV:
                self._prep_csv_writer()
                self.csv_writer.writerows(self._prep_rows(rows, sort, sort_by))
            elif self.mode == OutputTableModes.TABLE:
                for row in self.format_rows(rows, sort, sort_by):
                    print(row)
        except IOError as e:
            if e.errno == 32:   #broken pipe
                return
