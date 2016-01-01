#!/usr/bin/python3

'''
Author: Douglas Skrypa
Date: 2015.01.01
Version: 7
'''

import os, sys, shutil, time, hashlib;
from pydub import AudioSegment;
from enum import Enum;

def main(args):
	#Real paths
	sdir = "/media/user/WD_1TB_External_Backup/unduped_full_hash/";
	ddir = "/media/user/My Passport/unduped_audio_hash/";
	lpath = "/home/user/temp/dedupe.log";
	save_dir = "/home/user/temp/";

	#Test paths
	tsdir = "/home/user/temp/src/";
	tddir = "/home/user/temp/dest/";
	tlpath = "/home/user/temp/test_dedupe.log";
	tsave_dir = "/home/user/temp/test_";
	
	#Parse args
	parsed = parseArgs(args);
	comp_mode = parsed["cmode"] if ("cmode" in parsed) else None;				#Compare mode to use
	test_mode = parsed["rmode"] if ("rmode" in parsed) else True;				#Run mode; defaults to test
	skip = parsed["skip"] if ("skip" in parsed) else 0;							#Number of files to skip; defaults to 0
	
	if (comp_mode == None):														#If the compare mode was not provided
		helpAndExit("Compare mode is a required parameter!");					#Exit

	if test_mode:																#If testing
		clio.println("TEST MODE");
		deduper1 = DeDuper(tsdir, tddir, tlpath, tsave_dir);					#Then construct with test paths
	else:																		#Otherwise
		deduper1 = DeDuper(sdir, ddir, lpath, save_dir);						#Construct with real paths
	#/if
	deduper1.dedupe(comp_mode, skip);											#Run the DeDuper
#/main

def parseArgs(args):
	aliases = {'audio':'a', 'full':'f', 'test':'t', 'real':'r', 'skip':'s'};	#Aliases for flags
	flags = {
		'a': ('cmode', Modes.audio),	'f': ('cmode', Modes.full),
		't': ('rmode', True),			'r': ('rmode', False),
		's': ('ext', 'skip')
	};
	pargs = {};																	#Parsed arg dictionary
	last = None;																#Has value if previous flag expects a value

	for x in range(1, len(args)):												#Iterate through args
		arg = args[x].lower();													#Convert to lower case for ease of processing
		if (arg[0] == "-"):														#If the arg starts with a hyphen
			if (last != None):													#If an extended arg's value was expected
				helpAndExit("[Error] Expected value for " + last);
			arg = arg[1:];														#Ignore preceding hyphen
			if (arg in aliases): arg = aliases[arg];							#All valid long arg names should have a single letter alias
			
			ac = len(arg);														#Compressed arg count
			for y in range(0, ac):												#Iterate through given compressed args
				a = arg[y];														#Current compressed arg
				if (a in flags):												#If the current compressed arg is valid
					ft = flags[a][0];											#Get the flag type
					fv = flags[a][1];											#Get the flag value
					if (ft == "ext"):											#If it is an extended flag
						if ((y == 0) and (ac == 1)):							#And it's the 1st and only arg in the set
							last = fv;											#Store the vale as last
						else:													#Otherwise exit
							helpAndExit("Invalid placement of arg with expected value: " + arg);
					else:														#If it's a normal flag
						pargs[ft] = fv;											#Store the type:val in the dictionary
				else:															#Otherwise exit because the arg was invalid
					helpAndExit("Invalid arg: " + a);
			#/for y
		else:																	#Arg did not start with a hyphen
			conv_int = ["skip"];												#Args that should be converted to integers
			if (last == None):													#If an extended arg's value was not expected
				helpAndExit("Invalid arg: " + arg);								#Exit
			elif (last in conv_int):											#If the arg should be converted to an integer
				try:
					pargs[last] = int(arg);
				except:
					helpAndExit("Invalid val for {}: {}".format(last, arg));
			else:
				pargs[last] = arg;
			last = None;
	#/for x
	return pargs;																#Return the dictionary
#/parseArgs

def helpAndExit(msg=None):
	if (msg != None):
		clio.println(msg);
	fmta = "\t{}\n";
	fmtb = "\t\t{:10}\t\t{}\n";
	htxt = "Valid parameters:\n";
	htxt += fmta.format("Compare Modes: (required)");
	htxt += fmtb.format("-a, -audio", "Compare files based on a hash of the audio content (slower)");
	htxt += fmtb.format("-f, -full", "Compare files based on a hash of the entire file (faster)");
	htxt += fmta.format("Run Modes: (default: test)");
	htxt += fmtb.format("-t, -test", "Use test files / paths");
	htxt += fmtb.format("-r, -real", "Use real files / paths");
	htxt += fmta.format("Other");
	htxt += fmtb.format("-s, -skip [n]", "Skip the first [n] files when scanning the source dir (default 0)");
	clio.println(htxt);
	sys.exit(0);
#/helpAndExit

class clio():
	'''Command Line Interface Output'''
	@classmethod
	def _fmt(cls, msg):
		'''Format the given message for overwriting'''
		tcols = shutil.get_terminal_size()[0];									#Number of text character columns available in the terminal window
		blanks = "";
		smsg = str(msg);														#Make sure the input is a string
		fc = tcols - len(smsg);													#Determine the number of columns need to be filled after the given message
		if (fc > 0):
			blanks = " " * fc;
		#/if
		return "\r" + smsg + blanks;
	#/fmt
	@classmethod
	def show(cls, msg):
		'''Display overwritable message'''
		sys.stdout.write(cls._fmt(msg));
		sys.stdout.flush();
	#/show
	@classmethod
	def showf(cls, fmt, *args):
		'''Display formatted overwritable message'''
		msg = fmt.format(*args);
		cls.show(msg);
	#/showf
	@classmethod
	def println(cls, msg):
		'''Display message on a new line'''
		sys.stdout.write(cls._fmt(msg) + "\n");
		sys.stdout.flush();
	#/println
	@classmethod
	def printf(cls, fmt, *args):
		'''Display formatted message on a new line'''
		msg = fmt.format(*args);
		cls.println(msg);
	#/printf
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

def fTime(seconds):
	return time.strftime("%H:%M:%S",time.gmtime(seconds));
#/fTime

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
	
	def dedupe(self, mode, skip=0):
		self.mode = mode;
		self.processDirectory(skip);
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
			except:
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
		tl = str(len(str(t)));													#Length of that number as a string
		
		if (hashes.count() == t):												#If the destination dir contains as many files as there were hashes saved
			self.log2("Saved list appears to match destination directory!");
			return hashes;														#Return that list
		else:
			self.log2("Saved list did not appear to match destination directory.");
			hashes.reset();														#Otherwise, reset the saved list and rebuild it
		#/if
		
		self.log2("Scanning destination directory for existing files...");
		
		spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}]";					#Show progress report format
		spfmt += "[Rate: {:7,.2f} files/sec] Current file: {}";
		stime = time.perf_counter();											#Start time
		ltime = stime;															#Last time progress was reported
		c = 0;																	#Counter
		
		for fname in fnames:													#Iterate through each file name in the destination dir
			c += 1;																#Increment the counter
			ctime = time.perf_counter();										#Current time
			dt = ctime - stime;													#Time delta since start
			
			rpath = fname;														#Relative path [future]
			fpath = self.ddir + rpath;											#Rebuild the absolute path for the file
			
			if ((ctime - ltime) > 1):											#If it's been over 1 second since last progress report
				ltime = ctime;													#Set last time to current time
				clio.showf(spfmt, c/t, c, fTime(dt), c/dt, rpath);				#Show current progress report
				
				#clio.show(spfmt.format(c/t, c, fTime(dt), c/dt, fname));		#Show current progress report
				
			#/if
			
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
		clio.println("Runtime: " + fTime(rtime));
		
		return hashes;
	#/getExistingHashes
	
	def processDirectory(self, skip):
		ifmt = "Determining file uniqueness via {} content hash...";			#Intro format string
		self.log2(ifmt.format(self.mode.name));									#Display intro
		
		hashes = self.getExistingHashes();										#Get the Dictionary of hashes found
		
		self.log2("Processing source directory and copying unique files...");
		if (skip > 0):
			self.log2("Skipping the first {:,d} files without scanning them!".format(skip));
		else:
			skip = 0;
		#/if
		
		fnames = os.listdir(self.sdir);											#Array of file names (relative path)
		t = len(fnames);														#Total number of files to process
		t -= skip;																#Ignore the files being skipped for purposes of the total count
		tl = str(len(str(t)));													#Length of that number as a string
		pfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"] {} {} {}";						#Format string for progress reports
		spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}][Copied: {:8,d}]";	#Show progress report format
		spfmt += "[Skipped: {:8,d}][Errors: {:8,d}][Rate: {:,.2f} files/sec]";
		copied = 0;																#Counter for copied files
		skipped = 0;															#Counter for skipped files
		errors = 0;																#Counter for errors
		c = 0;																	#Counter for total files processed
		k = 0;																	#Counter for files skipped without scanning
		
		stime = time.perf_counter();											#Start time
		ltime = stime;															#Last time progress was reported
		
		for fname in fnames:													#Iterate through each file name
			if (k < skip):														#If the skip counter hasn't reached the file to skip to yet
				k += 1;															#Increment the skip counter
				continue;														#Skip to the next iteration of the for loop
			#/if
			c += 1;																#Increment the counter
			ctime = time.perf_counter();										#Current time
			dt = ctime - stime;													#Time delta since start
			clio.showf(spfmt, c/t, c, fTime(dt), copied, skipped, errors, c/dt);#Show current progress report
			
			#clio.show(spfmt.format(c/t, c, fTime(dt), copied, skipped, errors, c/dt));#Show current progress report

			rpath = fname;														#Relative path [future]
			fpath = self.sdir + rpath;											#Rebuild the absolute path for the file
			try:
				fhash = self.getHash(fpath);									#Get the hash for the given mode
				if (not hashes.contains(fhash)):								#If the destination doesn't already have a file with that hash
					copied += 1;												#Increment the copied counter
					hashes.add(fhash);											#Add the hash to the HashList
					shutil.copy(fpath, self.ddir);								#Copy the file to the destination
					self.dbg(pfmt.format(c/t, c, "Copying  ", fhash, rpath));
				else:															#If the hash was already moved to the destination
					skipped += 1;												#Increment the skipped counter
					self.dbg(pfmt.format(c/t, c, "Skipping ", fhash, rpath));
			except HashException as e:											#Log any errors
				errors += 1;
				self.log2("[ERROR] " + e.value);
			except Exception as ue:
				errors += 1;
				self.log2("[ERROR] Unexpected {} on file: {}".format(type(ue).__name__, fpath));
				clio.println(ue.args)
		#/for
		
		fmta = "Processed: {:d}";
		fmtb = "{}   {:" + tl + "d} ({:.2%})"
		clio.println("Done!");
		
		clio.printf(fmta, t);
		clio.printf(fmtb, "Copied: ", copied, copied/t);
		clio.printf(fmtb, "Skipped:", skipped, skipped/t);
		clio.printf(fmtb, "Errors: ", errors, errors/t);

		etime = time.perf_counter();
		rtime = etime-stime;
		clio.println("Runtime: " + fTime(rtime));
	#/processDirectory
	
	def dbg(self, msg):
		if self.debugMode:
			clio.println(msg);
	#/dbg
	
	def log2(self, msg):
		clio.println(msg);
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
			self.file.flush();									#Make sure the line is written to disk
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
