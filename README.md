# MusicDeduper

The goal of this project is to de-duplicate a collection of MP3 files.

A little while ago, my father asked me to help him with his MP3 collection.  He had a lot of duplicate files that needed to be discarded, and he wanted to get them more organized.

It turned out that they were all on an external hard drive, and everything was in one big folder with no subfolders.  That made things slightly easier from a programming standpoint...

There were over 115k files to comb through.

The first pass that I used compared files by their MD5 hashes (I am aware that MD5 has been proven to have collisions, but it is fine for this task).  This reduced the "unique" file count to about 44k.

The second pass that I used compared files by the MD5 hash of their audio content.  This reduced the "unique" file count to about 25k.  This was achieved with the help of the pydub library, available here: https://github.com/jiaaro/pydub

I have yet to decide upon what I will use for the task of organizing files into folders, renaming them, and cleaning up ID3 data.
