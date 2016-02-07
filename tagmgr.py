#!/usr/bin/python

'''
Author: Douglas Skrypa
Date: 2016.02.07
Version: 4.3
'''

from __future__ import division, unicode_literals;
import sys;
PY2 = (sys.version_info.major == 2);
if PY2:
	import codecs;
	open = codecs.open;
#/if Python 2.x

from argparse import ArgumentParser;
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
	parser.add_argument("--export", "-e", metavar="destination", help="Write commands that should be performed to the specified file instead of executing them.");
	parser.add_argument("--noaction", "-n", help="Don't move any files, just print where they would go", action="store_true", default=False);
	parser.add_argument("--verbose", "-v", help="Print more info about what is happening", action="store_true", default=False);
	parser.add_argument("--limit", "-l", metavar="N", type=int, help="Limit the number of songs' info that is printed", default=-1);
	parser.add_argument("--trim", "-t", help="Trim leading and trailing spaces in primary tags.", action="store_true", default=False);
	parser.add_argument("--analyzeDupes", "-a", help="Print a list of songs that are duplicates based on metadata", action="store_true", default=False);
	parser.add_argument("--undupe", "-u", help="Change destinations based on duplicate metadata", action="store_true", default=False);
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
	
	export = False;
	if (args.export != None) and ((args.move != None) or (args.copy != None)):
		if os.path.isdir(args.export):
			parser.print_help();
			parser.exit(0, "Invalid export path; must provide file name: " + args.export);
		else:
			export = True;
			efile = open(args.export, "w", encoding="utf-8");
	
	limit = (args.limit > -1);
	
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
	elif args.analyzeDupes:
		pmgr = PlacementManager(None);
	
	efmt = (('cp' if copyMode else 'mv') + ' "{}" "{}"\n') if export else None;	#Set the export format string
	paths = getFilteredPaths(args.dir, "mp3");
	rfmt = "{:" + str(max([len(p) for p in paths])) + "} -> {}";				#Set the reorganize format string
	c = 0;
	t = len(paths);
	spfmt = "[{}][{:7.2%}|{:"+str(len(str(t)))+"d}/"+str(t)+"][{:,.2f} files/sec]Current: {}";
	pt = PerfTimer();
	last_time = pt.elapsed();
	
	for path in paths:
		c += 1;
		dt = pt.elapsed();
		rate = c/dt;
		if ((dt - last_time) > 0.25):
			last_time = dt;
			clio.showf(spfmt, fTime(dt), c/t, c, rate, path);
		
		song = Song(path);
		compStr = " [Compilation]" if song.hasTag("TCMP") else "";
		
		if removeMode:
			for rtag in toRemove:
				song.remTag(rtag, toRemove[rtag]);
		
		if args.trim:
			changed = song.trimTags();
			if (len(changed) > 0):
				clio.println();
				clio.println(path + compStr);
				cws = getWidths(changed);
				trmdfmt = "Changed {:" + str(cws[0]) + "}: {}";
				for chng in changed:
					clio.printf(trmdfmt, chng, changed[chng]);
		
		tags = song.getTags();
		if args.printTags:
			clio.println();
			clio.println(path + compStr);
			lttdl = 0;
			for tag in tags:
				ttdl = len(tagTypes[tag['id']]);
				lttdl = ttdl if (ttdl > lttdl) else lttdl;
			tfmt = "{0[ver]} {0[id]} {1:" + str(lttdl) + "} {0[val]}";
			for tag in tags:
				clio.printf(tfmt, tag, tagTypes[tag["id"]]);
		elif showFilter:
			stags = [tag for tag in tags if (tag["id"] in toShow)];
			if (len(stags) > 0):
				clio.println();
				clio.println(path + compStr);
				lttdl = 0;
				for tag in stags:
					ttdl = len(tagTypes[tag['id']]);
					lttdl = ttdl if (ttdl > lttdl) else lttdl;
				tfmt = "{0[ver]} {0[id]} {1:" + str(lttdl) + "} {0[val]}";
				for tag in stags:
					tid = tag["id"];
					if ((tid in toShow) and ((toShow[tid] == None) or (int(tag["ver"]) == toShow[tid]))):
						clio.printf(tfmt, tag, tagTypes[tid]);
		
		if reorganize:
			opath, npath = pmgr.addSong(song);
			if export and (npath != None):
				efile.write(efmt.format(opath, npath));
		elif args.analyzeDupes:
			pmgr.addSong(song);
			
		if limit and (args.limit <= c):
			break;
	#/for processing files
	
	if reorganize:
		if args.undupe:
			moves = pmgr.analyzeSongs();
			for opath in moves:
				song = moves[opath];
				better = song.isBetter();
				if (better != None):
					basedir = args.copy if copyMode else args.move;
					basedir = basedir[:-1] if (basedir[-1:] == "/") else basedir;
					npath = song.getNewPath();
					npath = opath if (npath == None) else npath;
					rpath = npath[len(basedir):]; 
					dpath = "/dupe_better" if better else "/dupe_worse";
					moves[opath].setNewPath(basedir + dpath + rpath);
		else:
			moves = pmgr.getMoves();
		
		if args.noaction:			
			for orig in moves:
				dest = moves[orig].getNewPath();
				if (dest != None):
					clio.printf(rfmt, orig, dest);
		else:
			func = shutil.copy if copyMode else os.renames;
			for orig in moves:
				dest = moves[orig].getNewPath();
				
				if (dest != None):				
					spos = dest.rfind("/");
					if (spos != -1):
						destDir = dest[:spos+1];
						if not os.path.isdir(destDir):
							os.makedirs(destDir);
						if args.verbose:
							clio.printf(rfmt, orig, dest);
						func(orig, dest);
					else:
						clio.println("Invalid path: " + dest);
				#else:
				#	clio.println("Matching file exists in destination: " + orig);
	
	if args.analyzeDupes:
		pmgr.analyzeSongs(True);
	#/reorganize
	
	clio.println();
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
		self.analyzeOnly = (ddir == None);
		if not self.analyzeOnly:
			self.ddir = ddir[:-1] if (ddir[-1:] == "/") else ddir;
		else:
			self.ddir = "";
		self.mdir = self.ddir + "/mismatches/";
		self.cdir = self.ddir + "/compilations/";
		self.pdir = self.ddir + "/podcasts/";
		self.vdir = self.ddir + "/valid/";
		self.bdir = self.ddir + "/missing_info/";
		self.fdir = self.ddir + "/bad_files/";
		self.moves = {};														#Store paths as new:old for easy destination conflict check
		self.movez = {};
		self.songs = {};
	#/init
	
	def analyzeSongs(self, display=False):
		#self.songs[xartist][album][title]
		clio.println();
		fmt = "{}\t{}\t{}\t{}\t{}\t{}\t{}";
		if display:
			print("Copy\tBest\tBitrate\tArtist\tAlbum\tTitle\tPath");
		#dupes = [];
		for artist in self.songs:
			for album in self.songs[artist]:
				for title in self.songs[artist][album]:
					scount = len(self.songs[artist][album][title]);
					if (scount > 1):
						#dupes.append(self.songs[artist][album][title]);
						dupez = [];
						bitrates = [];
						for s in range(scount):
							song = self.songs[artist][album][title][s];
							br = song.getBitrate();
							bitrates.append(br);
							dupez.append([br, song.fpath]);
						brmax = max(bitrates);
						for s in range(scount):
							br, fpath = dupez[s];
							best = (br == brmax);
							oldPath = self.songs[artist][album][title][s].fpath;
							self.moves[oldPath].setBetter(best);
							if display:
								print(fmt.format(s, best, br, artist, album, title, fpath));
		return self.moves;
	#/analyzeSongs
	
	def getMoves(self):
		return self.moves;
	#/getMoves
	
	def addSong(self, song):
		npath = self.getNewPath(song);
		self.movez[npath] = song.fpath;
		#self.moves[song.fpath] = npath;
		song.setNewPath(npath);
		self.moves[song.fpath] = song;
		return (song.fpath, npath);
	#/addSong
	
	def getNewPath(self, song):
		tags = song.getTags();
		tagsMismatched = False;
		oldFname = os.path.basename(song.fpath);
		
		if song.isBad():
			return self.getUnusedName(song, self.fdir, oldFname);
		#/bad file
		
		try:
			albArtist = cleanup(song.getTagVal("TPE2", True));
			artist = cleanup(song.getTagVal("TPE1", True));
			album = cleanup(song.getTagVal("TALB", True));
			title = cleanup(song.getTagVal("TIT2", True));
			tnum = song.getTrack();
			fields = (artist, album, title);
			xartist = albArtist if ((albArtist != None) and (len(albArtist) > 0)) else artist;
		except SongException as e:
			tagsMismatched = True;
		
		if tagsMismatched:
			return self.getUnusedName(song, self.mdir, oldFname);
		elif (None in fields) or ("" in fields):
			npath = self.bdir;
			if (album != None):
				npath = "{}albums/{}".format(self.bdir, album[:255]);
			elif (xartist != None):
				npath = "{}artists/{}".format(self.bdir, xartist[:255]);
			return self.getUnusedName(song, npath, oldFname);
		else:
			if (tnum == None):
				tn = "XX";
			else:
				try:
					tn = int(tnum.split("/")[0]) if ("/" in tnum) else int(tnum);
				except ValueError as verr:
					return self.getUnusedName(song, self.fdir, oldFname);
				tn = "{:02}".format(tn);
			fname = "{} - {}".format(tn, title);
			
			ndir = self.vdir;
			if song.isPodcast():
				ndir = self.pdir;
			#/dir set for artist/album rpath
			if (song.isFromCompilation() or song.mayBeFromCompilation()):
				npath = "{}{}".format(self.cdir, album[:255]);
			else:
				npath = "{}{}/{}".format(ndir, xartist[:255], album[:255]);
			
			if (xartist not in self.songs):
				self.songs[xartist] = {};
			if (album not in self.songs[xartist]):
				self.songs[xartist][album] = {};
			if (title not in self.songs[xartist][album]):
				self.songs[xartist][album][title] = [];
			self.songs[xartist][album][title].append(song);
			
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
			else:
				ext = "UNKNOWN";
		bnmax = 254 - len(ext);													#Max allowable length for base name assuming 255 char limit
		fpath = bpath + "/" + basename[:bnmax] + "." + ext;
		c = 0;
		shash = None;															#Song Hash, if necessary for preventing duplicates
		while ((fpath in self.movez) or (os.path.exists(fpath))):
			if os.path.exists(fpath):
				if (fpath == song.fpath):										#If this is the same file, then it shouldn't be moved
					return None;
				if (shash == None):
					shash = hashlib.sha512(open(song.fpath,"rb").read()).hexdigest();
				fhash = hashlib.sha512(open(fpath,"rb").read()).hexdigest();
				if (shash == fhash):
					return None;
			c += 1;
			nbnmax = bnmax + len(str(c));
			fpath = bpath + "/" + basename[:nbnmax] + str(c) + "." + ext;
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
