

'''
Author: Douglas Skrypa
Date: 2017.02.04
Version: 1.4.1
'''

from __future__ import division
#from django.utils import text as dtext
import re
import eyed3_79 as eyed3
from common import *
from _constants import *

compIndicatorsA = {"soundtrack":True,"variousartists":True}
compIndicatorsB = ["billboard","now thats what i call music","power trakks"]


class SongException(Exception):
    def __init__(self, value):
        self.value = value

    def __str__(self):
        return repr(self.value)

class SongTag():
    def __init__(self, tid, version, content):
        self.id = tid
        self.ver = version
        
        if isinstance(content, eyed3.core.Date):
            self.val = str(content)
        elif isinstance(content, unicode):
            self.val = content
        else:
            try:
                self.val = unicode(content, "utf-8")
            except Exception as e:
                self.val= content
                #raise e

    def __getitem__(self, key):
        if key == "id":
            return self.id
        elif key == "ver":
            return self.ver
        elif key == "val":
            return self.val

    def __str__(self):
        return "[{}_{}]{}".format(self.id, self.ver, self.val)

    def __repr__(self):
        return "[{}_{}]{}".format(self.id, self.ver, self.val)

class Song():
    gpat = re.compile(r'\D*(\d+).*')
    def __init__(self, fpath):
        self.fpath = fpath
        self._isBadFile = False
        self.newPath = None
        self.better = None
        self.bitrate = None
        self.updateTags()
    
    def setBetter(self, isBetter):
        self.better = isBetter
    
    def isBetter(self):
        return self.better
    
    def getNewPath(self):
        return self.newPath
    
    def setNewPath(self, newPath):
        self.newPath = newPath
    
    def getBitrate(self):
        return self.bitrate
    
    def isBad(self):
        return self._isBadFile
    
    def updateTags(self):
        self.tags = []
        self.tagsById = {}
        self.versions = {}
        try:
            self._addTagsFromAudioFile(eyed3.load(self.fpath, (1,None,None)))
            self._addTagsFromAudioFile(eyed3.load(self.fpath, (2,None,None)))
        except (ValueError, SongException) as e:
            self._isBadFile = True
    
    def trimTags(self):
        changed = {}
        changed1 = self._trimTags(eyed3.load(self.fpath, (1,None,None)))
        if (changed1 is not None):
            changed.update(changed1)
        changed2 = self._trimTags(eyed3.load(self.fpath, (2,None,None)))
        if (changed2 is not None):
            changed.update(changed2)
        return changed
    
    def _trimTags(self, af):
        if (af.tag is None): return None
        fs = af.tag.frame_set
        ver = af.tag.version
        tver = "[" + str(ver[0] + (ver[1]/10)) + "]"
        
        s_artist = af.tag.artist.strip() if (af.tag.artist is not None) else None
        s_aartist = af.tag.album_artist.strip() if (af.tag.album_artist is not None) else None
        s_title = af.tag.title.strip() if (af.tag.title is not None) else None
        s_album = af.tag.album.strip() if (af.tag.album is not None) else None
        
        changed = {}
        if af.tag.artist != s_artist:
            changed[tver + "Artist"] = "'{}' -> '{}'".format(af.tag.artist, s_artist)
            af.tag.artist = s_artist
        if af.tag.album_artist != s_aartist:
            changed[tver + "Album Artist"] = "'{}' -> '{}'".format(af.tag.album_artist, s_aartist)
            af.tag.album_artist = s_aartist
        if af.tag.title != s_title:
            changed[tver + "Title"] = "'{}' -> '{}'".format(af.tag.title, s_title)
            af.tag.title = s_title
        if af.tag.album != s_album:
            changed[tver + "Album"] = "'{}' -> '{}'".format(af.tag.album, s_album)
            af.tag.album = s_album
        
        if len(changed) > 0:
            af.tag.save()
        return changed
    
    def _addTagsFromAudioFile(self, af):
        if (af.tag is None): return
        if (af.info is not None):
            self.bitrate = af.info.mp3_header.bit_rate
        else:
            clio.println("No Audio info for: " + self.fpath)
            raise SongException("No Audio Info")
        fs = af.tag.frame_set
        ver = af.tag.version
        tver = ver[0] + (ver[1]/10)
        for tid in fs:
            frames = fs[tid]
            for frame in frames:
                self._addTagInfo(tid, tver, frame)
    
    def _addTagInfo(self, tid, tver, frame):
        content = getFrameContent(frame)
        if ((tver < 2) and (tid == "TCON")):
            gmatch = Song.gpat.match(content)
            if gmatch:
                gid = int(gmatch.group(1))            
                if (gid > len(v1_genres)):
                    return                                                        #ID3v1 genres have a limited valid range of index values
                else:
                    content = v1_genres[gid]
        st = SongTag(tid, tver, content)
        self.tags.append(st)
        if not (tid in self.tagsById):
            self.tagsById[tid] = []
        self.tagsById[tid].append(st)
        self.versions[tver] = True
    
    def remTags(self, toRemove):
        if self._isBadFile: return
        for v in range(2, 0, -1):                                                #Check V2 then V1
            changed = False
            af = eyed3.load(self.fpath, (v,None,None))                            #Load the tags for the selected version
            if (af.tag is not None):                                                #If there are any tags
                for tagid in toRemove:                                            #Iterate through the tags to be removed
                    trv = toRemove[tagid]                                        #Get the version to be removed
                    if (trv is None) or (int(trv) == v):                        #If the version isn't set or matches the selected version
                        if (tagid in af.tag.frame_set):                            #If the tag id is present in the file
                            af.tag.frame_set.pop(tagid)                        #Remove it
                            changed = True                                        #Indicate that a change was made that should be saved
                if changed:                                                        #If a change was made
                    atv = af.tag.version                                        #Check the version number of the tag
                    if (atv[0] == 2):                                            #If it's version 2
                        af.tag.save(version=(2,4,0))                            #Save as version 2.4
                    else:                                                        #Otherwise if it's version 1
                        af.tag.save(version=atv)                                #Save as its original version
        self.updateTags()
    
    def getArtist(self):        return self.getTagVal("TPE1")
    def getAlbumArtist(self):   return self.getTagVal("TPE2")
    def getAlbum(self):         return self.getTagVal("TALB")
    def getTitle(self):         return self.getTagVal("TIT2")
    def getTrack(self):         return self.getTagVal("TRCK")
    
    def getTagVal(self, tid, safe=False):
        if tid not in self.tagsById:
            return None
        
        if self.hasMultipleVersionsOf(tid):
            for tag in self.tagsById[tid]:
                if tag.ver < 2:
                    tag1 = tag.val
                else:
                    tag2 = tag.val
            if not tag2.startswith(tag1):
                if tid == "TRCK":                                                #If it's the track number
                    try:
                        t1 = normalizeTrack(tag1)
                        t2 = normalizeTrack(tag2)
                        if (t1 != t2):
                            raise SongException("Multiple versions of " + tid)
                    except ValueError as ve:
                        raise SongException("Multiple versions of " + tid)
                elif (tid in ("TPE1", "TPE2")):                                    #If it's the artist / album artist
                    a1 = normalizeArtist(tag1)
                    a2 = normalizeArtist(tag2)
                    if (a1 != a2):
                        raise SongException("Multiple versions of " + tid)
                elif (tid == "TALB"):
                    a1 = normalizeAlbum(tag1)
                    a2 = normalizeAlbum(tag2)
                    if (a1 != a2):
                        raise SongException("Multiple versions of " + tid)
                else:
                    raise SongException("Multiple versions of " + tid)
        else:
            tag2 = self.tagsById[tid][0].val
        if safe:
            #dcleaned = dtext.get_valid_filename(tag2).replace("_", " ")        #Cleanup using Django first
            return cleanup(tag2)
        else:
            return tag2
    
    def hasMultipleVersions(self):
        return (len(self.versions) > 1)
    
    def hasMultipleVersionsOf(self, tagid):
        if (not (len(self.versions) > 1)) or (tagid not in self.tagsById):
            return False
        ver = 0
        for tag in self.tagsById[tagid]:
            ver = tag.ver if (ver == 0) else ver
            if ver != tag.ver:
                return True
        return False
    
    def getVersions(self, tagid):
        if tagid in self.tagsById:
            vers = {}
            for tag in self.tagsById[tagid]:
                vers[tag.ver] = True
            return vers
        return None
    
    def isPodcast(self):
        return "PCST" in self.tagsById
    
    def isFromCompilation(self):
        return "TCMP" in self.tagsById
    
    def mayBeFromCompilation(self):
        albArtist = normalize(self.getTagVal("TPE2", True))
        artist = normalize(self.getTagVal("TPE1", True))
        if (albArtist in compIndicatorsA) or (artist in compIndicatorsA):
            return True
        
        album = self.getTagVal("TALB", True)
        if ((album is None) or (len(album) < 1)):
            return False
        album = album.lower()
        for ci in compIndicatorsB:
            if ci in album:
                return True
        return False
    
    def hasTag(self, tagid):
        return tagid in self.tagsById
    
    def getTagsById(self, tagid):
        return self.tagsById[tagid] if (tagid in self.tagsById) else None
    
    def getTags(self):
        return self.tags


def normalize(strng):
    if (strng is None) or (len(strng) < 1):
        return strng
    return strng.lower().replace(" ","")


def normalizeAlbum(album):
    norm = album.lower().replace("(","[").replace(")","]")
    return re.sub(r'\[(cd|dis[ck])\s*(\d+)',r'[disk \2',norm) 


def normalizeArtist(artist):
    norm = artist.lower()
    if norm.startswith("the"):
        return re.sub(r'the (.*)',r'\1, the',norm)
    return norm


def normalizeTrack(track):
    return int(track.split("/")[0]) if ("/" in track) else int(track)


frame_type_content_map = {
    "ChapterFrame": "title",
    "DateFrame": "date",
    "UrlFrame": "url",
    "UserUrlFrame": "url",
    "MusicCDIdFrame": "toc",
    "ObjectFrame": "filename",
    "PopularityFrame": "rating",
    "CommentFrame": "text",
    "DescriptionLangTextFrame": "text",
    "LyricsFrame": "text",
    "TermsOfUseFrame": "text",
    "TextFrame": "text",
    "UserTextFrame": "text",
}


def getFrameContent(frame):
    if isinstance(frame, eyed3.id3.frames.ImageFrame):
        return byteFmt(len(frame.image_data)) + " " + frame.mime_type
    elif isinstance(frame, eyed3.id3.frames.PrivateFrame):
        #return frame.render()
        return "???"
    else:
        for ftype in ("PlayCountFrame", "TocFrame", "UniqueFileIDFrame"):
            if isinstance(frame, getattr(eyed3.id3.frames, ftype)):
                return frame.render()

        for ftype, fattr in frame_type_content_map.items():
            if isinstance(frame, getattr(eyed3.id3.frames, ftype)):
                return getattr(frame, fattr)

        return "???"


def getPrintable(frame, tagTypes):
    hd = frame.header
    version = "v{}.{}".format(hd.majorVersion, hd.minorVersion)
    return "{} {} {:20s} {}".format(version, hd.id, tagTypes[hd.id], getFrameContent(frame))
