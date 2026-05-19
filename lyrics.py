from argparse import ArgumentParser
from utils.utils import utils, log, logging_levels
from utils.track import Track
import requests
from terminaltables import AsciiTable
from ratelimit import limits, sleep_and_retry
from datetime import timedelta

lrclib_url = 'https://lrclib.net/api'
headers = {
    'User-Agent': 'My Music Tools (https://github.com/RazorTwig/MyMusicTools)',
    'Accept': 'application/json',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br, zstd',
    'x-user-agent': 'My Music Tools (https://github.com/RazorTwig/MyMusicTools)',
    'DNT': '1',
    'Sec-GPC': '1',
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'cors',
    'Sec-Fetch-Site': 'same-origin',
    'Priority': 'u=0'
}

def direct_add_lyrics(args):
    if not args.folder:
        log.error('Direct mode must have a file name in the folder argument.')
        raise Exception('No file specified')
    if not args.id:
        log.error('Direct mode must have an id supplied.')
        raise Exception('No id specified')
    
    trk = Track.open(args.folder)
    lyrics_types = args.synced

    req_type = f'get/{args.id}'
    lyrics_json = send_request(req_type)

    lyrics = None
    for l_type in lyrics_types:
        lyric_type = f'{l_type}Lyrics'
        if lyrics_json.get(lyric_type, None):
            lyrics = lyrics_json[lyric_type]
            break
    
    if lyrics:
        select_lyrics(trk, lyrics, args)

def search_lyrics(args):
    utils.set_working_dir(args.folder)
    
    lyrics_types = args.synced
    length_diff = args.length_diff
    mode = args.mode
    lyrics_found = 0
    
    tracks = [Track.open(f) for f in utils.get_files()]
    try:
        for trk in utils.progressbar(tracks):
            log.info(f'Track: {trk} (duration: {trk.length})')

            lyrics = None
            local_lyrics_path, local_lyrics = search_local(trk)
            if local_lyrics:
                log.info(f'Found local lyric file at {local_lyrics_path}')
                log.debug(f'{local_lyrics}')
                if args.save_to_folder.lower() == 'remove':
                    log.info(f'Deleting local lyric file {local_lyrics_path} (save_to_folder={args.save_to_folder})')
                    local_lyrics_path.unlink()
                elif args.save_to_folder.lower() in ('leave', 'save') and args.overwrite:
                    local_lyrics = None

            embedded_lyrics = trk['lyrics']
            if embedded_lyrics is not None:
                log.info(f'Lyrics already embedded in file')
                log.debug(f'{embedded_lyrics}')
                if args.embed_in_file == 'remove':
                    trk.remove_lyrics()
                    trk.save()
                elif args.save_to_folder.lower() in ('leave', 'embed') and args.overwrite:
                    embedded_lyrics = None

            if local_lyrics is not None and not embedded_lyrics:
                lyrics = local_lyrics
            elif embedded_lyrics is not None and not local_lyrics:
                lyrics = embedded_lyrics
            elif local_lyrics and embedded_lyrics and local_lyrics != embedded_lyrics:
                choice = input('Conflicting lyrics found in both a local file and embedded within the file. \
                               \nShould either the [L]ocal or [E]mbedded lyrics be used, or do you want to [S]earch for new ones? ')
                log.info(f'Lyrics found in both a local file and embedded. User chose: {choice}')
                if choice.lower() == 'l':
                    lyrics = local_lyrics
                elif choice.lower() == 'e':
                    lyrics = embedded_lyrics
                else:
                    lyrics = None
            
            if lyrics is None:
                lyrics_json = search_lrclib(trk)
                if len(lyrics_json):
                    if mode == 'auto':
                        lyrics = auto_search_lyrics(trk, lyrics_json, lyrics_types, length_diff)
                    else:
                        lyrics = manual_search_lyrics(trk, lyrics_json, lyrics_types)

            if lyrics:
                log.info('Lyrics selected')
                log.debug(lyrics)

                lyrics_found += 1
                select_lyrics(trk, lyrics, args, local_lyrics_path)
            else:
                log.info('No lyrics selected')
                if args.insert_empty:
                    save_lang = args.lang
                    args.lang = 'XXX'
                    select_lyrics(trk, '', args, local_lyrics_path)
                    args.lang = save_lang
    except Exception as e:
        log.error(e)
        raise e
    log.info(f'Lyrics found for {lyrics_found} of {len(tracks)} tracks.')

def auto_search_lyrics(trk, lyrics_json, lyrics_types=[], length_diff=0):
    def log_possible_result(possible_result):
        if log_lyrics:
            log.debug(f'\tid: {possible_result["id"]}')
            log.debug(f'\ttrackName: {possible_result["trackName"]}')
            log.debug(f'\tartistName: {possible_result["artistName"]}')
            log.debug(f'\talbumName: {possible_result["albumName"]}')
            log.debug(f'\tduration: {possible_result["duration"]}')
            log.debug(f'\tlyric_type exists: {"yes" if possible_result.get(lyric_type, None) else "no"}')

    lyrics = None
    trk_len_min = trk.length - length_diff
    trk_len_max = trk.length + length_diff
    log.info(f'Number of results: {len(lyrics_json)}')
    log_lyrics = True
    for l_type in lyrics_types:
        lyric_type = f'{l_type}Lyrics'
        for possible_lyrics in lyrics_json:
            log_possible_result(possible_lyrics)
            if possible_lyrics.get(lyric_type, None) and \
                possible_lyrics['trackName'].lower() == trk['title'].lower() and \
                possible_lyrics['artistName'].lower() == trk['artist'].lower() and \
                possible_lyrics['albumName'].lower() == trk['album'].lower() and \
                trk_len_min <= possible_lyrics['duration'] <= trk_len_max:
                lyrics = possible_lyrics[lyric_type]
                break
        if lyrics:
            break
        log_lyrics = False # Only want to log the first time through.
    return lyrics

def manual_search_lyrics(trk, lyrics_json, lyrics_types=[]):
    def shorten_lyrics(lyrics, lines=3):
        shorter_lyrics = ''
        if lyrics:
            groups = lyrics.split('\n')
            shorter_lyrics = f'{"\n".join(groups[:lines])}\n...(+{len(groups)-lines} more lines)'
        return shorter_lyrics
    def select(choices, choice_types):
        if not len(choice_types):
            return ''
        elif len(choice_types) == 1 and choices[f'{choice_types[0]}Lyrics']:
            return choices[f'{choice_types[0]}Lyrics']
        elif len(choice_types) == 1:
            return ''
        else:
            possibilities = [choices[f'{l}Lyrics'] for l in choice_types if choices[f'{l}Lyrics']]
            return possibilities[0] if len(possibilities) else ''
    table_data = [['#', 'id', 'artist', 'track', 'album', 'duration', 'synced lyrics', 'plain lyrics', 'instrumental?']]
    max_show = 5
    lyrics = None
    for i, lyric in enumerate(lyrics_json[:max_show]):
        table_data.append([i+1, lyric['id'], lyric['artistName'], lyric['trackName'], lyric['albumName'], 
                            lyric['duration'], shorten_lyrics(lyric.get('syncedLyrics', '')), 
                            shorten_lyrics(lyric.get('plainLyrics', '')), lyric['instrumental']])
    table = AsciiTable(table_data)
    print(f'Track: {trk} (duration: {trk.length}):')
    print(table.table)
    choice = input('Enter the [#] of the lyrics you want to attach (or CANCEL): ')
    if choice.isdigit() and 0 < int(choice) <= max_show:
        choice = int(choice)-1
        selected_choice = lyrics_json[choice]
        if selected_choice['instrumental']:
            lyrics = ""
        else:
            lyrics = select(selected_choice, lyrics_types)
    return lyrics

def search_local(trk):
    lyrics = None
    lrc_path = trk.filename.parent / (trk.filename.name + '.lrc')
    if lrc_path.exists():
        with open(lrc_path, 'r', encoding='UTF-8') as lrc_file:
            lyrics = '\n'.join(lrc_file.readlines())
    return (lrc_path, lyrics)

def search_lrclib(trk):
    params = setup_search_params(trk)
    lyrics_json = send_request('search', params)
    log.debug(f'params: {params}')
    log.debug(f'Number of results: {len(lyrics_json)}')
    return lyrics_json

def setup_search_params(trk):
    track_name = trk['title']
    artist_name = trk.get('artists', [trk['artist']])[0]
    album_name = trk['album']
    params = {
        'q': f'{track_name} {artist_name} {album_name}'
    }
    return params

@sleep_and_retry
@limits(calls=1, period=timedelta(seconds=5).total_seconds())
def send_request(req_type, params=None):
    req_url = f'{lrclib_url}/{req_type}'
    resp = requests.get(req_url, params, headers=headers)
    if resp.status_code == 200 and resp.headers['Content-Type'] == 'application/json':
        lyrics_json = resp.json()
    else:
        log.error('Invalid response from LRCLIB:')
        log.error(f'status code: {resp.status_code}')
        log.error(f'content-type: {resp.headers["Content-Type"]}')
        raise Exception()
    return lyrics_json

def select_lyrics(trk, lyrics, args, local_lyrics_path=None):
    if args.embed_in_file == 'embed' or \
        (args.embed_in_file == 'leave' and \
            trk['lyrics'] and \
            args.overwrite):
        log.info(f'Attaching {"" if len(lyrics) else "empty"} lyrics to file.')
        trk.add_lyrics(lyrics, lang=args.lang.upper())
        trk.save()

    if args.save_to_folder == 'save' or \
        (args.save_to_folder == 'leave' and \
            local_lyrics_path is not None and \
            local_lyrics_path.exists() is not None and \
            args.overwrite):
        save_lrc_file(trk, lyrics)

def save_lrc_file(trk, lyrics):
    lrc_filename = trk.filename.parent / (trk.filename.stem + '.lrc')
    log.info(f'Saving lyrics to {str(lrc_filename.resolve())}.')
    with open(lrc_filename, 'w', encoding='UTF-8') as lyric_file:
        lyric_file.write(lyrics)

def setup_args():
    parser = ArgumentParser()
    parser.add_argument('-f', '--folder')
    parser.add_argument('-m', '--mode', choices=['auto', 'direct', 'manual'], default=utils.get_default_args(str, 'lyrics', 'mode'))
    parser.add_argument('-y', '--synced', nargs='+', choices=['synced', 'plain'], default=utils.get_default_args(list, 'lyrics', 'synced_or_plain'))
    parser.add_argument('-l', '--length-diff', type=float, default=utils.get_default_args(float, 'lyrics', 'length_diff'))
    parser.add_argument('-e', '--embed-in-file', type=str, default=utils.get_default_args(str, 'lyrics', 'embed_in_file'))
    parser.add_argument('-s', '--save-to-folder', type=str, default=utils.get_default_args(str, 'lyrics', 'save_to_folder'))
    parser.add_argument('-o', '--overwrite', action='store_true')
    parser.add_argument('-i', '--id')
    parser.add_argument('--lang', default=utils.get_default_args(str, 'lyrics', 'lang'))
    parser.add_argument('--insert-empty', type=int, default=utils.get_default_args(int, 'lyrics', 'insert_empty'))
    parser.add_argument('--logging-level', choices=[l for l in logging_levels.keys()], default=utils.get_default_args(str, 'logging', 'level'))
    return parser

def run(args):
    utils.start_log('lyrics.log', level=args.logging_level)
    log.debug(args)
    if args.mode == 'direct':
        direct_add_lyrics(args)
    else:
        search_lyrics(args)

if __name__ == '__main__':
    parser = setup_args()
    args = parser.parse_args()
    # print(args)
    run(args)
