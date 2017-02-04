'''
Author: Douglas Skrypa
Date: 2016.02.07
Version: 1.6
'''

from __future__ import division, unicode_literals
import sys, os
PY2 = (sys.version_info.major == 2)
if PY2:
    import codecs
    open = codecs.open
    str = unicode
    trows, tcols = os.popen('stty size', 'r').read().split()
    tcols = int(tcols)
else:
    import shutil
    tcols = shutil.get_terminal_size()[0]
#/if Python 2.x

import time, re

_badpath = re.compile(u'[\u0000-\u001F\u007F-\u009F/$!@#<>"\'|:*%?\\\\]', re.U)


def getPaths(path):
    '''
    Recursively generates a list of absolute paths for every file discoverable
    via the given path.
    '''
    path = path[:-1] if (path[-1:] == "/") else path                            #Strip trailing slash if it exists
    path = unicode(path)
    paths = []                                                                    #Initialize list to store paths in
    if os.path.isdir(path):                                                        #If the given path is a directory
        for sub in os.listdir(path):                                            #Iterate through each sub-path in it
            sub = unicode(sub)
            paths += getPaths(path + "/" + sub)                                #Add the list of paths discoverable there
    elif os.path.isfile(path):                                                    #Otherwise, if it is a file
        paths += [path]                                                        #Add the path to the list
    return paths                                                                #Return the list
#/getPaths

def getFilteredPaths(path, ext, sort=True):
    paths = getPaths(path)                                                        #Get the paths
    fileFilter = re.compile(r'.*\.' + ext, re.IGNORECASE)                        #Define the filter
    filtered = [fname for fname in paths if fileFilter.match(fname)]            #Apply the filter
    return sorted(filtered) if sort else filtered                                #Return the filtered list (sorted if sort == True)
#/getFilteredPaths

def getUnusedPath(rpath, fname, ext=None):
    rpath = rpath[:-1] if (rpath[-1:] == "/") else rpath
    basename = fname
    if (ext == None):
        ppos = fname.rfind(".")
        if (ppos != -1):
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
#/getUnusedPath

def cleanup(strng):
    '''Returns a string that is usable in a file name, else None'''
    if (strng == None) or (len(strng) < 1):
        return None
    pass1 = _badpath.sub('', strng)                                            #Remove any characters invalid in filenames
    pass2 = re.sub(r'\s+',' ',pass1).strip()                                    #Remove extraneous spaces
    return pass2 if (len(pass2) > 0) else None
#/cleanup

def fTime(seconds, showDecimal=False):
    orig = seconds
    s = int(seconds)
    rmd = orig - s
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    if showDecimal:
        return "{:02d}:{:02d}:{:07.4f}".format(h, m, s + rmd)
    else:
        return "{:02d}:{:02d}:{:02d}".format(h, m, s)                            #Return a string representation of the given number of seconds as HH:MM:SS
#/fTime

def byteFmt(byteCount):
    labels = ['B','KB','MB','GB','TB']
    bc = byteCount
    c = 0
    while ((bc > 1024) and (c < 4)):
        bc /= 1024
        c += 1
    return "{:,.2f} {}".format(bc, labels[c])
#/byteFmt

def longestString(lst):
    return max([len(e) for e in lst])
#/longestString

class PerfTimer():
    '''Simple performance monitor including a timer and counters'''
    def __init__(self):
        self.now = time.time if PY2 else time.perf_counter
        self.start = self.now()                                                #Initialize the timer with the current time
    def time(self):
        return self.now()                                                        #Return the current time using the same method as the internal timer
    def elapsed(self, since=None):
        sinceTime = self.start if (since == None) else since
        return self.now() - sinceTime                                            #Return the time delta in seconds since initialization
    def elapsedf(self, since=None):
        return fTime(self.elapsed(since))                                        #Return the time delta as a string in the form HH:MM:SS
#/PerfTimer

class clio():
    '''Command Line Interface Output'''
    lml = 0                                                                    #Last message length
    lastWasShow = False
    @classmethod
    def _fmt(cls, msg):
        '''Format the given message for overwriting'''
        mlen = len(msg)                                                        #Length of the current message
        ldelta = clio.lml - mlen
        clio.lml = mlen                                                        #Store the current message's length as the last message length
        suffix = (" " * ldelta) if (clio.lastWasShow and (ldelta > 0)) else ""    #Fill with only as many spaces are necessary to hide the last message, if necessary
        return '\r' + msg + suffix                                                #\r to return to the beginning of the line
    #/fmt
    @classmethod
    def show(cls, msg=""):
        '''Display overwritable message'''
        msg = msg[:tcols-1]
        fmsg = cls._fmt(msg)
        sys.stdout.write(fmsg)
        sys.stdout.flush()
        clio.lastWasShow = True
    #/show
    @classmethod
    def showf(cls, fmt, *args):
        '''Display formatted overwritable message'''
        msg = fmt.format(*args)
        msg = msg[:tcols-1]
        cls.show(msg)
        clio.lastWasShow = True
    #/showf
    @classmethod
    def println(cls, msg=""):
        '''Display message on a new line'''
        fmsg = cls._fmt(msg) + "\n"
        sys.stdout.write(fmsg)
        sys.stdout.flush()
        clio.lastWasShow = False
    #/println
    @classmethod
    def printf(cls, fmt, *args):
        '''Display formatted message on a new line'''
        msg = fmt.format(*args)
        cls.println(msg)
        clio.lastWasShow = False
    #/printf
#/clio

class ErrorLog():
    '''Simple error log that includes a date+time stamp for each line'''
    def __init__(self, path):
        self.logfile = open(path, "a")
        self.tfmt = "%Y-%m-%d_%H:%M:%S"
        self.lfmt = "[{}] {}\n"
    #/init
    def record(self, err):
        ts = time.strftime(self.tfmt, time.localtime())
        self.logfile.write(self.lfmt.format(ts, err))
        self.logfile.flush()
    #/record
    def close(self):
        self.logfile.close()
    #/close
#/ErrorLog
