#!/usr/bin/python3

'''
Author: Douglas Skrypa
Date: 2015.12.30
Version: 4
'''

import os, sys;
from pydub import AudioSegment;
import hashlib;
import shutil;
import time;

debugMode = True;

def main(args):
	sdir = "/home/user/temp/src/";
	ddir = "/home/user/temp/dest/";
	
	stime = time.perf_counter();
	
	try:
		if (args[1] == "audio"):
			(copied, skipped, total) = hashAudio(sdir, ddir);
		elif (args[1] == "full"):
			(copied, skipped, total) = hashFull(sdir, ddir);
		else:
			helpAndExit();
		#/if
	except IndexError:
		helpAndExit();
	#/try
	
	tl = str(len(str(total)));
	fmta = "Processed: {:d}";
	fmtb = "Copied:    {:" + tl + "d} ({:.2%})";
	fmtc = "Skipped:   {:" + tl + "d} ({:.2%})";
	
	print("Done!");
	print(fmta.format(total));
	print(fmtb.format(copied, copied/total));
	print(fmtc.format(skipped, skipped/total));
	
	etime = time.perf_counter();
	rtime = etime-stime;
	print("Runtime: " + time.strftime("%H:%M:%S",time.gmtime(rtime)));
#/main

def helpAndExit():
	print("Valid parameters: audio, full");
	sys.exit(0);
#/helpAndExit	

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
	print("Moving if they are unique based on the hash of their audio content...");
	fnames = os.listdir(sdir);											#Array of file names (relative path)
	hashes = getExistingHashes(ddir, "audio");							#Dictionary of hashes found
	
	c = 0;																#Counter
	copied = 0;															#Counter for copied files
	skipped = 0;														#Counter for skipped files
	k = len(fnames);													#Number of files to process
	ksl = len(str(k));													#Length of that number as a string
	fmt = "[{:4.0%}|{:" + str(ksl) + "d}/" + str(k) + "] {} {} {}";		#Format string for progress reports
	
	for fname in fnames:												#Iterate through each file name
		c += 1;															#Increment the counter
		fpath = sdir + fname;											#Rebuild the absolute path for the file
		
		sound = AudioSegment.from_mp3(fpath);							#Extract the audio segment from the mp3
		fhash = hashlib.md5(sound.raw_data).hexdigest();				#Hash the audio segment
		
		if fhash not in hashes:											#If the hash wasn't already moved to the destination
			copied += 1;												#Increment the copied counter
			hashes[fhash] = True;										#Add the hash to the dictionary
			shutil.copy(fpath, ddir);									#Copy the file to the destination
			dbg(fmt.format(c/k, c, "Copying  ", fhash, fpath));
		else:															#If the hash was already moved to the destination
			skipped += 1;												#Increment the skipped counter
			dbg(fmt.format(c/k, c, "Skipping ", fhash, fpath));
		#/if
	#/for
	
	return (copied, skipped, k);
#/hashAudio

def hashFull(sdir, ddir):
	print("Moving if they are unique based on the hash of their full content...");
	fnames = os.listdir(sdir);											#Array of file names (relative path)
	hashes = getExistingHashes(ddir, "full");							#Dictionary of hashes found
	
	c = 0;																#Counter
	copied = 0;															#Counter for copied files
	skipped = 0;														#Counter for skipped files
	k = len(fnames);													#Number of files to process
	ksl = len(str(k));													#Length of that number as a string
	fmt = "[{:4.0%}|{:" + str(ksl) + "d}/" + str(k) + "] {} {} {}";		#Format string for progress reports
	
	for fname in fnames:												#Iterate through each file name
		c += 1;															#Increment the counter
		fpath = sdir + fname;											#Rebuild the absolute path for the file
		
		bfile = open(fpath,"rb");										#Open the file as a binary file
		fhash = hashlib.md5(bfile.read()).hexdigest();					#Hash the entire file
		
		if fhash not in hashes:											#If the hash wasn't already moved to the destination
			copied += 1;												#Increment the copied counter
			hashes[fhash] = True;										#Add the hash to the dictionary
			shutil.copy(fpath, ddir);									#Copy the file to the destination
			dbg(fmt.format(c/k, c, "Copying  ", fhash, fpath));
		else:															#If the hash was already moved to the destination
			skipped += 1;												#Increment the skipped counter
			dbg(fmt.format(c/k, c, "Skipping ", fhash, fpath));
		#/if
	#/for
	
	return (copied, skipped, k);
#/hashFull

def dbg(str):
	if debugMode:
		print(str);
#/dbg

if __name__ == "__main__":
	main(sys.argv);
#/__main__
