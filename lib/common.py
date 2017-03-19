#!/usr/bin/env python2

from __future__ import print_function, division, unicode_literals

import os
import re
import codecs
from contextlib import contextmanager

open = codecs.open
str = unicode

_badpath = re.compile(u'[\u0000-\u001F\u007F-\u009F/$!@#<>"\'|:*%?\\\\]', re.U)
invalid_path_rx = re.compile(u'[\u0000-\u001F\u007F-\u009F/$!@#<>"|:*%?\\\\]', re.U)


class InputValidationException(Exception):
    pass


def itemfinder(iterable, func):
    """
    :param iterable: A collection of items
    :param func: Function that takes 1 argument and returns a bool
    :return: The first item in iterable for which func(item) evaluates to True, or None if no such item exists
    """
    for i in iterable:
        if func(i):
            return i


@contextmanager
def ignore_exceptions(*exception_classes):
    try:
        yield
    except exception_classes:
        pass


@contextmanager
def ignore_exceptions_except(*exception_classes):
    try:
        yield
    except Exception as e:
        if isinstance(e, exception_classes):
            raise e


def getPaths(path):
    """
    Recursively generates a list of absolute paths for every file discoverable
    via the given path.
    """
    path = unicode(path[:-1] if (path[-1:] == os.sep) else path)
    paths = []
    if os.path.isdir(path):
        for sub in map(unicode, os.listdir(path)):
            paths.extend(getPaths(os.path.join(path, sub)))
    elif os.path.isfile(path):
        paths.append(path)
    return paths


def getFilteredPaths(path, ext, sort=True):
    fileFilter = re.compile(r'.*\.' + ext, re.IGNORECASE)
    filtered = [fname for fname in getPaths(path) if fileFilter.match(fname)]
    return sorted(filtered) if sort else filtered


def getUnusedPath(rpath, fname, ext=None):
    rpath = rpath[:-1] if (rpath[-1:] == "/") else rpath
    basename = fname
    if ext is None:
        ppos = fname.rfind(".")
        if ppos != -1:
            basename = fname[:ppos]
            ext = fname[ppos+1:]
        else:
            ext = "UNKNOWN"
    bnmax = 254 - len(ext)
    fpath = rpath + "/" + basename[:bnmax] + "." + ext
    c = 0
    while os.path.exists(fpath):
        c += 1
        nbnmax = bnmax + len(str(c))
        fpath = rpath + "/" + basename[:nbnmax] + str(c) + "." + ext
    return fpath


def cleanup(val):
    """Returns a string that is usable in a file name, else None"""
    if not val:
        return None
    elif isinstance(val, (str, unicode)):
        pass1 = _badpath.sub("", val)
        pass2 = re.sub("\s+", " ", pass1).strip()   #Condense multiple spaces into a single space
        return pass2 if (len(pass2) > 0) else None


def path_usable_str(val, nospace=False, lower=False):
    if not val:
        raise ValueError("Unusable in a file path")
    elif isinstance(val, (str, unicode)):
        newval = invalid_path_rx.sub("", val)
        newval = re.sub("\s+", " ", newval).strip()
        if lower:
            newval = newval.lower()
        if nospace:
            newval = newval.replace(" ", "")
        if newval:
            return newval
    raise ValueError("Unusable in a file path")
