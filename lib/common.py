#!/usr/bin/env python2

from __future__ import print_function, division, unicode_literals

import os
import re
import codecs
import time
import sys
from contextlib import contextmanager
from collections import OrderedDict, Callable

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


class DefaultOrderedDict(OrderedDict):
    def __init__(self, default_factory=None, *args, **kwargs):
        if (default_factory is not None) and (not isinstance(default_factory, Callable)):
            raise TypeError("first argument must be callable")
        OrderedDict.__init__(self, *args, **kwargs)
        self.default_factory = default_factory

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key)
        self[key] = value = self.default_factory()
        return value

    def __reduce__(self):
        args = tuple() if self.default_factory is None else self.default_factory,
        return type(self), args, None, None, self.iteritems()

    def copy(self):
        return self.__copy__()

    def __copy__(self):
        return type(self)(self.default_factory, self)


def fTime(seconds):
    seconds = int(seconds)
    minutes = int(seconds / 60)
    seconds -= (minutes * 60)
    hours = int(minutes / 60)
    minutes -= (hours * 60)
    return "{:02d}:{:02d}:{:02d}".format(hours, minutes, seconds)


class PerfTimer():
    """Simple performance monitor including a timer and counters"""
    def __init__(self):
        self.start = time.time()

    def time(self):
        """Return the current time using the same method as the internal timer"""
        return time.time()

    def elapsed(self, since=None):
        """Return the time delta in seconds since initialization"""
        sinceTime = self.start if since is None else since
        return time.time() - sinceTime

    def elapsedf(self):
        """Return the time delta as a string in the form HH:MM:SS"""
        return time.strftime("%H:%M:%S",time.gmtime(self.elapsed()))


def to_bytes(text):
    if isinstance(text, unicode):
        return text.encode("utf-8")
    return text


def to_unicode(text):
    if not isinstance(text, unicode):
        return text.decode("utf-8")
    return text


class clio():
    """Command Line Interface Output"""
    lml=0;
    #utfout = open(sys.stdout, 'w', encoding="utf-8")

    @classmethod
    def _fmt(cls, msg):
        """Format the given message for overwriting"""
        mlen = len(msg)
        suffix = " " * (clio.lml-mlen) if mlen < clio.lml else ""
        clio.lml = mlen
        return "\r" + msg + suffix

    @classmethod
    def show(cls, msg=""):
        """Display overwritable message"""
        wmsg = cls._fmt(msg)	#.encode("utf-8")
        #cls.utfout.write(wmsg)
        #cls.utfout.flush()
        try:
            sys.stdout.write(to_bytes(wmsg))
            sys.stdout.flush()
        except IOError:
            pass

    @classmethod
    def showf(cls, fmt, *args):
        """Display formatted overwritable message"""
        msg = fmt.format(*args)
        cls.show(msg)

    @classmethod
    def println(cls, msg=""):
        """Display message on a new line"""
        wmsg = cls._fmt(msg + "\n")	#.encode("utf-8")
        #sys.stdout.write(cls._fmt(msg) + "\n")
        #cls.utfout.write(wmsg)
        #cls.utfout.flush()
        try:
            sys.stdout.write(to_bytes(wmsg))
            sys.stdout.flush()
        except IOError:
            pass


    @classmethod
    def printf(cls, fmt, *args):
        """Display formatted message on a new line"""
        msg = fmt.format(*args)
        cls.println(msg)


