from mutagen.flac import FLAC,Picture
from mutagen.wave import WAVE
from mutagen.id3 import ID3,TALB,TCON,TCOP,TDOR,TDRC,TIT1,TIT2, \
                        TMED,TPE1,TPE2,TPOS,TPUB,TRCK,TRCK,TSRC, \
                        TXXX,TLAN,USLT,APIC,Encoding,PictureType
from mutagen.mp3 import MP3
from mutagen.mp4 import MP4, MP4FreeForm, MP4Cover, AtomDataType
import sys
from pathlib import Path
from enum import StrEnum, IntEnum
from utils.utils import utils

import subprocess
from copy import deepcopy
from PIL import Image
from io import BytesIO
from hashlib import sha1
from shutil import copy as sh_copy
import re

class COMPRESSION_TYPE(IntEnum):
    LOSSLESS = 1
    LOSSY    = 2

class E_TAGS(StrEnum):
    ALBUM = 'album'
    ALBUMARTIST = 'albumartist'
    ALBUMARTISTS = 'albumartists'
    ARTIST = 'artist'
    ARTISTS = 'artists'
    BARCODE = 'barcode'
    CATALOGNUMBER = 'catalognumber'
    COPYRIGHT = 'copyright'
    DATE = 'date'
    DISCNUMBER = 'discnumber'
    DISCTOTAL = 'disctotal'
    GENRE = 'genre'
    ISRC = 'isrc'
    LABEL = 'label'
    LANGUAGE = 'language'
    LYRICS = 'lyrics'
    MEDIA = 'media'
    MB_ALBUMARTISTID = 'musicbrainz_albumartistid'
    MB_ALBUMID = 'musicbrainz_albumid'
    MB_ARTISTID = 'musicbrainz_artistid'
    MB_RELEASEGROUPID = 'musicbrainz_releasegroupid'
    MB_RELEASETRACKID = 'musicbrainz_releasetrackid'
    MB_TRACKID = 'musicbrainz_trackid'
    MB_WORKID = 'musicbrainz_workid'
    ORIGINALDATE = 'originaldate'
    ORIGINALYEAR = 'originalyear'
    RELEASECOUNTRY = 'releasecountry'
    RELEASESTATUS = 'releasestatus'
    RELEASETYPE = 'releasetype'
    SCRIPT = 'script'
    TITLE = 'title'
    TOTALDISCS = 'totaldiscs'
    TOTALTRACKS = 'totaltracks'
    TRACKNUMBER = 'tracknumber'
    TRACKTOTAL = 'tracktotal'
    WORK = 'work'

class TTYPE(StrEnum):
    SINGLE = 'single'
    MULTI = 'multiple'
    SPLIT = 'split'
    OTHER = 'other'

DEFAULT_LYRICS_LANG = 'ENG'
SUPPORTED_E_TAGS = list(E_TAGS)

file_args_aliases = {
    '+f': 'filename',
    '+filename': 'filename'
}

class Tag(object):
    re_tag = r'%([a-zA-Z0-9:<>]*)%'
    re_format = r'([:<>])'

    def __init__(self, e_tag, name, tag_type):
        self.e_tag = e_tag
        self.tag_name = name
        self.type = tag_type

    @property
    def name(self):
        return self.tag_name

class Cover(object):
    def __init__(self, img_str=None, fname=None):
        if img_str:
            self.cover_type = 'embedded'
            self.filename = None
            self.__load_from_str(img_str)
        elif fname:
            self.cover_type = 'file'
            if not isinstance(fname, Path):
                fname = Path(fname)
            self.filename = fname
            self.__load_from_file(fname)
        else:
            raise Exception('Either a hash or a filename must be passed to a Cover object.')
    
    def __load_from_str(self, img_str):
        byte_img = BytesIO(img_str)
        img_hash = Cover.hash_image(byte_img)

        img = Image.open(byte_img)
        if img.format.upper() not in ('JPG', 'JPEG'):
            img = img.convert("RGB")

        self.img = img
        self.img_str = img_str
        self.mime = 'image/jpeg'
        self.suffix = '.jpg'
        self.width = img.width
        self.height = img.height
        self.hash = img_hash

    def __load_from_file(self, fname):
        with open(fname, 'rb') as f_image:
            img_str = f_image.read()
        self.__load_from_str(img_str)

    def __hash__(self):
        return hash((self.hash, self.cover_type, self.mime))

    def __eq__(self, other):
        if isinstance(other, Cover):
            if self.filename and other.filename:
                if self.hash == other.hash and \
                    self.filename.suffix == other.filename.suffix:
                    # Both are files and they have the same hash and suffix
                    return True
                else:
                    # Both are files, but either their hash or their suffix differs.
                    # Don't want 2 files with the same hash that are a PNG and JPG together.
                    return False
            elif self.hash == other.hash:
                # At least one is not a file on the file system
                return True
            else:
                # At least one is not a file and their hashes don't match.
                return False
        else:
            # other isn't even a cover!
            return False

    def __str__(self):
        self_str = f'{self.hash}: {self.cover_type} cover ({self.width}x{self.height})'
        if self.cover_type in ('file', 'merged'):
            self_str += f' ({str(self.filename)})'
        return self_str

    def copy(self):
        cover_copy = Cover(img_str=self.img_str)
        cover_copy.cover_type = 'copied'
        return cover_copy

    # Doesn't actually merge anything, just sets that 2 covers are the same for printing purposes.
    def merge(self, other):
        if self == other:
            self.type = 'merged'
            other.type = 'merged'
            if self.filename:
                other.filename = self.filename
            else:
                self.filename = other.filename
        else:
            raise Exception('Cannot merge covers with different hashes')

    @staticmethod
    def hash_image(byte_image):
        BUF_SIZE = 65536
        img_hash = sha1()

        while True:
            data = byte_image.read(BUF_SIZE)
            if not data:
                break
            img_hash.update(data)

        return img_hash.hexdigest()

    def resize(self, height=None, width=None):
        if height and not width:
            width = height
        if width and not height:
            height = width
        if not height and not width:
            raise Exception('When resizing an image, at least one dimension must be set.')
        
        self.img.thumbnail((height, width), Image.Resampling.LANCZOS)
        self.height = height
        self.width = width
        buf = BytesIO()
        self.img.save(buf, format='JPEG')
        self.hash = Cover.hash_image(buf)
        self.img_str = buf.getvalue()

        if self.filename:
            self.img.save(self.filename)

    def write_to_file(self, dir, fname):
        if not isinstance(dir, (Path)):
            dir = Path(dir)
        if not dir.exists():
            raise Exception(f'Unable to save to non-existing directory: {dir.resolve()}')
        
        file = dir / (fname + self.suffix)
        self.img.save(file, format=self.img.format)
        
        if not self.filename:
            self.filename = file
        
        return file
    
    def copy_to_folder(self, dir, filename=None):
        if not isinstance(dir, (Path)):
            dir = Path(dir)
        if not dir.exists():
            raise Exception(f'Unable to save to non-existing directory: {dir.resolve()}')
        if filename is None:
            filename = self.filename.name
        else:
            filename = filename + self.filename.suffix
        
        new_file = dir / filename
        sh_copy(self.filename, new_file)
        
    def move(self, new_path):
        old_filename = self.filename
        if not isinstance(new_path, Path):
            new_path = Path(new_path)
        if new_path.is_dir():
            new_path = new_path / old_filename.name
        old_filename.rename(new_path)
        self.filename = new_path
        return self.filename

    def delete(self):
        self.filename.unlink()
        self.file_type = 'temp'

    # returns:
    #           -1: Width or Height too small
    #            0: Width and Height between bounds
    #            1: Width or Height too large
    def check_size(self, min_size=0, max_size=4000):
        if self.width < min_size or \
            self.height < min_size:
            return -1
        elif self.width > max_size or \
            self.height > max_size:
            return 1
        else:
            return 0

class Track(object):
    def __init__(self, fname):
        raise NotImplementedError("Track is not implemented. Use one of the child classes.")

    def __getitem__(self, key):
        data = None
        if key not in SUPPORTED_E_TAGS:
            raise NotImplementedError(f"{key} is an unknown tag.")
        tag = self.tag_map[key]
        if tag.type in (TTYPE.SINGLE, TTYPE.MULTI):
            raw_data = self.file.get(tag.name, None)
            if raw_data:
                # A couple tags aren't iterable and need to be put into a list first.
                if not hasattr(raw_data, '__iter__'):
                    raw_data = [str(raw_data)]
                data = [self.__tagValToString(v) for v in raw_data]
                if tag.type == TTYPE.SINGLE:
                    data = data[0]
        elif tag.type == TTYPE.SPLIT:
            raw_data = self.file.get(tag.name, None)
            if raw_data:
                vals = self.split_tag(raw_data)
                if len(vals) > tag.position:
                    data = vals[tag.position]
        elif tag.type == TTYPE.OTHER:
            data = self.otherGetter(tag)
        return data

    def get(self, key, default=None):
        retval = default
        if key in SUPPORTED_E_TAGS:
            val = self[key]
            if val:
                retval = val  
        return retval

    def otherGetter(self, tag):
        raise NotImplementedError()

    def __setitem__(self, key, value=''):
        if key not in SUPPORTED_E_TAGS:
            raise NotImplementedError(f"{key} is an unknown tag.")
        tag = self.tag_map[key]

        if type(value) in (str, list):
            pass
        elif isinstance(value, (int, float, complex)):
            value = str(value)
        elif type(value) in (tuple, set, frozenset):
            value = list(value)
        elif value is None:
            value = ''
        else:
            raise TypeError(f'{type(value)} ({value}) cannot be added to a tag')
        
        self.set_tag(tag, value)

    def __str__(self):
        artist = self['artist']
        track = self['title']
        album = self['album']
        return f'{artist} - {track} ({album})'

    def __format__(self, spec):
        str_format = str(self)
        if spec.isdigit():
            spec = int(spec)
            str_format = str(self)
            str_format = str_format[:spec]
        return str_format
    
    @property
    def length(self):
        return round(self.file.info.length, 2)
    
    @property
    def filename(self):
        return Path(self.file.filename)

    def add_lyrics(self, lyrics, **kwargs):
        pass

    def remove_lyrics(self):
        self.remove_tag('unsyncedlyrics')

    @staticmethod
    # Sometimes, values are encoded byte strings and need to be decoded to be returned.
    def __tagValToString(v):
        if isinstance(v, (bytes, bytearray)):
            v = v.decode()
        else:
            v = str(v)
        return v

    @staticmethod
    def get_track_object(file_type):
        cls = None
        if file_type == 'mp3':
            cls = MP3_Track
        elif file_type == 'flac':
            cls = FLAC_Track
        elif file_type == 'wav':
            cls = WAV_Track
        elif file_type in ('mp4', 'm4a'):
            cls = M4A_Track
        if cls:
            return cls
        return None

    @staticmethod
    def conversion_args_help(file_type):
        cls = Track.get_track_object(file_type)
        if cls:
            return cls.conversion_args_help()
        return ""

    @staticmethod
    def parse_conversion_args(given_args=[]):
        parsed_args = []
        if isinstance(given_args, str):
            parsed_args = given_args.split(' ')
        elif isinstance(given_args, list):
            parsed_args = [p for x in given_args for p in x.split(' ')]
        return parsed_args
    
    @staticmethod
    def file_args_help(file_type):
        cls = Track.get_track_object(file_type)
        if cls:
            return cls.file_args_help()
        return ""

    @staticmethod
    def parse_file_args(new_file_type, given_args=[]):
        cls = Track.get_track_object(new_file_type)
        if cls:
            return cls.parse_file_args(given_args)
        return False
    
    @staticmethod
    def open(fname):
        if type(fname) == str:
            fname = Path(fname)

        cls = Track.get_track_object(fname.suffix[1:].lower())
        if cls:
            return cls(fname)
        raise Exception(f'Files of type {fname.suffix.lower()} are not supported.')

    def convert(self, to_file_type, 
                conversion_args={}, 
                file_args={}, 
                delete_after_convert=False):
        if self.compression != COMPRESSION_TYPE.LOSSLESS:
            raise Exception('Transcoding from a lossy format is not supported.')
        from_file_path = self.filename
        from_file_str = str(from_file_path)

        to_file_path = from_file_path.parent / f'{from_file_path.stem}.{to_file_type}'
        to_file_str = str(to_file_path)

        ffmpeg_args = [
            'ffmpeg',
            '-i', from_file_str
        ] + conversion_args + [
            to_file_str
        ]
        subprocess.run(ffmpeg_args)

        from_file = Track.open(from_file_path)
        to_file = Track.open(to_file_path)

        to_file.copy_tags(from_file)
        to_file.handle_file_args(file_args)
        to_file.save()

        if delete_after_convert:
            from_file.delete()

    def copy_tags(self, from_file, overwrite=True):
        if overwrite:
            self.clear_tags()
        for tag in [t for t in E_TAGS if from_file[t]]:
            self[tag] = from_file[tag]

        if from_file.has_cover:
            self.add_cover(from_file.cover_image)

    def tags_to_str(self, str_fmat):
        str_formatted = str_fmat
        for tag_format in re.finditer(Tag.re_tag, str_fmat):
            full_tag = tag_format[0]
            tag_format = tag_format[1]
            tag_splits = re.split(Tag.re_format, tag_format)
            new_val = None
            tag_name = tag_splits[0]
            pad_len = 0
            pad_val = ' '
            pad_side = 'l'
            try:
                if len(tag_splits) == 3 and tag_splits[1] == ':':
                    pad_len = int(tag_splits[2])
                if len(tag_splits) == 4 and tag_splits[1] == ':' and tag_splits[3] in ('<', '>'):
                    pad_len = int(tag_splits[2])
                    pad_side = 'r' if tag_splits[3] == '>' else 'l'
                if len(tag_splits) == 5 and tag_splits[1] == ':' and tag_splits[3] in ('<', '>'):
                    pad_val = tag_splits[2]
                    pad_side = 'r' if tag_splits[3] == '>' else 'l'
                    pad_len = int(tag_splits[4])
            except ValueError:
                pass
            if pad_side == 'l':
                new_val = self[tag_name].ljust(pad_len, pad_val)
            else:
                new_val = self[tag_name].rjust(pad_len, pad_val)
            str_formatted = str_formatted.replace(full_tag, new_val)
        return str_formatted
            
    # Stub to be implemented by child classes if necessary
    def clear_tags(self):
        pass

    def remove_tag(self, key):
        if key not in SUPPORTED_E_TAGS:
            raise NotImplementedError(f"{key} is an unknown tag.")
        self[key] = None

    # Stub to be implemented by child classes if necessary
    def handle_file_args(self, *args):
        pass

    # Stub to be implemented by child classes
    def add_cover(self, cover):
        pass

    # Stub to be implemented by child classes if necessary
    def remove_cover(self):
        pass

    def save(self):
        self.file.save()

    def delete(self):
        self.filename.unlink()

class MP3_Track(Track):
    compression = COMPRESSION_TYPE.LOSSY
    id3_versions = {
        'v3': (2, 3, 0),
        'v4': (2, 4, 0)
    }
    conversion_arg_aliases = {
        '+b': 'b:a', 
        '+bitrate': 'b:a',
        '+q': 'q:a', 
        '+quality': 'q:a',
        '+c': 'compression_level:a', 
        '+compression_level': 'compression_level:a',
        '+l': 'cutoff:a', 
        '+cutoff': 'cutoff:a',
        '+r': 'reservoir:a', 
        '+reservoir': 'reservoir:a',
        '+s': 'joint_stereo:a', 
        '+joint_stereo': 'joint_stereo:a',
        '+a': 'abr:a', 
        '+abr': 'abr:a',
        '+y': 'copyright:a', 
        '+copyright': 'copyright:a',
        '+o': 'original:a', 
        '+original': 'original:a'
    }
    file_arg_aliases = {
        '+i': 'id3v2_version',
        '+id3v2': 'id3v2_version'
    }
    class MP3_Tag(Tag):
        def __init__(self, e_tag, id3_frame, tag_type, desc, splitter=':', **other_params):
            super().__init__(e_tag, id3_frame, tag_type)
            self.desc = desc
            self.splitter = splitter
            if 'splitwith' in other_params:
                self.splitwith = other_params['splitwith']
            if 'position' in other_params:
                self.position = other_params['position']

        @property
        def name(self):
            name = self.tag_name
            if self.desc:
                name += f'{self.splitter}{self.desc}'
            return name
        
        @property
        def func(self):
            if self.tag_name in globals():
                return globals()[self.tag_name]
        
    tag_map = {
        E_TAGS.ALBUM: MP3_Tag(E_TAGS.ALBUM, 'TALB', TTYPE.SINGLE, None),
        E_TAGS.ALBUMARTIST: MP3_Tag(E_TAGS.ALBUMARTIST, 'TPE2', TTYPE.SINGLE, None),
        E_TAGS.ALBUMARTISTS: MP3_Tag(E_TAGS.ALBUMARTISTS, 'TXXX', TTYPE.MULTI, 'ALBUMARTISTS'),
        E_TAGS.ARTIST: MP3_Tag(E_TAGS.ARTIST, 'TPE1', TTYPE.SINGLE, None),
        E_TAGS.ARTISTS: MP3_Tag(E_TAGS.ARTISTS, 'TXXX', TTYPE.MULTI, 'ARTISTS'),
        E_TAGS.BARCODE: MP3_Tag(E_TAGS.BARCODE, 'TXXX', TTYPE.SINGLE, 'BARCODE'),
        E_TAGS.CATALOGNUMBER: MP3_Tag(E_TAGS.CATALOGNUMBER, 'TXXX', TTYPE.SINGLE, 'CATALOGNUMBER'),
        E_TAGS.COPYRIGHT: MP3_Tag(E_TAGS.COPYRIGHT, 'TCOP', TTYPE.SINGLE, None),
        E_TAGS.DATE: MP3_Tag(E_TAGS.DATE, 'TDRC', TTYPE.SINGLE, None),
        E_TAGS.DISCNUMBER: MP3_Tag(E_TAGS.DISCNUMBER, 'TPOS', TTYPE.SPLIT, None, splitwith=E_TAGS.DISCTOTAL, position=0),
        E_TAGS.DISCTOTAL: MP3_Tag(E_TAGS.DISCTOTAL, 'TPOS', TTYPE.SPLIT, None, splitwith=E_TAGS.DISCNUMBER, position=1),
        E_TAGS.GENRE: MP3_Tag(E_TAGS.GENRE, 'TCON', TTYPE.SINGLE, None),
        E_TAGS.ISRC: MP3_Tag(E_TAGS.ISRC, 'TSRC', TTYPE.MULTI, None),
        E_TAGS.LABEL: MP3_Tag(E_TAGS.LABEL, 'TPUB', TTYPE.MULTI, None),
        E_TAGS.LANGUAGE: MP3_Tag(E_TAGS.LANGUAGE, 'TLAN', TTYPE.SINGLE, None),
        E_TAGS.LYRICS: MP3_Tag(E_TAGS.LYRICS, 'USLT', TTYPE.OTHER, DEFAULT_LYRICS_LANG, splitter='::'),
        E_TAGS.MEDIA: MP3_Tag(E_TAGS.MEDIA, 'TMED', TTYPE.SINGLE, None),
        E_TAGS.MB_ALBUMARTISTID: MP3_Tag(E_TAGS.MB_ALBUMARTISTID, 'TXXX', TTYPE.MULTI, 'MusicBrainz Album Artist Id'),
        E_TAGS.MB_ALBUMID: MP3_Tag(E_TAGS.MB_ALBUMID, 'TXXX', TTYPE.SINGLE, 'MusicBrainz Album Id'),
        E_TAGS.MB_ARTISTID: MP3_Tag(E_TAGS.MB_ARTISTID, 'TXXX', TTYPE.MULTI, 'MusicBrainz Artist Id'),
        E_TAGS.MB_RELEASEGROUPID: MP3_Tag(E_TAGS.MB_RELEASEGROUPID, 'TXXX', TTYPE.SINGLE, 'MusicBrainz Release Group Id'),
        E_TAGS.MB_RELEASETRACKID: MP3_Tag(E_TAGS.MB_RELEASETRACKID, 'TXXX', TTYPE.SINGLE, 'MusicBrainz Release Track Id'),
        E_TAGS.MB_TRACKID: MP3_Tag(E_TAGS.MB_TRACKID, 'TXXX', TTYPE.SINGLE, 'MusicBrainz Track Id'),
        E_TAGS.MB_WORKID: MP3_Tag(E_TAGS.MB_WORKID, 'TXXX', TTYPE.MULTI, None),
        E_TAGS.ORIGINALDATE: MP3_Tag(E_TAGS.ORIGINALDATE, 'TDOR', TTYPE.SINGLE, None),
        E_TAGS.ORIGINALYEAR: MP3_Tag(E_TAGS.ORIGINALYEAR, 'TXXX', TTYPE.SINGLE, 'originalyear'),
        E_TAGS.RELEASECOUNTRY: MP3_Tag(E_TAGS.RELEASECOUNTRY, 'TXXX', TTYPE.SINGLE, 'MusicBrainz Album Release Country'),
        E_TAGS.RELEASESTATUS: MP3_Tag(E_TAGS.RELEASESTATUS, 'TXXX', TTYPE.SINGLE, 'MusicBrainz Album Status'),
        E_TAGS.RELEASETYPE: MP3_Tag(E_TAGS.RELEASETYPE, 'TXXX', TTYPE.MULTI, 'MusicBrainz Album Type'),
        E_TAGS.SCRIPT: MP3_Tag(E_TAGS.SCRIPT, 'TXXX', TTYPE.SINGLE, 'SCRIPT'),
        E_TAGS.TITLE: MP3_Tag(E_TAGS.TITLE, 'TIT2', TTYPE.SINGLE, None),
        E_TAGS.TOTALDISCS: MP3_Tag(E_TAGS.TOTALDISCS, 'TPOS', TTYPE.SPLIT, None, splitwith=E_TAGS.DISCNUMBER, position=1),
        E_TAGS.TOTALTRACKS: MP3_Tag(E_TAGS.TOTALTRACKS, 'TRCK', TTYPE.SPLIT, None, splitwith=E_TAGS.TRACKNUMBER, position=1),
        E_TAGS.TRACKNUMBER: MP3_Tag(E_TAGS.TRACKNUMBER, 'TRCK', TTYPE.SPLIT, None, splitwith=E_TAGS.TRACKTOTAL, position=0),
        E_TAGS.TRACKTOTAL: MP3_Tag(E_TAGS.TRACKTOTAL, 'TRCK', TTYPE.SPLIT, None, splitwith=E_TAGS.TRACKNUMBER, position=1),
        E_TAGS.WORK: MP3_Tag(E_TAGS.WORK, 'TIT1', TTYPE.MULTI, None)
    }

    def __init__(self, fname):
        self.file = ID3(fname)
        self.mp3_file = MP3(fname)
        self.v2_version = self.file.version[1]

    @property
    def has_cover(self):
        b_has_cover = False
        for k in self.file.keys():
            if k.startswith('APIC'):
                b_has_cover = True
                break
        return b_has_cover

    @property
    def cover_image(self):
        cover = None
        if self.has_cover:
            cover_tag = ''
            for k in self.file.keys():
                if k.startswith('APIC:'):
                    cover_tag = k
                    break
            cover = Cover(img_str=self.file[cover_tag].data)
        return cover

    @property
    def length(self):
        return round(self.mp3_file.info.length, 2)

    def otherGetter(self, tag):
        # Unsynced lyrics
        tag_val = None
        if tag.name[:4] == 'USLT':
            lyric_tag = next((x for x in self.file.keys() if x.startswith('USLT')), None)
            if lyric_tag:
                tag_val = self.file[lyric_tag].text
        return tag_val

    def set_tag(self, tag, value):
        new_tag = None
        del_old = True
        
        if tag.type in (TTYPE.SINGLE, TTYPE.MULTI):
            new_tag = tag.func(text=value, encoding=Encoding.UTF8, desc=tag.desc)
        elif tag.type == TTYPE.SPLIT:
            split_val = self[tag.splitwith]
            if split_val is not None:
                if tag.position == 0:
                    new_val = f'{value}/{split_val}'
                else:
                    new_val = f'{split_val}/{value}'
            else:
                new_val = str(value)
            new_tag = tag.func(text=new_val, encoding=Encoding.UTF8, desc=tag.desc)
        # Any of type OTHER here as they'd need to be done on a case-by-case basis
        elif tag.e_tag == E_TAGS.LYRICS:
            del_old = False
            lang = self[E_TAGS.LANGUAGE] or DEFAULT_LYRICS_LANG
            self.add_lyrics(value, lang)
            new_tag = USLT(text=value, encoding=Encoding.UTF8, lang='eng')

        if del_old:
            self.file.delall(tag.name)
        if new_tag:
            self.file.add(new_tag)

    def split_tag(self, raw_data):
        vals = str(raw_data).split('/')
        return vals

    def add_lyrics(self, lyrics, lang=DEFAULT_LYRICS_LANG):
        if type(lyrics) == list:
            lyrics = '\n'.join(lyrics)
        new_tag = USLT(text=lyrics, encoding=Encoding.UTF8, lang=lang.upper(), desc='')
        self.file.delall(f'USLT::{lang.upper()}')
        self.file.add(new_tag)

    def add_cover(self, cover):
        if self.has_cover:
            self.remove_cover()

        img_tag = APIC(encoding=Encoding.UTF8, mime=cover.mime,
                        type=PictureType.COVER_FRONT, desc='', 
                        data=cover.img_str)
        self.file.add(img_tag)

    def remove_cover(self):
        if self.has_cover:
            self.file.delall('APIC')

    def clear_tags(self):
        keys = deepcopy([k for k in self.file.keys()])
        for k in keys:
            self.file.delall(k)

    def remove_tag(self, key):
        if key not in SUPPORTED_E_TAGS:
            raise NotImplementedError(f"{key} is an unknown tag.")
        tag = self.tag_map[key]
        tag_name = tag.name[:4]
        self.file.delall(tag_name)

    def handle_file_args(self, file_args):
        if file_args.get('id3v2_version', self.v2_version) != self.v2_version:
            self.v2_version = file_args['id3v2_version']
            if self.v2_version == 3:
                self.file.update_to_v23()
            else:
                self.file.update_to_v24()

    def save(self):
        self.file.save(v2_version=self.v2_version)

    @staticmethod
    def conversion_args_help():
        default_args = utils.get_configs('convert', 'parameters', 'mp3')
        help = f'''    Conversion Options:
        Parameters to pass to ffmpeg to specify more conversion options, such as the codec and bitrate. Defaults: {default_args}
        +b, +bitrate - Set bitrate expressed in bits/s for CBR or ABR. LAME bitrate is expressed in kilobits/s. (8-320, larger sounds better)
        +q, +quality - Set constant quality setting for VBR. This option is valid only using the ffmpeg command-line tool. For library interface users, use global_quality. (0-9, smaller sounds better)
        +c, +compression_level - Set algorithm quality. Valid arguments are integers in the 0-9 range, with 0 meaning highest quality but slowest, and 9 meaning fastest while producing the worst quality.
        +l, +cutoff - Set lowpass cutoff frequency. If unspecified, the encoder dynamically adjusts the cutoff. ([0.001..50]kHz or [50..50000]Hz)
        +r, +reservoir - Enable use of bit reservoir when set to 1. Default value is 1. LAME has this enabled by default, but can be overridden by use --nores option. (0 or 1)
        +s, +joint_stereo - Enable the encoder to use (on a frame by frame basis) either L/R stereo or mid/side stereo. Default value is 1. (0 or 1)
        +a, +abr - Enable the encoder to use ABR when set to 1. The lame --abr sets the target bitrate, while this options only tells FFmpeg to use ABR still relies on b to set bitrate. (0 or 1)
        +y, +copyright - Set MPEG audio copyright flag when set to 1. The default value is 0 (disabled). (0 or 1)
        +o, +original - Set MPEG audio original flag when set to 1. The default value is 1 (enabled).  (0 or 1)
            Info copied from ffmpeg docs on libmp3lame https://ffmpeg.org/ffmpeg-codecs.html#libmp3lame-1
'''
        return help
    
    @staticmethod
    def file_args_help():
        default_args = utils.get_configs('saving') | utils.get_configs('saving', 'mp3')
        help = f'''    File Save Options:
        +f, +filename        - Format to save the new filename with. Default {default_args['filename']}
        +i, +id3_version    - ID3v2 version to tag the file with. Default: {default_args['mp3']['id3v2_version']} (choices: {','.join(MP3_Track.id3_versions.keys())})
'''
        return help

    @staticmethod
    def parse_file_args(given_args=[]):
        parsed_args = {}
        if len(given_args) == 0:
            parsed_args = utils.get_configs('saving', 'mp3') | utils.get_configs('saving', 'mp3')
        else:
            k = ''
            for val in given_args:
                if val.startswith('+'):
                    k = val
                else:
                    parsed_args[k] = val
        all_aliases = file_args_aliases | MP3_Track.file_arg_aliases
        for k, v in all_aliases.items():
            if k in parsed_args:
                parsed_args[v] = parsed_args.pop(k)
        return parsed_args

class M4A_Track(Track):
    class M4A_Tag(Tag):
        def __init__(self, e_tag, id3_frame, tag_type, **other_params):
            super().__init__(e_tag, id3_frame, tag_type)
            self.freeform = False
            if 'freeform' in other_params:
                self.freeform = other_params['freeform']
            if 'splitwith' in other_params:
                self.splitwith = other_params['splitwith']
            if 'position' in other_params:
                self.position = other_params['position']
            
    tag_map = {
        E_TAGS.ALBUM: M4A_Tag(E_TAGS.ALBUM, '©alb', TTYPE.SINGLE),
        E_TAGS.ALBUMARTIST: M4A_Tag(E_TAGS.ALBUMARTIST, 'aART', TTYPE.SINGLE),
        E_TAGS.ALBUMARTISTS: M4A_Tag(E_TAGS.ALBUMARTISTS, '----:com.apple.iTunes:ALBUMARTISTS', TTYPE.MULTI, freeform=True),
        E_TAGS.ARTIST: M4A_Tag(E_TAGS.ARTIST, '©ART', TTYPE.SINGLE),
        E_TAGS.ARTISTS: M4A_Tag(E_TAGS.ARTISTS, '----:com.apple.iTunes:ARTISTS', TTYPE.MULTI, freeform=True),
        E_TAGS.BARCODE: M4A_Tag(E_TAGS.BARCODE, '----:com.apple.iTunes:BARCODE', TTYPE.SINGLE, freeform=True),
        E_TAGS.CATALOGNUMBER: M4A_Tag(E_TAGS.CATALOGNUMBER, '----:com.apple.iTunes:CATALOGNUMBER', TTYPE.SINGLE, freeform=True),
        E_TAGS.COPYRIGHT: M4A_Tag(E_TAGS.COPYRIGHT, 'cprt', TTYPE.SINGLE),
        E_TAGS.DATE: M4A_Tag(E_TAGS.DATE, '©day', TTYPE.SINGLE),
        E_TAGS.DISCNUMBER: M4A_Tag(E_TAGS.DISCNUMBER, 'disk', TTYPE.SPLIT, splitwith=E_TAGS.DISCTOTAL, position=0),
        E_TAGS.DISCTOTAL: M4A_Tag(E_TAGS.DISCTOTAL, 'disk', TTYPE.SPLIT, splitwith=E_TAGS.DISCNUMBER, position=1),
        E_TAGS.GENRE: M4A_Tag(E_TAGS.GENRE, '©gen', TTYPE.SINGLE),
        E_TAGS.ISRC: M4A_Tag(E_TAGS.ISRC, '----:com.apple.iTunes:ISRC', TTYPE.MULTI, freeform=True),
        E_TAGS.LABEL: M4A_Tag(E_TAGS.LABEL, '----:com.apple.iTunes:LABEL', TTYPE.MULTI, freeform=True),
        E_TAGS.LANGUAGE: M4A_Tag(E_TAGS.LANGUAGE, '----:com.apple.iTunes:LANGUAGE', TTYPE.SINGLE, freeform=True),
        E_TAGS.LYRICS: M4A_Tag(E_TAGS.LYRICS, '©lyr', TTYPE.SINGLE),
        E_TAGS.MEDIA: M4A_Tag(E_TAGS.MEDIA, '----:com.apple.iTunes:MEDIA', TTYPE.SINGLE, freeform=True),
        E_TAGS.MB_ALBUMARTISTID: M4A_Tag(E_TAGS.MB_ALBUMARTISTID, '----:com.apple.iTunes:MusicBrainz Album Artist Id', TTYPE.MULTI, freeform=True),
        E_TAGS.MB_ALBUMID: M4A_Tag(E_TAGS.MB_ALBUMID, '----:com.apple.iTunes:MusicBrainz Album Id', TTYPE.SINGLE, freeform=True),
        E_TAGS.MB_ARTISTID: M4A_Tag(E_TAGS.MB_ARTISTID, '----:com.apple.iTunes:MusicBrainz Artist Id', TTYPE.MULTI, freeform=True),
        E_TAGS.MB_RELEASEGROUPID: M4A_Tag(E_TAGS.MB_RELEASEGROUPID, '----:com.apple.iTunes:MusicBrainz Release Group Id', TTYPE.SINGLE, freeform=True),
        E_TAGS.MB_RELEASETRACKID: M4A_Tag(E_TAGS.MB_RELEASETRACKID, '----:com.apple.iTunes:MusicBrainz Release Track Id', TTYPE.SINGLE, freeform=True),
        E_TAGS.MB_TRACKID: M4A_Tag(E_TAGS.MB_TRACKID, '----:com.apple.iTunes:MusicBrainz Release Track Id', TTYPE.SINGLE, freeform=True),
        E_TAGS.MB_WORKID: M4A_Tag(E_TAGS.MB_WORKID, '----:com.apple.iTunes:MusicBrainz Work Id', TTYPE.MULTI, freeform=True),
        E_TAGS.ORIGINALDATE: M4A_Tag(E_TAGS.ORIGINALDATE, '----:com.apple.iTunes:originaldate', TTYPE.SINGLE, freeform=True),
        E_TAGS.ORIGINALYEAR: M4A_Tag(E_TAGS.ORIGINALYEAR, '----:com.apple.iTunes:originalyear', TTYPE.SINGLE, freeform=True),
        E_TAGS.RELEASECOUNTRY: M4A_Tag(E_TAGS.RELEASECOUNTRY, '----:com.apple.iTunes:MusicBrainz Album Release Country', TTYPE.SINGLE, freeform=True),
        E_TAGS.RELEASESTATUS: M4A_Tag(E_TAGS.RELEASESTATUS, '----:com.apple.iTunes:MusicBrainz Album Status', TTYPE.SINGLE, freeform=True),
        E_TAGS.RELEASETYPE: M4A_Tag(E_TAGS.RELEASETYPE, '----:com.apple.iTunes:MusicBrainz Album Type', TTYPE.MULTI, freeform=True),
        E_TAGS.SCRIPT: M4A_Tag(E_TAGS.SCRIPT, '----:com.apple.iTunes:SCRIPT', TTYPE.SINGLE, freeform=True),
        E_TAGS.TITLE: M4A_Tag(E_TAGS.TITLE, '©nam', TTYPE.SINGLE),
        E_TAGS.TOTALDISCS: M4A_Tag(E_TAGS.TOTALDISCS, 'disk', TTYPE.SPLIT, splitwith=E_TAGS.DISCNUMBER, position=1),
        E_TAGS.TOTALTRACKS: M4A_Tag(E_TAGS.TOTALTRACKS, 'trkn', TTYPE.SPLIT, splitwith=E_TAGS.TRACKNUMBER, position=1),
        E_TAGS.TRACKNUMBER: M4A_Tag(E_TAGS.TRACKNUMBER, 'trkn', TTYPE.SPLIT, splitwith=E_TAGS.TRACKTOTAL, position=0),
        E_TAGS.TRACKTOTAL: M4A_Tag(E_TAGS.TRACKTOTAL, 'trkn', TTYPE.SPLIT, splitwith=E_TAGS.TRACKNUMBER, position=1),
        E_TAGS.WORK: M4A_Tag(E_TAGS.WORK, '©wrk', TTYPE.MULTI)
    }

    def __init__(self, fname):
        self.file = MP4(fname)
        self.compression = COMPRESSION_TYPE.LOSSLESS
        if self.file.info.codec.startswith('mp4a'):
            self.compression = COMPRESSION_TYPE.LOSSY

    @property
    def has_cover(self):
        b_has_cover = ('covr' in self.file and len(self.file['covr']) > 0)
        return b_has_cover

    @property
    def cover_image(self):
        cover = None
        if self.has_cover:
            cover = Cover(img_str=self.file['covr'][0])
        return cover

    def set_tag(self, tag, value):
        if type(value) == str:
            value = [value]
        if tag.name not in self.file:
            self.file.update({tag.name: []})
        if tag.freeform:
            value = [MP4FreeForm(v.encode(), dataformat=AtomDataType.UTF8) for v in value]
        self.file[tag.name] = value

    def split_tag(self, raw_data):
        vals = raw_data[0]
        return vals

    def add_cover(self, cover):
        if self.has_cover:
            self.remove_cover()

        img = MP4Cover(cover.img_str, AtomDataType.JPEG)
        self.file['covr'] = [img]

    def remove_cover(self):
        if self.has_cover:
            self.file['covr'] = []

class FLAC_Track(Track):
    compression = COMPRESSION_TYPE.LOSSLESS

    tag_map = {
        E_TAGS.ALBUM: Tag(E_TAGS.ALBUM, 'album', TTYPE.SINGLE),
        E_TAGS.ALBUMARTIST: Tag(E_TAGS.ALBUMARTIST, 'albumartist', TTYPE.SINGLE),
        E_TAGS.ALBUMARTISTS: Tag(E_TAGS.ALBUMARTISTS, 'albumartists', TTYPE.MULTI),
        E_TAGS.ARTIST: Tag(E_TAGS.ARTIST, 'artist', TTYPE.SINGLE),
        E_TAGS.ARTISTS: Tag(E_TAGS.ARTISTS, 'artists', TTYPE.MULTI),
        E_TAGS.BARCODE: Tag(E_TAGS.BARCODE, 'barcode', TTYPE.SINGLE),
        E_TAGS.CATALOGNUMBER: Tag(E_TAGS.CATALOGNUMBER, 'catalognumber', TTYPE.SINGLE),
        E_TAGS.COPYRIGHT: Tag(E_TAGS.COPYRIGHT, 'copyright', TTYPE.SINGLE),
        E_TAGS.DATE: Tag(E_TAGS.DATE, 'date', TTYPE.SINGLE),
        E_TAGS.DISCNUMBER: Tag(E_TAGS.DISCNUMBER, 'discnumber', TTYPE.SINGLE),
        E_TAGS.DISCTOTAL: Tag(E_TAGS.DISCTOTAL, 'disctotal', TTYPE.SINGLE),
        E_TAGS.GENRE: Tag(E_TAGS.GENRE, 'genre', TTYPE.SINGLE),
        E_TAGS.ISRC: Tag(E_TAGS.ISRC, 'isrc', TTYPE.MULTI),
        E_TAGS.LABEL: Tag(E_TAGS.LABEL, 'label', TTYPE.MULTI),
        E_TAGS.LANGUAGE: Tag(E_TAGS.LANGUAGE, 'language', TTYPE.SINGLE),
        E_TAGS.LYRICS: Tag(E_TAGS.LYRICS, 'lyrics', TTYPE.SINGLE),
        E_TAGS.MEDIA: Tag(E_TAGS.MEDIA, 'media', TTYPE.SINGLE),
        E_TAGS.MB_ALBUMARTISTID: Tag(E_TAGS.MB_ALBUMARTISTID, 'musicbrainz_albumartistid', TTYPE.MULTI),
        E_TAGS.MB_ALBUMID: Tag(E_TAGS.MB_ALBUMID, 'musicbrainz_albumid', TTYPE.SINGLE),
        E_TAGS.MB_ARTISTID: Tag(E_TAGS.MB_ARTISTID, 'musicbrainz_artistid', TTYPE.MULTI),
        E_TAGS.MB_RELEASEGROUPID: Tag(E_TAGS.MB_RELEASEGROUPID, 'musicbrainz_releasegroupid', TTYPE.SINGLE),
        E_TAGS.MB_RELEASETRACKID: Tag(E_TAGS.MB_RELEASETRACKID, 'musicbrainz_releasetrackid', TTYPE.SINGLE),
        E_TAGS.MB_TRACKID: Tag(E_TAGS.MB_TRACKID, 'musicbrainz_trackid', TTYPE.SINGLE),
        E_TAGS.MB_WORKID: Tag(E_TAGS.MB_WORKID, 'musicbrainz_workid', TTYPE.SINGLE),
        E_TAGS.ORIGINALDATE: Tag(E_TAGS.ORIGINALDATE, 'originaldate', TTYPE.SINGLE),
        E_TAGS.ORIGINALYEAR: Tag(E_TAGS.ORIGINALYEAR, 'originalyear', TTYPE.SINGLE),
        E_TAGS.RELEASECOUNTRY: Tag(E_TAGS.RELEASECOUNTRY, 'releasecountry', TTYPE.SINGLE),
        E_TAGS.RELEASESTATUS: Tag(E_TAGS.RELEASESTATUS, 'releasestatus', TTYPE.SINGLE),
        E_TAGS.RELEASETYPE: Tag(E_TAGS.RELEASETYPE, 'releasetype', TTYPE.MULTI),
        E_TAGS.SCRIPT: Tag(E_TAGS.SCRIPT, 'script', TTYPE.SINGLE),
        E_TAGS.TITLE: Tag(E_TAGS.TITLE, 'title', TTYPE.SINGLE),
        E_TAGS.TOTALDISCS: Tag(E_TAGS.TOTALDISCS, 'totaldiscs', TTYPE.SINGLE),
        E_TAGS.TOTALTRACKS: Tag(E_TAGS.TOTALTRACKS, 'totaltracks', TTYPE.SINGLE),
        E_TAGS.TRACKNUMBER: Tag(E_TAGS.TRACKNUMBER, 'tracknumber', TTYPE.SINGLE),
        E_TAGS.TRACKTOTAL: Tag(E_TAGS.TRACKTOTAL, 'tracktotal', TTYPE.SINGLE),
        E_TAGS.WORK: Tag(E_TAGS.WORK, 'work', TTYPE.MULTI)
    }

    def __init__(self, fname):
        self.file = FLAC(fname)
        self.deleteid3 = False

    @property
    def has_cover(self):
        b_has_cover = (len(self.file.pictures) > 0)
        return b_has_cover

    @property
    def cover_image(self):
        cover = None
        if self.has_cover:
            cover = Cover(img_str=self.file.pictures[0].data)
        return cover

    def set_tag(self, tag, value):
        self.file[tag.name] = value

    def add_cover(self, cover):
        img = Picture()
        img.data = cover.img_str
        img.type = PictureType.COVER_FRONT
        img.mime = cover.mime
        img.width = cover.width
        img.height = cover.height
        self.file.pictures = [img]

    def remove_cover(self):
        self.file.pictures = []
        
    def handle_file_args(self, file_args):
        if file_args.get('deleteid3', self.deleteid3) != self.deleteid3:
            self.deleteid3 = file_args['deleteid3']
    
    def save(self):
        self.file.save(deleteid3=self.deleteid3)

class WAV_Track(MP3_Track):
    compression = COMPRESSION_TYPE.LOSSLESS
    def __init__(self, fname):
        self.file = WAVE(fname)