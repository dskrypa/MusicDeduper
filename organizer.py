#!/usr/bin/python3

'''
Author: Douglas Skrypa
Date: 2016.01.09
Version: 2
'''

import os, sys, shutil, time, hashlib, re, glob;
import subprocess as sproc;
from common import *;

def main(args):
	sdir = "/media/user/IntelSSD/unduped_audio_hash/";
	ddir = "/media/user/IntelSSD/organized/";
	lpath = "/home/user/temp/organizer.log";
	alpath = "/home/user/temp/ActionLog.log";
	
	#sdir = "/home/user/temp/src/";
	#ddir = "/home/user/temp/dest/";
	#lpath = "/home/user/temp/organizer.log";
	
	mc = MusicCollection(ddir, lpath, alpath);
	mc.addSongs(sdir, False, False);
	#mc.executeMoves();
#/main

class MusicCollection():
	def __init__(self, ddir, lpath, alpath):
		self.errlog = ErrorLog(lpath);											#Initialize an ErrorLog at the given path
		self.log = self.errlog.record;											#Create a shortcut for convenience 
		self.dir = ddir[:-1] if (ddir[-1:] == "/") else ddir;					#Save the given directory path
		self.col = {};															#Initialize the collection dictionary
		self.alog = ActionLog(alpath);
		
		self.allSongs = [];
		
		self.initializing = True;
		self.pparser = re.compile(r'^/([^/]+)/([^/]+)/(.*).mp3$', re.IGNORECASE);
		self.feat = re.compile(r'(.+?)\s+feat.+', re.IGNORECASE);
		self.compilations = {"Billboard":"Billboard", "Now Thats What I Call Music":"NowCompilations"};
		self.addSongs(self.dir, False, False);									#Scan the destination directory, take no action on the files found
		self.initializing = False;
	#/init
	
	def addSongs(self, sdir, movable=False, action=False, fmax=0):
		self.log2("Scanning for music: " + sdir);
		blen = len(sdir[:-1] if (sdir[-1:] == "/") else sdir);					#Length of the base dir's path
		paths = getFilteredPaths(sdir, "mp3");									#Get the filtered, sorted list of paths
		
		t = len(paths);															#Total number of files to process
		t = fmax if ((fmax > 0) and (t > fmax)) else t;							#If the total file count is > the given max, cap it
		tl = str(len(str(t)));													#Length of that number as a string
		spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}]";
		if action:
			spfmt += "[Success: {:"+tl+",d}][Error: {:"+tl+",d}]";	
		spfmt += "[Rate: {:,.2f} files/sec][Remaining: ~{}] Current file: {}";
		success = 0;															#Counter for successful files
		errors = 0;																#Counter for errors
		c = 0;																	#Counter for total files processed
		
		pt = PerfTimer();														#Initialize new performance timer
		for path in paths:														#Iterate through each of the paths
			if ((fmax > 0) and (c >= fmax)):									#If a maximum file count was set, and that many files have been processed, stop
				break;
			c += 1;																#Increment the counter
			rpath = path[blen:];												#Current path relative to the given base directory
			
			dt = pt.elapsed();													#Get the time delta
			rate = c/dt;
			remaining = fTime((t-c) / rate);
			
			if action:
				clio.showf(spfmt, c/t, c, fTime(dt), success, errors, rate, remaining, ".."+rpath);
			else:
				clio.showf(spfmt, c/t, c, fTime(dt), rate, remaining, ".."+rpath);
			
			song = Song(path, movable);											#Initialize a new Song object
			if self.initializing:
				self.addSimple(rpath, song);
			else:
				song.bootstrap();												#Have the song gather it's own info
				if self.addSong(song, action):									#Add the Song to this collection
					success += 1;
				elif action:													#If adding wasn't successful and action is supposed to be taken, increment counter
					errors += 1;
		#/for path
		
		self.log2("Scan complete for directory: " + sdir);
		fmtb = "{}   {:" + tl + "d} ({:.2%})"
		clio.printf("Processed: {:d}", t);
		if not self.initializing:
			clio.printf(fmtb, "Renamed: ", success, success/t);
			clio.printf(fmtb, "Errors: ", errors, errors/t);
			
		clio.printf("Runtime: {}\t({:,.2f} files/sec)", pt.elapsedf(), c/pt.elapsed());
	#/addSongs
	
	def addSimple(self, relPath, song):
		m = self.pparser.match(relPath);
		if (m):
			artist = m.group(1);
			album = m.group(2);
			filename = m.group(3);
			
			if not (artist in self.col):											#If the artist did not already exist in this collection
				self.col[artist] = {};												#Add a dictionary for it
			if not (album in self.col[artist]):										#If the album did not already exist for this artist
				self.col[artist][album] = {};										#Add a dictionary for it
		
			self.col[artist][album][filename] = song;								#Store a pointer to the Song here
			self.allSongs.append(song);
		else:
			clio.println("ERROR");
			sys.exit(1);
	#/addSimple
	
	def addSong(self, song, action=False):
		tnum = song.get("Track Number");										#Get the given song's track number
		if (tnum == None):														#If the track number is unavailable
			tnum = "XX";														#Use "XX" instead
		else:
			if not tnum.isdigit():												#If tnum is not numeric
				m = re.compile(r'(\d{1,})/\d{1,}').match(tnum);					#See if it's in a form like 01/12
				if (m):															#If it is
					tnum = m.group(1);											#Take the portion before the slash
				else:
					tnum = "XX";												#Otherwise ignore it
		if (len(tnum) < 2):														#If it is a single digit
			tnum = "0" + tnum;													#Prepend it with a 0
		
		artist = song.getClean("Artist");										#Get the given song's artist
		album = song.getClean("Album");											#Get the given song's album
		title = song.getClean("Title");											#Get the given song's title
		fname = "{} - {}".format(tnum, title);									#Set the file name to be TrackNumber - TrackName
		
		isCompilation = False;
		for cname in self.compilations:											#Iterate through the possible compilation prefixes
			if (album.lower().startswith(cname.lower())):						#If the album name indicates that this is a compilation
				artist = self.compilations[cname];								#Use the given name instead of the artist's name
				isCompilation = True;											#Note that the artist was set here
				break;															#If it was a compilation, it won't be another as well
		#/check common compilation prefixes
		
		usingAlbumArtist = False;
		if (not isCompilation):
			aartist = song.getClean("Album Artist");
			if (aartist != "Unknown"):											#If Album Artist is set
				if (aartist.lower().startswith("various")):						#If it starts with "Various"
					artist = "Various Artists";									#Normalize it to put them all in one folder
					usingAlbumArtist = True;
				elif (aartist != artist):										#If the Album Artist is different than the Artist
					artist = aartist;											#Use the Album Artist
					usingAlbumArtist = True;
		#/if not a compilation
		
		featOther = False;
		if ((not isCompilation) and (not usingAlbumArtist)):
			featMatcher = self.feat.match(artist);
			if (featMatcher):
				artist = featMatcher.group(1);
				featOther = True;
		#/featuring check
		
		unknownTitle = False;
		#if ("Unknown" in (artist, album, title)):								#If any field is unknown
			#artist = "Unknown";													#Treat artist as unknown
			#album = "Unknown";													#And album as unknown
		if (title == "Unknown"):
			fname = song.getFileName()[:-4];									#And set the file name to be the same as before (ignore extension for now)
			unknownTitle = True;
		if not (artist in self.col):											#If the artist did not already exist in this collection
			self.col[artist] = {};												#Add a dictionary for it
		if not (album in self.col[artist]):										#If the album did not already exist for this artist
			self.col[artist][album] = {};										#Add a dictionary for it
		
		filename = fname;														#Different filename var to facilitate uniqueness test
		c = 0;																	#Counter for uniqueness test
		while (filename in self.col[artist][album]):							#Loop while the file name isn't unique in this dir
			c += 1;																#Increment the counter
			filename = fname + str(c);											#Append the counter to the original (new) file name
		
		self.col[artist][album][filename] = song;								#Store a pointer to the Song here
		self.allSongs.append(song);
		
		dfmt = "{}/{}/{}/";														#Format string for the file's new directory
		dfmt2 = "{}/{}/{}/{}.mp3";
		newPath = dfmt.format(self.dir, artist, album, filename);
		self.alog.write(song.getPath(), newPath);
		
		song.setNewPath(dfmt.format(self.dir, artist, album), filename+".mp3");	#Save the new dir and name in the Song object
		song.setFlags(isCompilation, usingAlbumArtist, featOther, unknownTitle);
		
		if action:																#If action should be taken,
			return self.tryMove(song);
	#/addSong
	
	def executeMoves(self):
		self.log2("Executing moves now...");
		t = len(self.allSongs);													#Total number of files to process
		tl = str(len(str(t)));													#Length of that number as a string
		spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}][Success: ";		#Show progress report format
		spfmt += "{:"+tl+",d}][Error: {:"+tl+",d}][Rate: {:,.2f} files/sec]";
		success = 0;															#Counter for successful files
		errors = 0;																#Counter for errors
		c = 0;																	#Counter for total files processed
		
		pt = PerfTimer();														#Initialize new performance timer
		for song in self.allSongs:												#Iterate through each pre-processed song
			c += 1;																#Increment the counter
			dt = pt.elapsed();													#Get the time delta
			clio.showf(spfmt, c/t, c, fTime(dt), success, errors, c/dt);		#Show current progress report
			if song.isMovable():
				if self.tryMove(song):
					success += 1;
				else:
					errors += 1;
		#/for song
		
		self.log2("Moves complete!");
		fmtb = "{}   {:" + tl + "d} ({:.2%})"
		clio.printf(fmtb, "Renamed: ", success, success/t);
		clio.printf(fmtb, "Errors: ", errors, errors/t);
		clio.printf("Runtime: {}\t({:,.2f} files/sec)", pt.elapsedf(), c/pt.elapsed());
	#/executeMoves
	
	def tryMove(self, song):
		try:
			song.move();														#Move the file
			return True;
		except:
			self.log2("[ERROR] Unable to move file: " + song.getPath());
			return False;
	#/tryMove
	
	def log2(self, msg):
		clio.println(msg);
		self.log(msg);
	#/log2
#/MusicCollection

class SongException(Exception):
	def __init__(self, value):
		self.value = value;
	def __str__(self):
		return repr(self.value);
#/SongException

class Song():
	t1 = re.compile(r'^Tag 1:.*');												#Regex for ID3v1 lines
	t2 = re.compile(r'^Tag 2:.*');												#Regex for ID3v2 lines
	kv = re.compile(r'^\s\s(.*?)\s\s(.*)$');									#Regex for key:value lines
	
	flagStrs = {"isCompilation": "[COMP]", "usingAlbumArtist": "[AART]", "featOther": "[FEAT]", "unknownTitle": "[UNKT]"};
	
	def __init__(self, path, movable=False):
		self.path = path;														#Save the location of this song
		self.attrs1 = {};														#Initialize a dictionary to store ID3v1 attributes
		self.attrs2 = {};														#Initialize a dictionary to store ID3v2 attributes
		self.movable = movable;													#Whether or not this Song should be moved
		self.newDir = None;														#New directory to be placed in
		self.newName = None;													#New file name to use
		self.flags = {};
	#/init

	def setFlags(self, isCompilation, usingAlbumArtist, featOther, unknownTitle):
		self.flags = {
			"isCompilation":isCompilation,	"usingAlbumArtist":usingAlbumArtist,
			"featOther":featOther,			"unknownTitle":unknownTitle
		};
	#/setFlags
	
	def getFlags(self):
		flagstr = "";
		for flag in self.flags:
			if self.flags[flag]:
				flagstr += Song.flagStrs[flag];
		return flagstr;
	#/getFlags

	def isMovable(self):
		return self.movable;
	#/isMovable

	def bootstrap(self):
		cmd = ["kid3-cli", self.path, "-c", "get"];
		sp = sproc.Popen(cmd, stdout=sproc.PIPE, stderr=sproc.PIPE);			#Call the subprocess
		sp_out, sp_err = sp.communicate();										#Retrieve the output
		if (sp.returncode != 0):												#If it did not run successfully
			raise SongException("Unable to process file: " + self.path);		#Raise a SongException
		#/if
		tagInfo = sp_out.decode();												#Save the output, using the file path as the key
		self.parseOwnInfo(tagInfo);
	#/bootstrap
	
	def parseOwnInfo(self, info):
		ctag = 0;																#Current tag version info is being read from
		for line in info.splitlines():
			if (Song.t1.match(line)):											#If it's the start of an ID3v1 section
				ctag = 1;														#Set the current tag version to 1
			elif (Song.t2.match(line)):											#If it's the start of an ID3v2 section
				ctag = 2;														#Set the current tag version to 2
			else:
				if (ctag in [1,2]):												#If the tag version is set
					m = Song.kv.match(line);									#Test the line with the key:value pair regex
					if (m):														#If the line matches
						key = m.group(1).strip();								#Strip leading/trailing spaces on the key
						val = m.group(2).strip();								#Strip leading/trailing spaces on the value
						self.setx(ctag, key, val);								#Store the extracted key:value pair
		#/for line
	#/parseOwnInfo
	
	def setNewPath(self, newDir, newName):
		self.newDir = newDir;
		self.newName = newName;
	#/setNewPath
	
	def getNewLoc(self):
		return (self.newDir, self.newName);
	#/getNewLoc
	
	def getPath(self):
		return self.path;
	#/getPath
	
	def getFileName(self):
		return os.path.basename(self.path);
	#/getFileName
	
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
		return "Unknown" if (val == None) else val;
	#/getStr
	
	def getClean(self, attr):
		val = self.getStr(attr);
		bad = r'[?+*=%#&@$!;:|`~"<>/\\\']';
		val = re.sub(bad, "", val).strip();
		if (len(val) == 1):
			aval = val.encode("ascii", "ignore").decode();
			val = "" if (aval == "") else val;
		return "Unknown" if (val == "") else val;
	#/getClean
	
	def move(self):
		'''Display old and new paths, if not in testing mode, move the file'''
		newpath = self.newDir + self.newName;
		clio.printf("{} -> {}", self.path, newpath);
		
		if not self.movable:
			return;
				
		if not os.path.isdir(self.newDir):
			os.makedirs(self.newDir);
		
		if os.path.exists(newpath):
			raise SongException("Unable to move; file exists: " + newpath);
		else:
			os.rename(self.path, newpath);	
	#/moveSong
#/song

class ActionLog():
	headers = ["Original","Destination"];
	fmt = "{}\t{}\n";
	def __init__(self, path):
		psplit = os.path.splitext(path);
		pathA = psplit[0];
		ext = psplit[1];
		c = 0;
		while (os.path.isfile(pathA + ext)):
			pathA = psplit[0] + str(c);
			c += 1;
		#/while
		self.path = pathA + ext;
		self.file = open(self.path, "w");
		self.paths = {};
	#/init
	
	def act(self):
		for path in self.paths:
			oldPath = path;
			newPath = self.paths[path];
			print("{} -> {}".format(oldPath, newPath));
			os.renames(oldPath, newPath);
	#/act
	
	def write(self, *args):
		self.paths[args[0]] = args[1];
		self.file.write(self.fmt.format(*args));
		self.file.flush();
	#/write
	
	def close(self):
		self.file.close();
	#/close
#/ActionLog

if __name__ == "__main__":
	main(sys.argv);
#/__main__
