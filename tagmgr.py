#!/usr/bin/python

'''
Author: Douglas Skrypa
Date: 2016.01.30
Version: 4
'''

from __future__ import division, unicode_literals;
from argparse import ArgumentParser;
from django.utils import text as dtext;
import re;
import os, shutil, hashlib;
import eyed3_79 as eyed3;

from common import *;
from _constants import *;
from songWrapper import *;


def main():
	parser = ArgumentParser(description="MP3 Tag Manager");
	parser.add_argument("--dir", "-d", help="The directory to scan for music", required=True);
	parser.add_argument("--remove", "-r", nargs="+", metavar="tagId[ver]", help="A tag to remove from all mp3s in the given directory, optionally with a version number (default: both)", action="append");
	parser.add_argument("--printTags", "-p", help="Print the list of tags and their contents for each file", action="store_true", default=False);
	parser.add_argument("--show", "-s", nargs="+", metavar="tagId[ver]", help="The tag IDs that should be displayed, optionally with a version number (default: both)", action="append");
	parser.add_argument("--move", "-m", metavar="destination", help="Destination directory for songs that should be moved");
	parser.add_argument("--copy", "-c", metavar="destination", help="Destination directory for songs that should be copied");
	parser.add_argument("--noaction", "-n", help="Don't move any files, just print where they would go", action="store_true", default=False);
	parser.add_argument("--verbose", "-v", help="Print more info about what is happening", action="store_true", default=False);
	args = parser.parse_args();
	
	print(args);
	removeMode = False;
	if (args.remove != None):
		removeMode = True;
		remTags = [item for sublist in args.remove for item in sublist];
		toRemove = {rtag[0:4].upper():sint(rtag[4:]) for rtag in remTags};		#Split the tags to remove into tag:version if they have one
		print("[Tag  Version  Description] to be removed:");
		for rtag in toRemove:
			tagDesc = tagTypes[rtag] if rtag in tagTypes else "???";
			print("{:4}  {:7}  {}".format(rtag, str(toRemove[rtag]), tagDesc));
	
	showFilter = False;
	if (args.show != None):
		showFilter = True;
		sTags = [item for sublist in args.show for item in sublist];
		toShow = {stag[0:4].upper():sint(stag[4:]) for stag in sTags};
		print("[Tag  Version  Description] to be displayed:");
		for stag in toShow:
			tagDesc = tagTypes[stag] if stag in tagTypes else "???";
			print("{:4}  {:7}  {}".format(stag, str(toShow[stag]), tagDesc));
	
	reorganize = False;
	copyMode = False;
	if (args.move != None) and (args.copy != None):
		parser.print_help();
		parser.exit(0, "Only one of move or copy can be used at a time");
	elif (args.move != None):
		pmgr = PlacementManager(args.move);
		reorganize = True;
	elif (args.copy != None):
		pmgr = PlacementManager(args.copy);
		reorganize = True;
		copyMode = True;
	
	paths = getFilteredPaths(args.dir, "mp3");
	
	c = 0;
	t = len(paths);
	tl = str(len(str(t)));
	spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}]";
	spfmt += "[Rate: {:,.2f} files/sec][Remaining: ~{}] Current file: {}";
	pt = PerfTimer();
	
	fmt = "{}  {}";
	
	for path in paths:
		c += 1;
		dt = pt.elapsed();
		rate = c/dt;
		remaining = fTime((t-c) / rate);
		clio.showf(spfmt, c/t, c, fTime(dt), rate, remaining, path);
		
		#try:
		song = Song(path);
		compStr = " [Compilation]" if song.hasTag("TCMP") else "";
		
		if removeMode:
			for rtag in toRemove:
				song.remTag(rtag, toRemove[rtag]);
				
		tags = song.getTags();
		if (args.printTags or showFilter):
			clio.println();
			clio.println(path + compStr);
			lttdl = 0;
			for tag in tags:
				ttdl = len(tagTypes[tag['id']]);
				lttdl = ttdl if (ttdl > lttdl) else lttdl;
			tfmt = "{0[ver]} {0[id]} {1:" + str(lttdl) + "} {0[val]}";
			for tag in tags:
				tid = tag["id"];
				if (not showFilter) or ((tid in toShow) and ((toShow[tid] == None) or (int(tag["ver"]) == toShow[tid]))):
					clio.printf(tfmt, tag, tagTypes[tid]);
		
		if reorganize:
			pmgr.addSong(song);
		#except Exception as e:
		#	clio.printf("[ERROR] {}: {}", path, str(e));
	
	if reorganize:
		moves = pmgr.getMoves();
		cws = getWidths(moves);
		fmt = "{:" + str(cws[0]) + "} -> {:" + str(cws[1]) + "}";
		
		if args.noaction:			
			for orig in moves:
				dest = moves[orig];
				clio.printf(fmt, orig, dest);
		else:
			func = shutil.copy if copyMode else os.renames;
			for orig in moves:
				dest = moves[orig];
				
				if (dest != None):				
					spos = dest.rfind("/");
					if (spos != -1):
						destDir = dest[:spos+1];
						if not os.path.isdir(destDir):
							os.makedirs(destDir);
						if args.verbose:
							clio.printf(fmt, orig, dest);
						func(orig, dest);
					else:
						clio.println("Invalid path: " + dest);
				else:
					clio.println("Matching file exists in destination: " + orig);
	#/reorganize
#/main

def getWidths(dict):
	kw = 0;
	vw = 0;
	for key in dict:
		klen = len(unicode(key));
		vlen = len(unicode(dict[key]));
		kw = klen if (klen > kw) else kw;
		vw = vlen if (vlen > vw) else vw;
	return (kw, vw);
#/getWidths

class PlacementManager():
	def __init__(self, ddir):
		self.ddir = ddir[:-1] if (ddir[-1:] == "/") else ddir;
		self.mdir = self.ddir + "/mismatches/";
		self.cdir = self.ddir + "/compilations/";
		self.vdir = self.ddir + "/valid/";
		self.bdir = self.ddir + "/missing_info/";
		self.moves = {};														#Store paths as new:old for easy destination conflict check
		self.movez = {};
	#/init
	
	def getMoves(self):
		return self.moves;
	#/getMoves
	
	def addSong(self, song):
		npath = self.getNewPath(song);
		self.movez[npath] = song.fpath;
		self.moves[song.fpath] = npath;
		return (song.fpath, npath);
	#/addSong
	
	def getNewPath(self, song):
		tags = song.getTags();
		tagsMismatched = False;
		isCompilation = song.isFromCompilation();
		oldFname = os.path.basename(song.fpath);
		
		try:
			albArtist = song.getTagVal("TPE2", True);
			artist = song.getTagVal("TPE1", True);
			album = song.getTagVal("TALB", True);
			title = song.getTagVal("TIT2", True);
			tnum = song.getTrack();
			fields = (artist, album, title);
		except SongException as e:
			tagsMismatched = True;
		
		if tagsMismatched:
			return self.getUnusedName(song, self.mdir, oldFname);
		elif (None in fields) or ("" in fields):
			return self.getUnusedName(song, self.bdir, oldFname);
		else:
			if (tnum == None):
				tn = "XX";
			else:
				tn = int(tnum.split("/")[0]) if ("/" in tnum) else int(tnum);
				tn = "{:02}".format(tn);
			
			fname = "{} - {}".format(tn, title);
			npath = "";
			if (isCompilation or (artist == "Various Artists")):
				npath = "{}{}".format(self.cdir, album);
			else:
				xartist = albArtist if (albArtist != None) else artist;
				npath = "{}{}/{}".format(self.vdir, xartist, album);
			return self.getUnusedName(song, npath, fname, "mp3");
	#/getNewPath

	def getUnusedName(self, song, basedir, fname, ext=None):
		bpath = basedir[:-1] if (basedir[-1:] == "/") else basedir;
		basename = fname;
		if (ext == None):
			ppos = fname.rfind(".");
			if (ppos != -1):
				basename = fname[:ppos];
				ext = fname[ppos+1:];
		fpath = bpath + "/" + basename + "." + ext;
		c = 0;
		shash = None;
		while ((fpath in self.movez) or (os.path.exists(fpath))):
			if os.path.exists(fpath):
				if (shash == None):
					shash = hashlib.sha512(open(song.fpath,"rb").read()).hexdigest();
				fhash = hashlib.sha512(open(fpath,"rb").read()).hexdigest();
				if (shash == fhash):
					return None;
			c += 1;
			fpath = bpath + "/" + basename + str(c) + "." + ext;
		return fpath;
	#/getUnusedName
#/PlacementManager

def sint(val):
	'''If val is castable to an integer, returns that integer, otherwise returns None'''
	try:
		return int(val);
	except ValueError:
		return None;
#/sint

if __name__ == "__main__":
	main();
#/__main__
