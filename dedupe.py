#!/usr/bin/python3

'''
Author: Douglas Skrypa
Date: 2015.12.31
Version: 6
'''

import os, sys, shutil, time, hashlib;
from pydub import AudioSegment;
from enum import Enum;

def main(args):
	sdir = "/media/user/WD_1TB_External_Backup/unduped_full_hash/";
	ddir = "/media/user/My Passport/unduped_audio_hash/";
	lpath = "/home/user/temp/dedupe.log";
	save_dir = "/home/user/temp/";

	tsdir = "/home/user/temp/src/";
	tddir = "/home/user/temp/dest/";
	tlpath = "/home/user/temp/test_dedupe.log";
	tsave_dir = "/home/user/temp/test_";

	mode = None;
	try:
		if (args[1] == "audio"):
			mode = Modes.audio;
		elif (args[1] == "full"):
			mode = Modes.full;
		else:
			helpAndExit();
	except IndexError:
		helpAndExit();
	#/try

	deduper1 = DeDuper(sdir, ddir, lpath, save_dir);
	deduper1.dedupe(mode);
#/main

def helpAndExit():
	prnt("Valid parameters: audio, full");
	sys.exit(0);
#/helpAndExit

class clio():
	'''		Command Line Interface Output		'''
	def fmt(msg):										#Format for output
		tcols = shutil.get_terminal_size()[0];			#Character columns available in the terminal window
		blanks = "";
		fc = tcols - len(msg);							#Fill Columns needed
		if (fc > 0):
			blanks = " " * fc;
		return "\r" + msg + blanks;
	#/fmt
	def show(msg):										#Show the given message and allow it to be overwritten
		sys.stdout.write(clio.fmt(msg));
		sys.stdout.flush();
	#/show
	def println(msg):									#Print the given message so that it overwrites a previously shown message
		sys.stdout.write(clio.fmt(msg) + "\n");
		sys.stdout.flush();
	#/print
#/clio

class Modes(Enum):
	audio = 1;
	full = 2;
#/Modes

class HashException(Exception):
	def __init__(self, value):
		self.value = value;
	def __str__(self):
		return repr(self.value);
#/HashException

class DeDuper():
	'''
	Class to wrap the methods used for deduping music in a given directory
	'''
	def __init__(self, sdir, ddir, lpath, save_dir):
		self.debugMode = True;
		self.sdir = sdir;
		self.ddir = ddir;
		self.errlog = ErrorLog(lpath);
		self.log = self.errlog.record;
		self.save_dir = save_dir;
	#/init
	
	def dedupe(self, mode):
		self.mode = mode;
		self.processDirectory();
	#/dedupe
	
	def getHash(self, fpath):
		'''
		Calculates and returns the hash for the given file based on the current mode
		'''
		if (self.mode == Modes.audio):
			if (fpath[-3:].lower() != "mp3"):
				raise HashException("Unable to hash audio for: " + fpath);
			#/if
			try:
				sound = AudioSegment.from_mp3(fpath);
				return hashlib.md5(sound.raw_data).hexdigest();
			except CouldntDecodeError:
				raise HashException("Unable to decode file: " + fpath);
		elif (self.mode == Modes.full):
			if (fpath[-3:].lower() != "mp3"):
				raise HashException("Skipping non-mp3 file: " + fpath);
			#/if
			try:
				return hashlib.md5(open(fpath,"rb").read()).hexdigest();
			except (OSError, IOError):
				raise HashException("Unable to open file: " + fpath);
		else:
			raise HashException("Invalid mode!");
	#/getHash
	
	def getExistingHashes(self):
		'''
		Builds dictionary of hashes of files already in the destination dir
		'''
		self.log2("Scanning for saved hashes...");
		hashes = HashList(self.mode, self.save_dir);							#Initialize a new HashList with the mode and save location
		fnames = os.listdir(self.ddir);											#Array of file names (relative path) in the destination dir
		t = len(fnames);														#Total number of files in the destination dir
		
		if (hashes.count() == t):												#If the destination dir contains as many files as there were hashes saved
			self.log2("Saved list appears to match destination directory!");
			return hashes;														#Return that list
		else:
			self.log2("Saved list did not appear to match destination directory.");
			hashes.reset();														#Otherwise, reset the saved list and rebuild it
		#/if
		
		self.log2("Scanning destination directory for existing files...");
		
		spfmt = "[{:7.2%}][Elapsed: {}] Current file: {}";						#Show progress report format
		stime = time.perf_counter();											#Start time
		ltime = stime;															#Last time progress was reported
		c = 0;																	#Counter
		
		for fname in fnames:													#Iterate through each file name in the destination dir
			c += 1;																#Increment the counter
			ctime = time.perf_counter();										#Current time
			dtime = ctime - stime;												#Time delta since start
			if ((ctime - ltime) > 1):											#If it's been over 1 second since last progress report
				ltime = ctime;													#Set last time to current time
				fte = time.strftime("%H:%M:%S",time.gmtime(dtime));				#Formatted time elapsed
				show(spfmt.format(c/t, fte, fname));							#Show current progress report
			#/if
			
			fpath = self.ddir + fname;											#Construct full path
			try:
				fhash = self.getHash(fpath);									#Get the hash for the current mode
				hashes.add(fhash);												#Add the hash to the HashList
			except HashException as e:											#Log any errors
				self.log2("[ERROR] " + e.value);
			except Exception as ue:
				self.log2("[ERROR] Unexpected {} on file: {}".format(type(ue).__name__, fpath));
			#/try
		#/for
		self.log2("Destination directory scan complete! Found {:d} files.".format(hashes.count()));
		
		etime = time.perf_counter();
		rtime = etime-stime;
		clio.println("Runtime: " + time.strftime("%H:%M:%S",time.gmtime(rtime)));
		
		return hashes;
	#/getExistingHashes
	
	def processDirectory(self):
		self.log2("Determining file uniqueness via {} content hash...".format(self.mode.name));
		spfmt = "[{:7.2%}][Elapsed: {}][Copied: {:8,d}][Skipped: {:8,d}][Errors: {:8,d}]";		#Show progress report format
		stime = time.perf_counter();											#Start time
		ltime = stime;															#Last time progress was reported
		
		fnames = os.listdir(self.sdir);											#Array of file names (relative path)
		hashes = self.getExistingHashes();										#Dictionary of hashes found
		
		self.log2("Processing source directory and copying unique files...");
		
		c = 0;																	#Counter
		copied = 0;																#Counter for copied files
		skipped = 0;															#Counter for skipped files
		errors = 0;																#Counter for errors
		t = len(fnames);														#Total number of files to process
		tl = str(len(str(t)));													#Length of that number as a string
		pfmt = "[{:7.2%}|{:" + tl + "d}/" + str(t) + "] {} {} {}";				#Format string for progress reports
		
		for fname in fnames:													#Iterate through each file name
			c += 1;																#Increment the counter
			ctime = time.perf_counter();										#Current time
			dtime = ctime - stime;												#Time delta since start
			if ((ctime - ltime) > 1):											#If it's been over 1 second since last progress report
				ltime = ctime;													#Set last time to current time
				fte = time.strftime("%H:%M:%S",time.gmtime(dtime));				#Formatted time elapsed
				show(spfmt.format(c/t, fte, copied, skipped, errors));			#Show current progress report
			#/if
			
			fpath = self.sdir + fname;											#Rebuild the absolute path for the file
			try:
				fhash = self.getHash(fpath);									#Get the hash for the given mode
				if (not hashes.contains(fhash)):								#If the destination doesn't already have a file with that hash
					copied += 1;												#Increment the copied counter
					hashes.add(fhash);											#Add the hash to the HashList
					shutil.copy(fpath, self.ddir);								#Copy the file to the destination
					self.dbg(pfmt.format(c/t, c, "Copying  ", fhash, fpath));
				else:															#If the hash was already moved to the destination
					skipped += 1;												#Increment the skipped counter
					self.dbg(pfmt.format(c/t, c, "Skipping ", fhash, fpath));
			except HashException as e:											#Log any errors
				errors += 1;
				self.log2("[ERROR] " + e.value);
			except Exception as ue:
				errors += 1;
				self.log2("[ERROR] Unexpected {} on file: {}".format(type(ue).__name__, fpath));
				prnt(ue.args)
		#/for
		
		fmta = "Processed: {:d}";
		fmtb = "{}   {:" + tl + "d} ({:.2%})"
		prnt("Done!");
		prnt(fmta.format(t));
		prnt(fmtb.format("Copied: ", copied, copied/t));
		prnt(fmtb.format("Skipped:", skipped, skipped/t));
		prnt(fmtb.format("Errors: ", errors, errors/t));
		
		etime = time.perf_counter();
		rtime = etime-stime;
		prnt("Runtime: " + time.strftime("%H:%M:%S",time.gmtime(rtime)));
	#/processDirectory
	
	def dbg(self, msg):
		if self.debugMode:
			prnt(msg);
	#/dbg
	
	def log2(self, msg):
		prnt(msg);
		self.log(msg);
	#/log2
#/DeDuper

class HashList():
	'''
	A list of file hashes that saves the values to file so they can be recovered later
	'''
	def __init__(self, mode, save_dir):
		self.hashes = {}										#Initialize the dictionary for storing hashes
		fpath = save_dir + "hashes_" +  mode.name + ".tmp";		#Construct the full path for the save file
		if os.path.isfile(fpath):								#If the save file already exists, load the entries in it
			hfile = open(fpath, "r");							#Open it for reading
			for line in hfile.read().splitlines():				#Iterate through each line
				self.hashes[line] = True;						#Add the line to the dictionary
			#/for
			hfile.close();										#Close the file
		#/if
		self.file = open(fpath, "a");							#Open the file in append mode
		self.fpath = fpath;										#Store the file path
	#/init
	
	def reset(self):
		self.file.close();										#Close the existing file
		self.file = open(self.fpath, "w");						#Re-open file in write mode, which overwrites the existing file
	#/reset
	
	def add(self, fhash):
		if (fhash not in self.hashes):							#Verify the hash isn't already in the dictionary
			self.hashes[fhash] = True;							#Add it to the dictionary
			self.file.write(fhash + "\n");						#Append it to the save file
		#/if
	#/add
	
	def contains(self, fhash):
		return (fhash in self.hashes);							#Return true if the hash is in the dictionary, false otherwise
	#/contains
	
	def getHashes(self):
		return self.hashes;										#Return the full dictionary of hashes
	#/getHashes
	
	def count(self):
		return len(self.hashes);								#Return the count of hashes in the dictionary
	#/count
	
	def close(self):
		self.file.close();										#Close the save file
	#/close
#/HashList

class ErrorLog():
	def __init__(self, path):
		self.logfile = open(path, "a");
		self.tfmt = "%Y-%m-%d_%H:%M:%S";
		self.lfmt = "[{}] {}\n";
	#/init
	def record(self, err):
		ts = time.strftime(self.tfmt, time.localtime());
		self.logfile.write(self.lfmt.format(ts, err));
	#/record
	def close(self):
		self.logfile.close();
	#/close
#/ErrorLog

if __name__ == "__main__":
	main(sys.argv);
#/__main__
