#!/usr/bin/python3

'''
Author: Douglas Skrypa
Date: 2016.01.23
Version: 0.1
'''

from argparse import ArgumentParser;
from mutagen.mp3 import MP3;
from mutagen.id3 import ID3;
from common import *;
from _constants import *;

def main():
	parser = ArgumentParser(description="Music info printer");
	parser.add_argument("--path", "-p", help="The directory to scan for music", required=True);
	parser.add_argument("--remove","-r", nargs="+", metavar="tagId", help="A tag to remove from all mp3s in the given directory", action="append");
	args = parser.parse_args();
	
	remTags = [item for sublist in args.remove for item in sublist];
	
	print("Tags to be removed:");
	for rtag in remTags:
		tagName = tagTypes[rtag] if rtag in tagTypes else "???";
		print("{}\t{}".format(rtag, tagName));
	
	paths = getFilteredPaths(args.path, "mp3");
	
	
	c = 0;
	t = len(paths);
	tl = str(len(str(t)));
	spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}]";
	spfmt += "[Rate: {:,.2f} files/sec][Remaining: ~{}] Current file: {}";
	pt = PerfTimer();
	
	discTagTypes = {};
	extended = {};
	
	for path in paths:
		c += 1;
		dt = pt.elapsed();
		rate = c/dt;
		remaining = fTime((t-c) / rate);
		clio.showf(spfmt, c/t, c, fTime(dt), rate, remaining, path);
		
		try:		
			audio = MP3(path);
			for tagId in audio:
				rtid = tagId[:4] if (":" in tagId) else tagId;
				
				if rtid in remTags:
					clio.printf("Removing {} from {}", rtid, path);
		except Exception as e:
			clio.printf("[ERROR] {}: {}", path, str(e));
	

		
#	'TXXX'
#/main

def countUsage(paths):
	c = 0;
	t = len(paths);
	tl = str(len(str(t)));
	spfmt = "[{:7.2%}|{:"+tl+"d}/"+str(t)+"][Elapsed: {}]";
	spfmt += "[Rate: {:,.2f} files/sec][Remaining: ~{}] Current file: {}";
	pt = PerfTimer();
	
	discTagTypes = {};
	extended = {};
	
	for path in paths:
		c += 1;
		dt = pt.elapsed();
		rate = c/dt;
		remaining = fTime((t-c) / rate);
		clio.showf(spfmt, c/t, c, fTime(dt), rate, remaining, path);
		
		try:		
			audio = MP3(path);
			for tagId in audio:
				rtid = tagId[:4] if (":" in tagId) else tagId;
				
				if rtid in remTags:
					clio.printf("Removing {} from {}", rtid, path);
				
			
				if ":" in tagId:
					etid = tagId[:4];
					if (etid == "APIC"):
						if (etid in discTagTypes):
							discTagTypes[etid] += 1;
						else:
							discTagTypes[etid] = 1;
					else:
						if (tagId in extended):
							extended[tagId] += 1;
						else:
							extended[tagId] = 1;
				else:	
					if (tagId in discTagTypes):
						discTagTypes[tagId] += 1;
					else:
						discTagTypes[tagId] = 1;
		except Exception as e:
			clio.printf("[ERROR] {}: {}", path, str(e));
		
		
	for dtid in discTagTypes:
		tagName = tagTypes[dtid] if dtid in tagTypes else "???";
		print("{:,d}\t{}\t{}".format(discTagTypes[dtid], dtid, tagName));
	
	for etid in extended:
		tagId = etid[:4];
		tagExtended = etid[5:];
		tagName = tagTypes[tagId] if tagId in tagTypes else "???";
		print("{:,d}\t{}\t{}\t{}".format(extended[etid], tagId, tagName, tagExtended));
#/countUsage

def showInfo(paths):
	tagTypes = loadTagIds("frameids.txt");	
	
	for path in paths:
		audio = MP3(path);
		
		print();
		print(path);
		
		info = audio.pprint().splitlines();
		print(info[0]);
		
		for line in info[1:]:
			line = line.strip();
			tagId = line[:4];
			tagType = "User-defined" if (tagId == "TXXX") else tagTypes[tagId];
			tagVal = line.split("=")[1].strip();
			print("{}\t{}\t{}".format(tagId, tagType, tagVal));
#/showInfo

if __name__ == "__main__":
	main();
#/__main__
