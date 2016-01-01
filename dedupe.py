#!/usr/bin/python3

'''
Author: Douglas Skrypa
Date: 2015.12.30
Version: 3
'''

import os;
from pydub import AudioSegment;
import hashlib;
import shutil;
import time;

debugMode = True;

def main():
	sdir = "/home/user/temp/src/";
	ddir = "/home/user/temp/dest/";
	
	stime = time.perf_counter();
	
	hashAudio(sdir, ddir);
	
	etime = time.perf_counter();
	rtime = etime-stime;
	print("Runtime: " + time.strftime("%H:%M:%S",time.gmtime(rtime)));
#/main

def getExistingHashes(ddir, mode):
	'''
	Builds a dictionary with the hashes of the files already in the
	destination directory.
	'''
	fnames = os.listdir(ddir);	#Array of file names (relative path)
	hashes = {};
	if (mode == "audio"):
		for fname in fnames:
			fpath = ddir + fname;
			sound = AudioSegment.from_mp3(fpath);
			fhash = hashlib.md5(sound.raw_data).hexdigest();
			hashes[fhash] = True;
		#/for
	else:
		for fname in fnames:
			fpath = ddir + fname;
			fhash = hashlib.md5(open(fpath,"rb").read()).hexdigest();
			hashes[fhash] = True;
		#/for
	#/if
	return hashes;
#/getExistingHashes

def hashAudio(sdir, ddir):
	fnames = os.listdir(sdir);								#Array of file names (relative path)
	hashes = getExistingHashes(ddir,"audio");				#Dictionary of hashes found
	
	c = 0;													#Counter
	copied = 0;												#Counter for copied files
	skipped = 0;											#Counter for skipped files
	k = len(fnames);										#Number of files to process
	ksl = len(str(k));										#Length of that number as a string
	fmt = "{} [{:" + str(ksl) + "d}/" + str(k) + "] {} {}";	#Format string for progress reports
	
	for fname in fnames:									#Iterate through each file name
		c += 1;												#Increment the counter
		fpath = sdir + fname;								#Rebuild the absolute path for the file
		
		sound = AudioSegment.from_mp3(fpath);				#Extract the audio segment from the mp3
		fhash = hashlib.md5(sound.raw_data).hexdigest();	#Hash the audio segment
		
		if fhash not in hashes:								#If the hash wasn't already moved to the destination
			copied += 1;									#Increment the copied counter
			hashes[fhash] = True;							#Add the hash to the dictionary
			shutil.copy(fpath, ddir);						#Copy the file to the destination
			dbg(fmt.format(fhash, c, "Copying  ", fpath));
		else:												#If the hash was already moved to the destination
			skipped += 1;									#Increment the skipped counter
			dbg(fmt.format(fhash, c, "Skipping ", fpath));
		#/if
	#/for
	
	print("Done!");
	print("Copied:  " + str(copied));
	print("Skipped: " + str(skipped));
#/hashAudio

def hashFull(sdir, ddir):
	fnames = os.listdir(sdir);								#Array of file names (relative path)
	hashes = getExistingHashes(ddir,"full");				#Dictionary of hashes found
	
	c = 0;													#Counter
	copied = 0;												#Counter for copied files
	skipped = 0;											#Counter for skipped files
	k = len(fnames);										#Number of files to process
	ksl = len(str(k));										#Length of that number as a string
	fmt = "{} [{:" + str(ksl) + "d}/" + str(k) + "] {} {}";	#Format string for progress reports
	
	for fname in fnames:									#Iterate through each file name
		c += 1;												#Increment the counter
		fpath = sdir + fname;								#Rebuild the absolute path for the file
		
		bfile = open(fpath,"rb");							#Open the file as a binary file
		fhash = hashlib.md5(bfile.read()).hexdigest();		#Hash the entire file
		
		if fhash not in hashes:								#If the hash wasn't already moved to the destination
			copied += 1;									#Increment the copied counter
			hashes[fhash] = True;							#Add the hash to the dictionary
			shutil.copy(fpath, ddir);						#Copy the file to the destination
			dbg(fmt.format(fhash, c, "Copying  ", fpath));
		else:												#If the hash was already moved to the destination
			skipped += 1;									#Increment the skipped counter
			dbg(fmt.format(fhash, c, "Skipping ", fpath));
		#/if
	#/for
	
	print("Done!");
	print("Copied:  " + str(copied));
	print("Skipped: " + str(skipped));
#/hashFull

def dbg(str):
	if debugMode:
		print(str);
#/dbg

if __name__ == "__main__":
	main();
#/__main__
