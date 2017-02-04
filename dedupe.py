#!/usr/bin/env python2

"""
Author: Douglas Skrypa
Date: 2017.02.04
Version: 8.1.1
"""

from __future__ import division
import os
import sys
import time
import shutil
import hashlib
import logging
import argparse
import tempfile
from enum import Enum   #For Python 2, need to run 'sudo pip install enum34'
import eyeD3b as eyeD3  #A version of eyeD3 with a kludge added by me to make it support using a SpooledTemporaryFile

from common import clio, getUnusedPath, ErrorLog, getFilteredPaths, PerfTimer, fTime

PY2 = (sys.version_info.major == 2)
if PY2:
    import codecs
    open = codecs.open
#/Python 2 compatibility


def main():
    #Real paths
    #sdir = "/media/user/WD_1TB_External_Backup/unduped_full_hash/"
    #ddir = "/media/user/My Passport/unduped_audio_hash/"
    #lpath = "/home/user/temp/dedupe.log"
    #save_dir = "/home/user/temp/"

    #Test paths
    #tsdir = "/home/user/temp/srcx/"
    #tddir = "/home/user/temp/src2/"
    #tlpath = "/home/user/temp/test_dedupe.log"
    #tsave_dir = "/home/user/temp/test_"
    
    #Construct an ArgumentParser to handle command line arguments
    parser = argparse.ArgumentParser(description="Music collection deduper")
    parser.add_argument("scan_dir", help="The directory to scan for music")

    cmgroup = parser.add_argument_group("Compare Modes (required)")
    cmgroup.add_argument("-a", "--audio", help="Compare files based on a hash of the audio content (slower)", dest="comp_mode", action="store_const", const=Modes.audio)
    cmgroup.add_argument("-f", "--full", help="Compare files based on a hash of the entire file (faster)", dest="comp_mode", action="store_const", const=Modes.full)

    parser.add_argument("--list", "-l", help="List files that are duplicates instead of moving them", action="store_true", default=False)
    parser.add_argument("--xfile","-x", help="Path to hashes file")
    parser.add_argument("--export", "-e", metavar="path", help="File to which the duplicate list should be exported")
    
    #tmgroup = parser.add_argument_group("Run Modes (default: test)")
    #tmgroup.add_argument("-t", "--test", help="Use test files / paths", dest="test_mode", action="store_true")
    #tmgroup.add_argument("-r", "--real", help="Use test files / paths", dest="test_mode", action="store_false")
    oagroup = parser.add_argument_group("Other")
    oagroup.add_argument("-s", "--skip", metavar="N", nargs=1, type=int, default=0)
    #parser.set_defaults(test_mode=True)
    
    #Parse and process the given command line arguments
    args = parser.parse_args()

    if args.comp_mode is None:                                                #If the compare mode was not provided
        parser.print_help()                                                     #Print the help text
        parser.exit(0, "Compare mode is a required parameter!\n")                #Exit
    elif not args.list:
        parser.print_help()
        parser.exit(0, "Error: Moving files is not currently supported.  Please use --list.")
    
    export = False
    if args.export is not None:
        export = True
        efile = open(args.export, "w", encoding="utf-8")
    
    #paths = getFilteredPaths(args.dir, "mp3")
    logPath = getUnusedPath("/home/user/temp/", "dedupe", "log")
    
    deduperx = DeDuper(args.scan_dir, None, logPath, args.xfile)
    hashes = deduperx.dedupe(args.comp_mode, args.skip).getHashes()            #Run the DeDuper
    
    clio.println()
    
    dupes = {h:hashes[h] for h in hashes if (len(hashes[h]) > 1)}
    for d in dupes:
        line = d + "\t" + ("\t".join(dupes[d]))
        if export:
            efile.write(line + "\n")
        print(line)
    
    #if args.test_mode:                                                            #If testing
    #    clio.println("TEST MODE")
    #    deduper1 = DeDuper(tsdir, tddir, tlpath, tsave_dir)                    #Then construct with test paths
    #else:                                                                        #Otherwise
    #    deduper1 = DeDuper(sdir, ddir, lpath, save_dir)                        #Construct with real paths
    #deduper1.dedupe(args.comp_mode, args.skip)                                    #Run the DeDuper

class Modes(Enum):
    audio = 1
    full = 2


class HashException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class DeDuper():
    """
    Class to wrap the methods used for deduping music in a given directory
    """
    def __init__(self, sdir, ddir, lpath, save_dir):
        self.debugMode = True
        self.sdir = sdir
        self.ddir = ddir
        self.errlog = ErrorLog(lpath)
        self.log = self.errlog.record
        self.save_dir = save_dir
    
    def dedupe(self, mode, skip=0):
        self.mode = mode
        return self.processDirectory(skip)
    
    def getHash(self, fpath):
        """
        Calculates and returns the hash for the given file based on the current mode
        """
        if fpath[-3:].lower() != "mp3":
            raise HashException("Skipping non-mp3 file: " + fpath)
        elif self.mode == Modes.audio:
            try:
                tag = eyeD3.Tag()                                                #Initialize a new eyeD3 Tag
                mfile = tempfile.SpooledTemporaryFile()                        #Initialize a temporary file in memory
                mfile.write(open(fpath, "rb").read())                            #Copy the contents of the file into memory
                tag.link(mfile)                                                #Process the file for Id3 tags
                tag.remove(eyeD3.ID3_ANY_VERSION)                                #Remove all ID3 (v1 & v2) tags from the temporary file in memory
                mfile.seek(0)                                                    #Need to move the pointer back to the beginning before hashing
                return hashlib.sha256(mfile.read()).hexdigest()                #Return the hash of the audio content of the file
            except Exception as e:
                raise HashException("Unable to decode file: " + fpath)
        elif self.mode == Modes.full:
            try:
                return hashlib.sha256(open(fpath,"rb").read()).hexdigest()
            except (OSError, IOError):
                raise HashException("Unable to open file: " + fpath)
        else:
            raise HashException("Invalid mode!")
    
    def getExistingHashes(self):
        """
        Builds dictionary of hashes of files already in the destination dir
        """
        self.log2("Scanning for saved hashes...")
        hashes = HashList(self.mode, self.save_dir)                            #Initialize a new HashList with the mode and save location
        
        if self.ddir is None:
            return hashes
        
        paths = getFilteredPaths(self.ddir, "mp3")
        
        #fnames = os.listdir(self.ddir)                                            #Array of file names (relative path) in the destination dir
        #t = len(fnames)                                                        #Total number of files in the destination dir
        t = len(paths)
        tl = str(len(str(t)))                                                    #Length of that number as a string
        
        if (hashes.count() == t):                                                #If the destination dir contains as many files as there were hashes saved
            self.log2("Saved list appears to match destination directory!")
            return hashes                                                        #Return that list
        else:
            self.log2("Saved list did not appear to match destination directory.")
            hashes.reset()                                                        #Otherwise, reset the saved list and rebuild it
        #/if
        
        self.log2("Scanning destination directory for existing files...")
        
        spfmt = "[{}][{:7.2%}|{:"+str(len(str(t)))+"d}/"+str(t)+"][{:,.2f} files/sec]Current: {}"
        
        #spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}]"                    #Show progress report format
        #spfmt += "[Rate: {:7,.2f} files/sec][Remaining: ~{}] Current file: {}"
        
        pt = PerfTimer()
        #ltime = pt.time()
        last_time = pt.elapsed()
        
        c = 0                                                                    #Counter
        #for fname in fnames:                                                    #Iterate through each file name in the destination dir
        for fpath in paths:
            c += 1
            dt = pt.elapsed()
            rate = c/dt
            if ((dt - last_time) > 0.25):
                last_time = dt
                clio.showf(spfmt, fTime(dt), c/t, c, rate, fpath)
            
            #c += 1                                                                #Increment the counter
            #dt = pt.elapsed()
            #rpath = fname                                                        #Relative path [future]
            #fpath = self.ddir + rpath                                            #Rebuild the absolute path for the file
            #if (pt.elapsed(ltime) > 0.25):                                        #If it's been over 250ms since last progress report
            #    ltime = pt.time()
            #    rate = c/dt
            #    remaining = fTime((t-c) / rate)
            #    clio.showf(spfmt, c/t, c, pt.elapsedf(), rate, remaining, rpath)    #Show current progress report
            
            try:
                fhash = self.getHash(fpath)                                    #Get the hash for the current mode
                hashes.add(fhash, fpath)                                        #Add the hash to the HashList
            except HashException as e:                                            #Log any errors
                self.log2("[ERROR] " + e.value)
            except Exception as ue:
                self.log2("[ERROR] Unexpected {} on file: {}".format(type(ue).__name__, fpath))

        self.log2("Destination directory scan complete! Found {:d} files.".format(hashes.count()))
        clio.println("Destination directory scan runtime: " + pt.elapsedf())
        return hashes
    
    def processDirectory(self, skip):
        ifmt = "Determining file uniqueness via {} content hash..."            #Intro format string
        self.log2(ifmt.format(self.mode.name))                                    #Display intro
        
        hashes = self.getExistingHashes()                                        #Get the Dictionary of hashes found
        
        self.log2("Processing source directory and copying unique files...")
        if skip > 0:
            self.log2("Skipping the first {:,d} files without scanning them!".format(skip))
        else:
            skip = 0
        
        #fnames = os.listdir(self.sdir)                                            #Array of file names (relative path)
        paths = getFilteredPaths(self.sdir, "mp3")
        t = len(paths)
        #t = len(fnames)                                                        #Total number of files to process
        
        t -= skip                                                                #Ignore the files being skipped for purposes of the total count
        tl = str(len(str(t)))                                                    #Length of that number as a string
        pfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"] {} {} {}"                        #Format string for progress reports
        spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}][Copied: {:8,d}]"    #Show progress report format
        spfmt += "[Skipped: {:8,d}][Errors: {:8,d}][Rate: {:,.2f} files/sec][Remaining: ~{}]"
        copied = 0                                                                #Counter for copied files
        skipped = 0                                                            #Counter for skipped files
        errors = 0                                                                #Counter for errors
        c = 0                                                                    #Counter for total files processed
        k = 0                                                                    #Counter for files skipped without scanning
        pt = PerfTimer()                                                        #Initialize a PerfTimer with the current time
        last_time = pt.elapsed()
        
        #for fname in fnames:                                                    #Iterate through each file name
        for fpath in paths:
            if k < skip:                                                        #If the skip counter hasn't reached the file to skip to yet
                k += 1                                                            #Increment the skip counter
                continue                                                        #Skip to the next iteration of the for loop
            c += 1                                                                #Increment the counter
            dt = pt.elapsed()
            rate = c/dt
            remaining = fTime((t-c) / rate)
            if ((dt - last_time) > 0.25):
                last_time = dt
                clio.showf(spfmt, c/t, c, pt.elapsedf(), copied, skipped, errors, rate, remaining)#Show current progress report

            #rpath = fname                                                        #Relative path [future]
            #fpath = self.sdir + rpath                                            #Rebuild the absolute path for the file
            try:
                fhash = self.getHash(fpath)                                    #Get the hash for the given mode
                if (not hashes.contains(fhash, fpath)):                            #If the destination doesn't already have a file with that hash
                    copied += 1                                                #Increment the copied counter
                    #hashes.add(fhash, fpath)                                            #Add the hash to the HashList
                    #shutil.copy(fpath, self.ddir)                                #Copy the file to the destination
                    #self.dbg(pfmt.format(c/t, c, "Copying  ", fhash, rpath))
                else:                                                            #If the hash was already moved to the destination
                    skipped += 1                                                #Increment the skipped counter
                    self.dbg(pfmt.format(c/t, c, "Skipping ", fhash, fpath))
            except HashException as e:                                            #Log any errors
                errors += 1
                self.log2("[ERROR] " + e.value)
            except Exception as ue:
                errors += 1
                self.log2("[ERROR] Unexpected {} on file: {}".format(type(ue).__name__, fpath))
                clio.println(ue.message)
        
        fmt = "{}   {:" + tl + "d} ({:.2%})"
        clio.println("Done!")
        clio.printf("Processed: {:d}", t)
        clio.printf(fmt, "Copied: ", copied, copied/t)
        clio.printf(fmt, "Skipped:", skipped, skipped/t)
        clio.printf(fmt, "Errors: ", errors, errors/t)
        clio.println("Runtime: " + pt.elapsedf())
        
        return hashes
    
    def dbg(self, msg):
        if self.debugMode:
            clio.println(msg)
    
    def log2(self, msg):
        clio.println(msg)
        self.log(msg)


class HashList():
    """
    A list of file hashes that saves the values to file so they can be recovered later
    """
    def __init__(self, mode, save_dir=None):
        self.hashes = {}                                                        #Initialize the dictionary for storing hashes
        if save_dir is None:
            self.save = False
        else:
            self.save = True        
            fpath = save_dir + "hashes_" +  mode.name + ".tmp"                        #Construct the full path for the save file
            if os.path.isfile(fpath):                                                #If the save file already exists, load the entries in it
                hfile = open(fpath, "r")                                            #Open it for reading
                for line in hfile.read().splitlines():                                #Iterate through each line
                    self.hashes[line] = True                                        #Add the line to the dictionary
                hfile.close()                                                        #Close the file
            self.file = open(fpath, "a")                                            #Open the file in append mode
            self.fpath = fpath                                                        #Store the file path
    
    def reset(self):
        if self.save:
            self.file.close()                                                    #Close the existing file
            self.file = open(self.fpath, "w")                                    #Re-open file in write mode, which overwrites the existing file
        self.hashes = {}                                                        #Reset the dictionary of hashes
    
    #def add(self, fhash, fpath):
    #    if fhash not in self.hashes:
    #        self.hashes[fhash] = []
    #        if self.save:
    #            self.file.write(fhash + "\n")                                    #Append it to the save file
    #            self.file.flush()                                                #Make sure the line is written to disk
    #    self.hashes[fhash].append(fpath)
    #/add
    
    def contains(self, fhash, fpath):
        contained = (fhash in self.hashes)
        if not contained:
            self.hashes[fhash] = []
            if self.save:
                self.file.write(fhash + "\n")                                    #Append it to the save file
                self.file.flush()                                                #Make sure the line is written to disk
        self.hashes[fhash].append(fpath)
        return contained
    
    def getHashes(self):
        return self.hashes                                                        #Return the full dictionary of hashes
    
    def count(self):
        return len(self.hashes)                                                #Return the count of hashes in the dictionary
    
    def close(self):
        if self.save:
            self.file.close()                                                    #Close the save file


if __name__ == "__main__":
    #main(sys.argv)
    main()

