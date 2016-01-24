# MusicDeduper

The goal of this project is to de-duplicate a collection of MP3 files.

A little while ago, my father asked me to help him with his MP3 collection.  He had a lot of duplicate files that needed to be discarded, and he wanted to get them more organized.

It turned out that they were all on an external hard drive, and everything was in one big folder with no subfolders.  That made things slightly easier from a programming standpoint...

There were over 115k files to comb through.

The first pass that I used compared files by their MD5 hashes (I am aware that MD5 has been proven to have collisions, but it is fine for this task).  This reduced the "unique" file count to about 44k.

The second pass that I used compared files by the MD5 hash of their audio content.  This reduced the "unique" file count to about 25k.  This was achieved with the help of the pydub library, available here: https://github.com/jiaaro/pydub

I have yet to decide upon what I will use for the task of organizing files into folders, renaming them, and cleaning up ID3 data.

----------------------------------------

These are all a bit of a mess at the moment.  I updated dedupe.py to use a version of eyeD3 that I added a kludge to so that it would work well with SpooledTemporaryFiles.  This lets it get an audio content hash based on what the MP3 would be without any ID3 tags, rather than hashing the data returned from calling an external program to convert the file to WAV as pydub did.  This should dramatically speed it up for a number of reasons:
   * Everything is done in Python now - no external API calls
   * Pydub would create a temporary file on a disk for the conversion to wav, which is no longer necessary
   * Instead of decompressing/converting the MP3 data, a version of the MP3 file stored in memory is truncated to ignore the section that contained ID3 tags
      * This is done entirely in memory - there is no intermediate step where a temporary file needs to be written to / read from disk

Most of the original scripts need to be updated to accept arbitrary paths instead of using the hard-coded ones...  They should also be updated to have in-place options instead of always copying to another directory.  The original idea was to keep the original files as a backup.

Initially, I used a call to an external program to gather ID3 data because it was much simpler than figuring out how to use one of the existing ID3 libraries for Python.  The result was that it would run rather slowly.  After taking the time to learn a bit more about the existing libraries, I figured out how to make both Mutagen and eyeD3 work.

Mutagen was easier to work with initially, but it doesn't support specifying whether you want to read only v1 or v2 tags, and only reads v1 tags if there are no v2 tags present.  Additionally, Mutagen only supports reading tags when given a file name, it will not accept a file object.  This meant that it wouldn't be possible to pass it a temp file that only exists in memory for stripping tags to get the audio data portion.

After playing around with Mutagen for a bit, I switched to eyeD3.  EyeD3 let me specify which version of ID3 data I wanted to access, and it had support for passing a file object instead of just a file path.  I then discovered that SpooledTemporaryFile doesn't actually extend File when eyeD3.Tag's isinstance(f, file) check failed.  I then made a copy of eyeD3, and changed that line to accept SpooledTemporaryFile as well.  I ended up having to make a couple other tweaks to prevent it from closing the temporary file, and to make sure that it would call .seek(0) when necessary to return to the beginning of the file.

When I switched to eyeD3, I had to also switch to Python 2 due to a BytesIO/StringIO implementation discrepancy between them, though I don't remember the exact problem at the moment.  I could probably fix it to work with Python 3 in the edited version of eyeD3, but I haven't gone back to do so yet.  Switching to Python 2 required some adjustments for compatibility.

Files:
dedupe.py		Scans a source directory for mp3s, and copies "unique" files to the destination directory.
tagRemover.py	POC script that led to the improvement of dedupe.py
organizer.py	Organizes a given folder using ID3 data to generate folder structure.  Needs to be updated to use eyeD3/mutagen.
reorganizer.py	Similar to organizer... Both files need to be cleaned up
common.py		Some common functions used in most of these scripts.
_constants.py	Arrays of standard ID3 info, such as genre mappings for ID3v1 and mappings of tag IDs to readable descriptions.
info.py			Prints a list of ID3 tags in use in the files in the given path, and a count of each one
tagmgr.py		Intended to remove tags specified at runtime; ID3v1 limitation of Mutagen realized before continuing
tagmgr2.py		Same intention as above; implemented with eyeD3, only able to read tags at the moment.
