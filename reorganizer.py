#!/usr/bin/python3

'''
Author: Douglas Skrypa
Date: 2016.01.09
Version: 0.1
'''

import os, sys, shutil, time, hashlib, re, glob;
from argparse import ArgumentParser;
from common import *;

def main():
	mdir = "/media/user/IntelSSD/organized/";
	
	#sdir = "/home/user/temp/src/";
	sdir = "/media/user/IntelSSD/unduped_audio_hash/";
	
	parser = ArgumentParser(description="Music collection reorganizer");
	parser.add_argument("-v", "--verbose", help="Display original and new paths for each file being moved", action="store_true", default=False);
	parser.add_argument("-n", "--nomove", help="No action. Use this setting to see where files would be moved without actually moving them", action="store_true", default=False);
	parser.add_argument("-p", "--prep", help="Prepare the source directory by breaking it in to smaller folders", action="store_true", default=False);
	parser.add_argument("-a", "--acton", metavar="path", nargs=1, help="Act on rename info provided in path");
	args = parser.parse_args();
	
	print(args);
	
	if (args.prep):
		prepSource(sdir);
	
	if (args.acton != None):
		actPath = args.acton[0];
		if (not os.path.isfile(actPath)):
			parser.print_help();
			parser.exit(0, "Invalid path provided for info to act on: " + actPath);
		else:
			paths = loadActions(actPath);
			takeActions(paths, args.verbose, args.nomove);
	
	sys.exit(0);
	
	printf("Scanning {} for music...", mdir);
	music = scanDir(mdir);
	printf("Processing...");
	moves = processMusic(music);
	printf("Moving...");
	moveFiles(mdir, moves, args.verbose, args.nomove);
#/main

def prepSource(sdir):
	paths = getFilteredPaths(sdir, "mp3");
	c = 0;
	d = 1;
	dfmt = "/{:03d}/";
	newdir = dfmt.format(d);
	for path in paths:
		fname = os.path.basename(path);
		dname = os.path.dirname(path);
		if ((c % 100) == 0):
			d += 1;
			newdir = dfmt.format(d);
		newpath = dname + newdir + fname;
		printf("{}\t{}", path, newpath);
		c += 1;
#/prepSource

def printf(fmt, *args):
	print(fmt.format(*args));
#/printf

def takeActions(paths, verbose, nomove):
	for opath in paths:
		npath = paths[opath];
		if verbose:
			printf("{} -> {}", oldPath, newPath);
		if not nomove:
			os.renames(opath, npath);
#/takeActions

def loadActions(path):
	paths = {};
	for line in open(path, "r").read().splitlines():
		old_new = line.split("\t");
		paths[old_new[0]] = old_new[1];
	return paths;
#/loadActions

def moveFiles(baseDir, files, verbose, nomove):
	baseDir = baseDir[:-1] if (baseDir[-1:] == "/") else baseDir;
	
	for old_rel in files:
		oldPath = baseDir + old_rel;
		newPath = baseDir + files[old_rel];
		if verbose:
			printf("{} -> {}", oldPath, newPath);
		if not nomove:
			os.renames(oldPath, newPath);
	#/for
#/moveFiles

def processMusic(music):
	reorg = {"Billboard":"/Billboard/", "Now Thats What I Call Music":"/NowCompilations/"};
	moves = {};
	for artist in music:
		for album in music[artist]:
			for prefix in reorg:
				if (album.lower().startswith(prefix.lower())):
					tracks = music[artist][album];
					for fname in tracks:
						#music[artist][album][fname]["new_rel"] = reorg[prefix] + fname;
						#moves[tracks[fname]["old_rel"]] = reorg[prefix] + fname;
						moves[tracks[fname]["old_rel"]] = reorg[prefix] + album + "/" + fname;
					break;														#If the album name matched one prefix, it won't match another
				#/if album name matches prefix
			#/for each prefix in reorg
		#/for each album in artist
	#/for each artist
	return moves;
#/processMusic

def scanDir(mdir):
	paths = getFilteredPaths(mdir, "mp3");
	pparser = re.compile(r'^/([^/]+)/([^/]+)/(.*).mp3$', re.IGNORECASE);
	blen = len(mdir[:-1] if (mdir[-1:] == "/") else mdir);						#Length of the base dir's path
	music = {};
	for path in paths:
		rpath = path[blen:];
		m = pparser.match(rpath);
		if (m):
			artist = m.group(1);
			album = m.group(2);
			#filename = m.group(3);
			fname = os.path.basename(path);
			
			if (artist not in music):
				music[artist] = {};
			if (album not in music[artist]):
				music[artist][album] = {};
			music[artist][album][fname] = {"old_rel":rpath};
		else:
			raise Exception("ERROR: Invalid path: " + path);
	return music;
#/scanDir



if __name__ == "__main__":
	main();
#/__main__
