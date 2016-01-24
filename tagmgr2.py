#!/usr/bin/python

'''
Author: Douglas Skrypa
Date: 2016.01.24
Version: 0.1
'''

from __future__ import division;
from argparse import ArgumentParser;
import re;
import eyeD3;
from common import *;
from _constants import *;


def main():
	parser = ArgumentParser(description="Music info printer");
	parser.add_argument("--path", "-p", help="The directory to scan for music", required=True);
	#parser.add_argument("--remove","-r", nargs="+", metavar="tagId", help="A tag to remove from all mp3s in the given directory", action="append");
	args = parser.parse_args();
	
	#remTags = [item for sublist in args.remove for item in sublist];
	
	#print("Tags to be removed:");
	#for rtag in remTags:
	#	tagName = tagTypes[rtag] if rtag in tagTypes else "???";
	#	print("{}\t{}".format(rtag, tagName));
	
	paths = getFilteredPaths(args.path, "mp3");
	
	c = 0;
	t = len(paths);
	tl = str(len(str(t)));
	spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}]";
	spfmt += "[Rate: {:,.2f} files/sec][Remaining: ~{}] Current file: {}";
	pt = PerfTimer();
	
	fmt = "{}  {}";
	
	for path in paths:
		c += 1;
		dt = pt.elapsed();
		rate = c/dt;
		remaining = fTime((t-c) / rate);
		clio.showf(spfmt, c/t, c, fTime(dt), rate, remaining, path);
		
		clio.println();
		clio.println(path);
		
		try:
			tags = Song(path).getTags();
			lttdl = 0;
			for tag in tags:
				ttdl = len(tagTypes[tag['id']]);
				lttdl = ttdl if (ttdl > lttdl) else lttdl;
			tfmt = "{0[version]} {0[id]} {1:" + str(lttdl) + "} {0[content]}";
			for tag in tags:
				clio.printf(tfmt, tag, tagTypes[tag['id']]);
			
		except Exception as e:
			clio.printf("[ERROR] {}: {}", path, str(e));
	
	
	
#/main

class Song():
	gpat = re.compile(r'\D*(\d+).*');
	def __init__(self, path):
		self.path = path;
		self.tags = [];
		tag = eyeD3.Tag();
		tag.link(path, eyeD3.ID3_V1);
		for frame in tag.frames:
			self.addTagInfo(frame);
		tag.link(path, eyeD3.ID3_V2);
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
