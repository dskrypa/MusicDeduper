#!/usr/bin/python

'''
Author: Douglas Skrypa
Date: 2016.01.24
Version: 0.1
'''

from __future__ import division;
from argparse import ArgumentParser;
from common import *;
from _constants import *;
import re;
import hashlib;
import tempfile;
import eyeD3b as eyeD3;															#A version of eyeD3 with a kludge added by me to make it support using a SpooledTemporaryFile

def main():
	parser = ArgumentParser(description="Music info printer");
	parser.add_argument("--path", "-p", help="The directory to scan for music", required=True);
	args = parser.parse_args();
	
	paths = getFilteredPaths(args.path, "mp3");

	for path in paths:
		tag = eyeD3.Tag();
		clio.println();
		clio.println(path);
		
		rfile = open(path, "rb");
		
		mfile = tempfile.SpooledTemporaryFile();
		mfile.write(rfile.read());
		mfile.flush();
		
		tag.link(mfile);
		tag.remove(eyeD3.ID3_ANY_VERSION);
		
		mfile.flush();
		mfile.seek(0);
		
		mhash = hashlib.md5(mfile.read()).hexdigest();
		mfile.seek(0);
		clio.println("Memory version: {}".format(mhash));
		try:
			tags = Song(mfile).getTags();
			lttdl = 0;
			for tag in tags:
				ttdl = len(tagTypes[tag['id']]);
				lttdl = ttdl if (ttdl > lttdl) else lttdl;
			tfmt = "{0[version]} {0[id]} {1:" + str(lttdl) + "} {0[content]}";
			for tag in tags:
				clio.printf(tfmt, tag, tagTypes[tag['id']]);
			
		except Exception as e:
			clio.printf("[ERROR] {}: {}", path, str(e));
		mfile.close();
		
		rfile = open(path,"r+b");
		
		#tag.link(rfile);
		#tag.remove(eyeD3.ID3_ANY_VERSION);	#ID3_V1
		
		rfile.seek(0);
		
		rhash = hashlib.md5(rfile.read()).hexdigest();
		rfile.seek(0);
		clio.println("Real version:   {}".format(rhash));
		try:
			tags = Song(rfile).getTags();
			lttdl = 0;
			for tag in tags:
				ttdl = len(tagTypes[tag['id']]);
				lttdl = ttdl if (ttdl > lttdl) else lttdl;
			tfmt = "{0[version]} {0[id]} {1:" + str(lttdl) + "} {0[content]}";
			for tag in tags:
				clio.printf(tfmt, tag, tagTypes[tag['id']]);
			
		except Exception as e:
			clio.printf("[ERROR] {}: {}", path, str(e));
	clio.println();
#/main

class Song():
	gpat = re.compile(r'\D*(\d+).*');
	def __init__(self, mp3File):
		self.tags = [];
		tag = eyeD3.Tag();
		tag.link(mp3File, eyeD3.ID3_V1);
		for frame in tag.frames:
			self.addTagInfo(frame);
		tag.link(mp3File, eyeD3.ID3_V2);
		for frame in tag.frames:
			self.addTagInfo(frame);
	#/init
	
	def getTags(self):
		return self.tags;
	#/getTags
	
	def addTagInfo(self, frame):
		th = frame.header;
		tid = th.id;
		tver = th.majorVersion + (th.minorVersion / 10);
		#tver = "{}.{}".format(th.majorVersion, th.minorVersion);
		if (2 <= tver < 2.3):
			tid = eyeD3.frames.TAGS2_2_TO_TAGS_2_3_AND_4[tid];					#Convert ID3v2.2 tag IDs to v2.3+
		content = getFrameContent(frame);
		
		if ((tver < 2) and (tid == "TCON")):
			gmatch = Song.gpat.match(content);
			if gmatch:
				gid = int(gmatch.group(1));			
				if (gid > len(v1_genres)):
					return;														#ID3v1 genres have a limited valid range of index values
				else:
					content = v1_genres[gid];
		
		self.tags.append({'id': tid, 'version': tver, 'content': content});
	#/addTagInfo
#/Song

def getFrameContent(frame):
	if isinstance(frame, eyeD3.frames.CommentFrame):
		content = frame.comment;
	elif isinstance(frame, eyeD3.frames.DateFrame):
		content = frame.date_str;
	elif isinstance(frame, eyeD3.frames.ImageFrame):
		content = byteFmt(len(frame.imageData)) + " " + frame.mimeType;
	elif isinstance(frame, eyeD3.frames.LyricsFrame):
		content = frame.lyrics;
	elif isinstance(frame, eyeD3.frames.MusicCDIdFrame):
		content = frame.getFrameDesc();
	elif isinstance(frame, eyeD3.frames.ObjectFrame):
		content = frame.description;
	elif isinstance(frame, eyeD3.frames.PlayCountFrame):
		content = frame.count;
	elif isinstance(frame, eyeD3.frames.TextFrame):
		content = frame.text;
	elif isinstance(frame, eyeD3.frames.URLFrame):
		content = frame.url;
	elif isinstance(frame, eyeD3.frames.UniqueFileIDFrame):
		content = frame.id;
	elif isinstance(frame, eyeD3.frames.UnknownFrame):
		content = frame.getFrameDesc();
	elif isinstance(frame, eyeD3.frames.UserTextFrame):
		content = frame.text;
	elif isinstance(frame, eyeD3.frames.UserURLFrame):
		content = frame.url;
	else:
		content = "???";
	return content;
#/getFrameContent

def getPrintable(frame, tagTypes):
	hd = frame.header;
	version = "v{}.{}".format(hd.majorVersion, hd.minorVersion);
	fid = hd.id;
	content = getFrameContent(frame);
	return "{} {} {:20s} {}".format(version, fid, tagTypes[fid], content);
#/getPrintable

if __name__ == "__main__":
	main();
#/__main__
