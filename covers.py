from argparse import ArgumentParser
import subprocess
from utils.utils import utils, log, logging_levels
from utils.track import Track, Cover
from pathlib import Path


class Cover_Cache(object):
    class cck(object):
        def __init__(self, trk):
            self.artist = trk['artist']
            self.album = trk['album']
            self.date = trk['date']
        def __hash__(self):
            return hash((self.artist, self.album, self.date))
        def __eq__(self, other):
            return isinstance(other, Cover_Cache.cck) and hash(self) == hash(other)

    def __init__(self):
        self.dir = Path().cwd() / 'cover_cache'
        self.cache = {}

    def search(self, trk):
        key = Cover_Cache.cck(trk)
        file = None
        if key in self.cache:
            file = Cover(fname=self.cache[key])
        return file

    def add_cover(self, trk, cover):
        key = Cover_Cache.cck(trk)
        filename = cover.write_to_file(self.dir, str(hash(key)))
        self.cache[key] = filename

    def delete_temp_files(self):
        for file in self.dir.glob('*'):
            file.unlink()

    def get_cache_dir(self):
        return self.dir

    @staticmethod
    def get_file_stem(trk):
        key = Cover_Cache.cck(trk)
        return hash(key)

cover_cache = Cover_Cache()

def get_covers(args):
    def get_from_cache(trk):
        nonlocal cover
        cover = cover_cache.search(trk)
        return cover

    def search_existing(trk, args):
        nonlocal cover
        cover = search_for_existing_covers(trk, args)
        return cover

    utils.set_working_dir(args.folder)

    tracks = [Track.open(f) for f in utils.get_files()]
    for trk in utils.progressbar(tracks):
        cover = None
        save_to_folder = args.save_to_folder
        save_to_cache = True
        if get_from_cache(trk):
            # If it's in the cache, it should already be in the corresponding folder thanks to another file.
            save_to_folder = False
            save_to_cache = False
        # search_existing is a function can will set the "cover" variable if it finds something
        elif not search_existing(trk, args):
            cover = covit_search(trk, args)
        if cover:
            size_check = cover.check_size(args.min_size, args.max_size)
            if args.resize == 'min' and size_check >= 0:
                cover.resize(args.min_size)
            elif args.resize == 'max' and size_check == 1:
                cover.resize(args.max_size)

            if args.embed_in_file == 'embed':
                trk.add_cover(cover)
                trk.save()
            elif args.embed_in_file == 'remove' and trk.cover_image is not None:
                trk.remove_cover()
                trk.save()
            
            if save_to_folder == 'save':
                if cover.filename and cover.filename.parent != trk.filename.parent:
                    # Not in the same folder
                    cover.copy_to_folder(trk.filename.parent, args.cover_name)
                elif cover.filename and cover.filename.stem != args.cover_name:
                    # In the same folder, wrong name
                    new_path = trk.filename.parent / (args.cover_name + cover.filename.suffix)
                    cover.move(new_path)
                elif not cover.filename:
                    # Was embedded in a track file
                    cover.write_to_file(trk.filename.parent, args.cover_name)

            if save_to_cache:
                # Wait to save to cache until after it's been resized and such
                cover_cache.add_cover(trk, cover)

    cover_cache.delete_temp_files()
            

def search_for_existing_covers(trk, args):
    cover = None
    embedded_cover = trk.cover_image
    separate_file_covers = search_for_cover_files(trk, args)
    if embedded_cover in separate_file_covers:
        for file_cover in separate_file_covers:
            if embedded_cover == file_cover:
                file_cover.merge(embedded_cover)
    elif embedded_cover is not None:
        separate_file_covers.append(embedded_cover)
    # We have other covers that already exist. Allow for any that are the same as the min size or larger as they can be resized back down.
    possible_covers = [cov for cov in separate_file_covers if cov.check_size(args.min_size) >= 0]
    if len(possible_covers) == 1:
        cover = possible_covers[0]
    elif len(possible_covers) > 1:
        print(f'Found multiple possible covers for the album {trk["album"]} by {trk["albumartist"]}.\n')
        for i, cov in enumerate(possible_covers):
            print(f'{i+1} | {cov}')
        choice = input(f'Should any of these be used? (1{"-" + str(len(possible_covers)) if len(possible_covers) > 1 else ""} or "N") ')
        if choice.isdigit() and 0 < int(choice) <= len(possible_covers):
            choice = int(choice)-1
            cover = possible_covers[choice]
    return cover

def search_for_cover_files(trk, args):
    covers = []
    fldr = trk.filename.parent
    for cover_file in fldr.glob(f'{args.cover_name}*'):
        covers.append(Cover(fname=cover_file))
    return covers

def covit_search(trk, args):
    cover = None
    covit_args = get_covit_args(trk, args)
    ret_val = subprocess.run(covit_args, capture_output=True, text=True)
    if ret_val.returncode == 0:
        ret_vals = ret_val.stdout.split('\n')
        needle = 'Saved: '
        cover_path = next((x for x in ret_vals if x.startswith(needle)), None)
        if cover_path:
            cover_path = Path(cover_path.replace(needle, ""))
            if cover_path.exists():
                cover = Cover(fname=cover_path)
    return cover

def get_covit_args(trk, args):
    output_file = cover_cache.get_cache_dir() / str(cover_cache.get_file_stem(trk))
    covit_args = ['external_tools/covit-windows-amd64.exe',
                '--address','covers.musichoarders.xyz',
                '--catch',
                '--input', trk.filename,
                '--primary-output', str(output_file.resolve()),
                '--primary-overwrite',
                '--query-resolution', str(args.min_size),
                '--query-sources', 'bandcamp,amazonmusic,applemusic,discogs,spotify,musicbrainz']
    return covit_args

def setup_args():
    parser = ArgumentParser()
    parser.add_argument('-f', '--folder')
    parser.add_argument('-x', '--max-size', type=int, default=utils.get_default_args(int, 'covers', 'max_size'))
    parser.add_argument('-n', '--min-size', type=int, default=utils.get_default_args(int, 'covers', 'min_size'))
    parser.add_argument('-r', '--resize', type=str, default=utils.get_default_args(str, 'covers', 'resize'))
    parser.add_argument('-e', '--embed-in-file', type=str, default=utils.get_default_args(str, 'covers', 'embed_in_file'))
    parser.add_argument('-s', '--save-to-folder', type=str, default=utils.get_default_args(str, 'covers', 'save_to_folder'))
    parser.add_argument('-l', '--cover-name', type=str, default=utils.get_default_args(str, 'covers', 'filename'))
    parser.add_argument('--logging-level', choices=[l for l in logging_levels.keys()], default=utils.get_default_args(str, 'logging', 'level'))
    return parser

def run(args):
    utils.start_log('covers.log', level=args.logging_level)
    log.debug(args)
    get_covers(args)

if __name__ == '__main__':
    parser = setup_args()
    args = parser.parse_args()
    # print(args)
    run(args)