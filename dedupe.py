#!/usr/bin/python3

'''
Author: Douglas Skrypa
Date: 2015.12.30
Version: 2
'''

import os;
from pydub import AudioSegment;
import hashlib;
import shutil;

debugMode = True;

def main():
	sdir = "/home/user/temp/src/";
	ddir = "/home/user/temp/dest/";
	
	fnames = os.listdir(sdir);									#Array of file names (relative path)
	hashes = {};												#Dictionary of hashes found
	
	c = 0;
	k = len(fnames);
	ksl = len(str(k));
	fmt = "{} [{:" + str(ksl) + "d}/" + str(k) + "] {} {}";
	
	for fname in fnames:
		c += 1;
		fpath = sdir + fname;
		
		sound = AudioSegment.from_mp3(fpath);
		fhash = hashlib.md5(sound.raw_data).hexdigest();
		
		if fhash not in hashes:
			hashes[fhash] = True;
			shutil.copy(fpath, ddir);
			dbg(fmt.format(fhash, c, "Copying  ", fpath));
		else:
			dbg(fmt.format(fhash, c, "Skipping ", fpath));
		#/if
	#/for
#/main

def dbg(str):
	if debugMode:
		print(str);
#/dbg

if __name__ == "__main__":
	main();
#/__main__
