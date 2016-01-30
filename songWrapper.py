

'''
Author: Douglas Skrypa
Date: 2016.01.30
Version: 1
'''

from __future__ import division;
from django.utils import text as dtext;
import re;
import eyed3_79 as eyed3;
from common import *;
from _constants import *;

class SongException(Exception):
	def __init__(self, value):
		self.value = value;
	def __str__(self):
		return repr(self.value);
#/HashException

class SongTag():
	def __init__(self, tid, version, content):
		self.id = tid;
		self.ver = version;
		
		if isinstance(content, eyed3.core.Date):
			self.val = str(content);
		elif isinstance(content, unicode):
			self.val = content;
		else:
			try:
				self.val = unicode(content, "utf-8");
			except Exception as e:
				self.val= content;
				#raise e;
			#self.val = str(content);
	#/init
	def __getitem__(self, key):
		if (key == "id"):
			return self.id;
		elif (key == "ver"):
			return self.ver;
		elif (key == "val"):
			return self.val;
	#/getitem
#/SongTag

class Song():
	gpat = re.compile(r'\D*(\d+).*');
	def __init__(self, fpath):
		self.fpath = fpath;
		self.updateTags();
	#/init
	
	def updateTags(self):
		self.tags = [];
		self.tagsById = {};
		self.versions = {};
		self.addTagsFromAudioFile(eyed3.load(self.fpath, (1,None,None)));
		self.addTagsFromAudioFile(eyed3.load(self.fpath, (2,None,None)));
	#/updateTags
	
	def addTagsFromAudioFile(self, af):
		if (af.tag == None): return;
		fs = af.tag.frame_set;
		ver = af.tag.version;
		tver = ver[0] + (ver[1]/10);
		for tid in fs:
			frames = fs[tid];
			for frame in frames:
				self.addTagInfo(tid, tver, frame);
	#/addTagsFromAudioFile
	
	def addTagInfo(self, tid, tver, frame):
		content = getFrameContent(frame);
		if ((tver < 2) and (tid == "TCON")):
			gmatch = Song.gpat.match(content);
			if gmatch:
				gid = int(gmatch.group(1));			
				if (gid > len(v1_genres)):
					return;														#ID3v1 genres have a limited valid range of index values
				else:
					content = v1_genres[gid];
		
		st = SongTag(tid, tver, content)
		self.tags.append(st);
		if not (tid in self.tagsById):
			self.tagsById[tid] = [];
		self.tagsById[tid].append(st);
		self.versions[tver] = True;
	#/addTagInfo
	
	def remTag(self, tagid, id3v=None):
		if (tagid in self.tagsById):
			if (id3v != None):
				ev = (int(id3v),None,None);
				af = eyed3.load(self.fpath, ev);
				if (af.tag == None): return;
				af.tag.frame_set.pop(tagid);
				af.tag.save(version=(2,4,0));
			else:
				for ver in self.getVersions(tagid):
					ev = (int(ver),None,None);
					af = eyed3.load(self.fpath, ev);
					af.tag.frame_set.pop(tagid);
					af.tag.save(version=(2,4,0));
		self.updateTags();
	#/remTag
	
	def getArtist(self):		return self.getTagVal("TPE1");
	def getAlbumArtist(self):	return self.getTagVal("TPE2");
	def getAlbum(self):			return self.getTagVal("TALB");
	def getTitle(self):			return self.getTagVal("TIT2");
	def getTrack(self):			return self.getTagVal("TRCK");
	
	def getTagVal(self, tid, safe=False):
		if (tid not in self.tagsById):
			return None;
		
		if self.hasMultipleVersionsOf(tid):
			for tag in self.tagsById[tid]:
				if (tag.ver < 2):
					tag1 = tag.val;
				else:
					tag2 = tag.val;
			if not tag2.startswith(tag1):
				raise SongException("Multiple versions of " + tid);
		else:
			tag2 = self.tagsById[tid][0].val;
		if safe:
			return dtext.get_valid_filename(tag2).replace("_", " ");
		else:
			return tag2;
	#/getTagVal
	
	def hasMultipleVersions(self):
		return (len(self.versions) > 1);
	#/hasMultipleVersions
	
	def hasMultipleVersionsOf(self, tagid):
		if (len(self.versions) < 2) or (tagid not in self.tagsById):
			return False;
		
		ver = 0;
		for tag in self.tagsById[tagid]:
			ver = tag["version"] if (ver == 0) else ver;
			if (ver != tag["version"]):
				return True;
		return False;
	#/hasMultipleVersionsOf
	
	def getVersions(self, tagid):
		if (tagid in self.tagsById):
			vers = {};
			for tag in self.tagsById[tagid]:
				vers[tag["version"]] = True;
			return vers;
		return None;
	#/getVersions
	
	def isFromCompilation(self):
		return ("TCMP" in self.tagsById);
	#/isFromCompilation
	
	def hasTag(self, tagid):
		return (tagid in self.tagsById);
	#/hasTag
	
	def getTagsById(self, tagid):
		return self.tagsById[tagid] if (tagid in self.tagsById) else None;
	#/getTagsById
	
	def getTags(self):
		return self.tags;
	#/getTags
#/Song

def getFrameContent(frame):
	if isinstance(frame, eyed3.id3.frames.ChapterFrame):
		content = frame.title;
	elif isinstance(frame, eyed3.id3.frames.CommentFrame):
		content = frame.text;
	elif isinstance(frame, eyed3.id3.frames.DateFrame):
		content = frame.date;
	elif isinstance(frame, eyed3.id3.frames.DescriptionLangTextFrame):
		content = frame.text;
	elif isinstance(frame, eyed3.id3.frames.ImageFrame):
		content = byteFmt(len(frame.image_data)) + " " + frame.mime_type;
	elif isinstance(frame, eyed3.id3.frames.LyricsFrame):
		content = frame.text;
	elif isinstance(frame, eyed3.id3.frames.MusicCDIdFrame):
		content = frame.toc;
	elif isinstance(frame, eyed3.id3.frames.ObjectFrame):
		content = frame.filename;
	elif isinstance(frame, eyed3.id3.frames.PlayCountFrame):
		content = frame.render();
	elif isinstance(frame, eyed3.id3.frames.PopularityFrame):
		content = frame.rating;
	elif isinstance(frame, eyed3.id3.frames.PrivateFrame):
		#content = frame.render();
		content = "???";
	elif isinstance(frame, eyed3.id3.frames.TermsOfUseFrame):
		content = frame.text;
	elif isinstance(frame, eyed3.id3.frames.TextFrame):
		content = frame.text;
	elif isinstance(frame, eyed3.id3.frames.TocFrame):
		content = frame.render();
	elif isinstance(frame, eyed3.id3.frames.UniqueFileIDFrame):
		content = frame.render();
	elif isinstance(frame, eyed3.id3.frames.UrlFrame):
		content = frame.url;
	elif isinstance(frame, eyed3.id3.frames.UserTextFrame):
		content = frame.text;
	elif isinstance(frame, eyed3.id3.frames.UserUrlFrame):
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