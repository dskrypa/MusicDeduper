
v1_fields = ["title","artist","album","year","comment","track","genre"]

tagTypes= {
    #iTunes Verified Fields
    "TIT2": "Song title",
    "TALB": "Album",
    "TPE2": "Album Artist",
    "TPE1": "Artist",
    
    "TCOM": "Composer",
    "TRCK": "Track number",
    "TPOS": "Disk Number",
    "TCON": "Genre",
    "TYER": "Year",                                                                #V2.3
    
    "USLT": "Lyrics",
    "TIT1": "Grouping",
    "TBPM": "BPM (beats per minute)",
    "TCMP": "Compilation (boolean)",                                            #iTunes only
    "TSOC": "Composer [for sorting]",                                            #iTunes only
    "TSO2": "Album Artist [for sorting]",                                        #iTunes only
    "TSOT": "Song title [for sorting]",
    "TSOA": "Album [for sorting]",
    "TSOP": "Artist [for sorting]",
    
    "TENC": "Encoded by",
    
    #iTunes-only Fields
    "TDES": "Podcast Description",
    "TGID": "Podcast Identifier",
    "WFED": "Podcast URL",
    "PCST": "Podcast Flag",
    
    #General Fields
    "AENC": "Audio encryption",
    "APIC": "Album Cover",
    "ASPI": "Audio seek point index",
    "COMM": "Comments",
    "COMR": "Commercial frame",
    "ENCR": "Encryption method registration",
    "EQUA": "Equalisation",                                                        #V2.3
    "EQU2": "Equalisation (2)",                                                    #V2.4
    "ETCO": "Event timing codes",
    "GEOB": "General encapsulated object",
    "GRID": "Group identification registration",
    "LINK": "Linked information",
    "MCDI": "Music CD identifier",
    "MLLT": "MPEG location lookup table",
    "OWNE": "Ownership frame",
    "PRIV": "Private frame",
    "PCNT": "Play counter",
    "POPM": "Popularimeter",
    "POSS": "Position synchronisation frame",
    "RBUF": "Recommended buffer size",
    "RVAD": "Relative volume adjustment",                                        #V2.3
    "RVA2": "Relative volume adjustment (2)",                                    #V2.4
    "RVRB": "Reverb",
    "SEEK": "Seek frame",
    "SIGN": "Signature frame",
    "SYLT": "Synchronised lyric/text",
    "SYTC": "Synchronised tempo codes",
    "TCOP": "Copyright message",
    "TDEN": "Encoding time",
    "TDLY": "Playlist delay",    
    "TORY": "Original release year",                                            #V2.3
    "TDOR": "Original release time",                                            #V2.4
    "TDAT": "Date",                                                                #V2.3
    "TIME": "Time",                                                                #V2.3
    "TRDA": "Recording Date",                                                    #V2.3
    "TDRC": "Date",                                                                #V2.4
    "TDRL": "Release time",
    "TDTG": "Tagging time",
    "TEXT": "Lyricist/Text writer",
    "TFLT": "File type",
    "IPLS": "Involved people list",                                                #V2.3
    "TIPL": "Involved people list",                                                #V2.4
    "TIT3": "Subtitle/Description refinement",
    "TKEY": "Initial key",
    "TLAN": "Language(s)",
    "TLEN": "Length",
    "TMCL": "Musician credits list",                                            #V2.4
    "TMED": "Media type",
    "TMOO": "Mood",
    "TOAL": "Original album/movie/show title",
    "TOFN": "Original filename",
    "TOLY": "Original lyricist(s)/text writer(s)",
    "TOPE": "Original artist(s)/performer(s)",
    "TOWN": "File owner/licensee",
    "TPE3": "Conductor",
    "TPE4": "Interpreted, remixed, or otherwise modified by",
    "TPRO": "Produced notice",
    "TPUB": "Publisher",
    "TRSN": "Internet radio station name",
    "TRSO": "Internet radio station owner",
    "TSRC": "ISRC (international standard recording code)",
    "TSSE": "Encoding Settings",
    "TSST": "Set subtitle",
    "TXXX": "User-defined",
    "UFID": "Unique file identifier",
    "USER": "Terms of use",
    "WCOM": "Commercial info",
    "WCOP": "Copyright/Legal info",
    "WOAF": "Audio file's website",
    "WOAR": "Artist's website",
    "WOAS": "Audio source's website",
    "WORS": "Radio station's website",
    "WPAY": "Payment",
    "WPUB": "Publisher's website",
    "WXXX": "User-defined URL",
    
    #Deprecated
    "TSIZ": "Size",                                                                #Deprecated in V2.4
    
    #Invalid tags discovered
    "ITNU": "iTunesU? [invalid]",
    "TCAT": "Podcast Category? [invalid]",
    "MJCF": "MediaJukebox? [invalid]",
}

v1_genres = [
    "Blues",
    "Classic Rock",
    "Country",
    "Dance",
    "Disco",
    "Funk",
    "Grunge",
    "Hip-Hop",
    "Jazz",
    "Metal",
    "New Age",
    "Oldies",
    "Other",
    "Pop",
    "R&B",
    "Rap",
    "Reggae",
    "Rock",
    "Techno",
    "Industrial",
    "Alternative",
    "Ska",
    "Death Metal",
    "Pranks",
    "Soundtrack",
    "Euro-Techno",
    "Ambient",
    "Trip-Hop",
    "Vocal",
    "Jazz+Funk",
    "Fusion",
    "Trance",
    "Classical",
    "Instrumental",
    "Acid",
    "House",
    "Game",
    "Sound Clip",
    "Gospel",
    "Noise",
    "Alt. Rock",
    "Bass",
    "Soul",
    "Punk",
    "Space",
    "Meditative",
    "Instrumental Pop",
    "Instrumental Rock",
    "Ethnic",
    "Gothic",
    "Darkwave",
    "Techno-Industrial",
    "Electronic",
    "Pop-Folk",
    "Eurodance",
    "Dream",
    "Southern Rock",
    "Comedy",
    "Cult",
    "Gangsta Rap",
    "Top 40",
    "Christian Rap",
    "Pop/Funk",
    "Jungle",
    "Native American",
    "Cabaret",
    "New Wave",
    "Psychedelic",
    "Rave",
    "Showtunes",
    "Trailer",
    "Lo-Fi",
    "Tribal",
    "Acid Punk",
    "Acid Jazz",
    "Polka",
    "Retro",
    "Musical",
    "Rock & Roll",
    "Hard Rock",
    "Folk",
    "Folk-Rock",
    "National Folk",
    "Swing",
    "Fast-Fusion",
    "Bebop",
    "Latin",
    "Revival",
    "Celtic",
    "Bluegrass",
    "Avantgarde",
    "Gothic Rock",
    "Progressive Rock",
    "Psychedelic Rock",
    "Symphonic Rock",
    "Slow Rock",
    "Big Band",
    "Chorus",
    "Easy Listening",
    "Acoustic",
    "Humour",
    "Speech",
    "Chanson",
    "Opera",
    "Chamber Music",
    "Sonata",
    "Symphony",
    "Booty Bass",
    "Primus",
    "Porn Groove",
    "Satire",
    "Slow Jam",
    "Club",
    "Tango",
    "Samba",
    "Folklore",
    "Ballad",
    "Power Ballad",
    "Rhythmic Soul",
    "Freestyle",
    "Duet",
    "Punk Rock",
    "Drum Solo",
    "A Cappella",
    "Euro-House",
    "Dance Hall",
    "Goa",
    "Drum & Bass",
    "Club-House",
    "Hardcore",
    "Terror",
    "Indie",
    "BritPop",
    "Afro-Punk",
    "Polsk Punk",
    "Beat",
    "Christian Gangsta Rap",
    "Heavy Metal",
    "Black Metal",
    "Crossover",
    "Contemporary Christian",
    "Christian Rock",
    "Merengue",
    "Salsa",
    "Thrash Metal",
    "Anime",
    "JPop",
    "Synthpop",
    "Abstract",
    "Art Rock",
    "Baroque",
    "Bhangra",
    "Big Beat",
    "Breakbeat",
    "Chillout",
    "Downtempo",
    "Dub",
    "EBM",
    "Eclectic",
    "Electro",
    "Electroclash",
    "Emo",
    "Experimental",
    "Garage",
    "Global",
    "IDM",
    "Illbient",
    "Industro-Goth",
    "Jam Band",
    "Krautrock",
    "Leftfield",
    "Lounge",
    "Math Rock",
    "New Romantic",
    "Nu-Breakz",
    "Post-Punk",
    "Post-Rock",
    "Psytrance",
    "Shoegaze",
    "Space Rock",
    "Trop Rock",
    "World Music",
    "Neoclassical",
    "Audiobook",
    "Audio Theatre",
    "Neue Deutsche Welle",
    "Podcast",
    "Indie Rock",
    "G-Funk",
    "Dubstep",
    "Garage Rock",
    "Psybient"
]
