#!/usr/bin/python3

'''
Author: Douglas Skrypa
Date: 2016.01.03
Version: 1
'''

import os, shutil, sys, time, re;

def getPaths(path):
	'''
	Recursively generates a list of absolute paths for every file discoverable
	via the given path.
	'''
	path = path[:-1] if (path[-1:] == "/") else path;							#Strip trailing slash if it exists
	paths = [];																	#Initialize list to store paths in
	if os.path.isdir(path):														#If the given path is a directory
		for sub in os.listdir(path):											#Iterate through each sub-path in it
			paths += getPaths(path + "/" + sub);								#Add the list of paths discoverable there
	elif os.path.isfile(path):													#Otherwise, if it is a file
		paths += [path];														#Add the path to the list
	return paths;																#Return the list
#/getPaths

def getFilteredPaths(path, ext, sort=True):
	paths = getPaths(path);														#Get the paths
	fileFilter = re.compile(r'.*\.' + ext, re.IGNORECASE);						#Define the filter
	filtered = [fname for fname in paths if fileFilter.match(fname)];			#Apply the filter
	return sorted(filtered) if sort else filtered;								#Return the filtered list (sorted if sort == True)
#/getFilteredPaths

def fTime(seconds):
	return time.strftime("%H:%M:%S",time.gmtime(seconds));						#Return a string representation of the given number of seconds as HH:MM:SS
#/fTime

class PerfTimer():
	'''Simple performance monitor including a timer and counters'''
	def __init__(self):
		self.start = time.perf_counter();										#Initialize the timer with the current time
	#/init

	def elapsed(self):
		return time.perf_counter() - self.start;								#Return the time delta in seconds since initialization
	#/elapsed
	
	def elapsedf(self):
		return time.strftime("%H:%M:%S",time.gmtime(self.elapsed()));			#Return the time delta as a string in the form HH:MM:SS
	#/elapsedf
#/PerfTimer

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
	def show(cls, msg=""):
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
	def println(cls, msg=""):
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
	'''Simple error log that includes a date+time stamp for each line'''
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
