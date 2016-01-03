#!/usr/bin/python3

'''
Author: Douglas Skrypa
Date: 2016.01.01
Version: 1
'''

import os, sys, shutil, time, hashlib, re, glob;
import subprocess as sproc;

def main(args):
	sdir = "/home/user/temp/src2/";
	lpath = "/home/user/temp/organizer.log";
	
	org = Organizer(lpath);
	info = org.collectInfo(sdir);
	
	for fname in info:
		clio.printf("{}:\n{}", fname, info[fname]);
	#/for
	
	
#/main

def fTime(seconds):
	return time.strftime("%H:%M:%S",time.gmtime(seconds));
#/fTime

class Organizer():
	def __init__(self, lpath):
		self.errlog = ErrorLog(lpath);
		self.log = self.errlog.record;
	#/init
	
	def collectInfo(self, sdir):
		cmd = ["kid3-cli", "", "-c", "get"];									#List with the command and its args
		
		fnames = os.listdir(sdir);												#Get list of files in the given dir
		ff = re.compile(".*\.mp3", re.IGNORECASE);								#Regex to filter file list to only mp3 files
		filtered = [fname for fname in fnames if ff.match(fname)];				#Apply the filter
		fnames = sorted(filtered);												#Sort the file list alphabetically
		
		t = len(fnames);														#Total number of files to process
		tl = str(len(str(t)));													#Length of that number as a string
		spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}][Success: ";		#Show progress report format
		spfmt += "{:"+tl+",d}][Error: {:"+tl+",d}][Rate: {:,.2f} files/sec] Current file: {}";
		success = 0;															#Counter for successful files
		errors = 0;																#Counter for errors
		c = 0;																	#Counter for total files processed
		
		stime = time.perf_counter();											#Start time
		
		tagInfo = {};															#Initialize dictionary to store info
		for fname in fnames:													#Iterate through each file name
			c += 1;																#Increment the counter
			ctime = time.perf_counter();										#Current time
			dt = ctime - stime;													#Time delta since start
			clio.showf(spfmt, c/t, c, fTime(dt), success, errors, c/dt, fname);	#Show current progress report
			
			fpath = sdir + fname;												#Rebuild the absolute path
			cmd[1] = fpath;														#Set the first arg to bo the file's path
			#cmd = cmdfmt.format(fpath);											#Insert the file path in to the command
			sp = sproc.Popen(cmd, stdout=sproc.PIPE, stderr=sproc.PIPE);		#Call the subprocess
			sp_out, sp_err = sp.communicate();									#Retrieve the output
		
			if (sp.returncode != 0):											#If it did not run successfully
				errors += 1;
				self.log2("Unable to process file: " + fpath);					#Log the file's name
			else:
				success += 1;
				tagInfo[fpath] = sp_out;										#Save the output, using the file path as the key
			#/if
		#/for
		
		etime = time.perf_counter();
		rtime = etime-stime;
		clio.println("Runtime: " + fTime(rtime));
		
		return tagInfo;															#Return the dictionary
	#/collectInfo

	def log2(self, msg):
		clio.println(msg);
		self.log(msg);
	#/log2
#/Organizer

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

class ErrorLog():
	def __init__(self, path):
		self.logfile = open(path, "a");
		self.tfmt = "%Y-%m-%d_%H:%M:%S";
		self.lfmt = "[{}] {}\n";
	#/init
	def record(self, err):
		ts = time.strftime(self.tfmt, time.localtime());
		self.logfile.write(self.lfmt.format(ts, err));
		self.logfile.flush();
	#/record
	def close(self):
		self.logfile.close();
	#/close
#/ErrorLog

if __name__ == "__main__":
	main(sys.argv);
#/__main__
