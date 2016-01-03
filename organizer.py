#!/usr/bin/python3

'''
Author: Douglas Skrypa
Date: 2016.01.02
Version: 1.2
'''

import os, sys, shutil, time, hashlib, re, glob;
import subprocess as sproc;

def main(args):
	sdir = "/home/user/temp/src2/";
	lpath = "/home/user/temp/organizer.log";
	
	org = Organizer(lpath);
	info = org.collectInfo(sdir, 2);
	songs = org.parse(info);
	
	fmt = "[Artist: {}][Album: {}][Title: {}]";
	fmt2 = "{}:\n[Artist: {}] -> [Artist: {}]\n[Album: {}] -> [Album: {}]\n[Title: {}] -> [Title: {}]\n";
	
	for spath in songs:
		song = songs[spath];
		artist = song.getStr("Artist");
		album = song.getStr("Album");
		name = song.getStr("Title");
		
		cartist = cleanup(artist);
		calbum = cleanup(album);
		cname = cleanup(name);
		
		#clio.printf(fmt, artist, album, name);
		
		clio.printf(fmt2, spath, artist, cartist, album, calbum, name, cname);
		
	#/for
	
#/main

def cleanup(original):
	bad = r'[?+*=%#&@$!:|`~"<>/\\\']';
	return re.sub(bad, "", original);
#/cleanup

def fTime(seconds):
	return time.strftime("%H:%M:%S",time.gmtime(seconds));
#/fTime


class Song():
	def __init__(self, path):
		self.path = path;														#Save the location of this song
		self.attrs1 = {};														#Initialize a dictionary to store ID3v1 attributes
		self.attrs2 = {};														#Initialize a dictionary to store ID3v2 attributes
	#/init
	
	def setx(self, ver, key, val):
		'''Set the value of the key for the given tag version'''
		if (ver == 1):
			self.set1(key, val);
		elif (ver == 2):
			self.set2(key, val);
	#/setx
	
	def set1(self, key, val):
		'''Set the value of an ID3v1 tag'''
		self.attrs1[key] = val;
	#/set1
	
	def set2(self, key, val):
		'''Set the value of an ID3v2 tag'''
		self.attrs2[key] = val;
	#/set1
	
	def get(self, attr):
		'''Returns the value for the given attribute, if it exists. Favors ID3v2 over v1'''
		if (attr in self.attrs2):
			return self.attrs2[attr];
		if (attr in self.attrs1):
			return self.attrs1[attr];
		return None;
	#/get
	
	def getStr(self, attr):
		val = self.get(attr);
		return "[Unknown]" if (val == None) else val;
	#/getStr
#/song

class Organizer():
	def __init__(self, lpath):
		self.errlog = ErrorLog(lpath);
		self.log = self.errlog.record;
	#/init
	
	def parse(self, info):
		t1 = re.compile(r'^Tag 1:.*');											#Regex for ID3v1 lines
		t2 = re.compile(r'^Tag 2:.*');											#Regex for ID3v2 lines
		kv = re.compile(r'^\s\s(.*?)\s\s(.*)$');								#Regex for key:value lines
		
		songs = {};																#Initialize a dictionary to store songs
		
		for path in info:														#Iterate through the dictionary of info
			song = Song(path);													#Create a new Song object for the song
			ctag = 0;															#Current tag version info is being read from
			
			for line in info[path].splitlines():								#Iterate through each line in the stored output
				if (t1.match(line)):											#If it's the start of an ID3v1 section
					ctag = 1;													#Set the current tag version to 1
				elif (t2.match(line)):											#If it's the start of an ID3v2 section
					ctag = 2;													#Set the current tag version to 2
				else:
					if (ctag in [1,2]):											#If the tag version is set
						m = kv.match(line);										#Test the line with the key:value pair regex
						if (m):													#If the line matches
							key = m.group(1).strip();							#Strip leading/trailing spaces on the key
							val = m.group(2).strip();							#Strip leading/trailing spaces on the value
							song.setx(ctag, key, val);							#Store the extracted key:value pair
			#/for line
			songs[path] = song;													#Store the Song in the dictionary
		#/for path
		return songs;															#Return the dictionary of songs
	#/parser
	
	def collectInfo(self, sdir, fmax=0):
		cmd = ["kid3-cli", "", "-c", "get"];									#List with the command and its args
		
		fnames = os.listdir(sdir);												#Get list of files in the given dir
		ff = re.compile(r'.*\.mp3', re.IGNORECASE);								#Regex to filter file list to only mp3 files
		filtered = [fname for fname in fnames if ff.match(fname)];				#Apply the filter
		fnames = sorted(filtered);												#Sort the file list alphabetically
		
		t = len(fnames);														#Total number of files to process
		t = fmax if ((fmax > 0) and (t > fmax)) else t;							#If the total file count is > the given max, cap it
		tl = str(len(str(t)));													#Length of that number as a string
		spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}][Success: ";		#Show progress report format
		spfmt += "{:"+tl+",d}][Error: {:"+tl+",d}][Rate: {:,.2f} files/sec] Current file: {}";
		success = 0;															#Counter for successful files
		errors = 0;																#Counter for errors
		c = 0;																	#Counter for total files processed
		
		stime = time.perf_counter();											#Start time
		
		tagInfo = {};															#Initialize dictionary to store info
		for fname in fnames:													#Iterate through each file name
			if ((fmax > 0) and (c >= fmax)):									#If a maximum file count was set, and that many files have been processed, stop
				break;
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
				tagInfo[fpath] = sp_out.decode();								#Save the output, using the file path as the key
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
