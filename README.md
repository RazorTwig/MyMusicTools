# My Music Tools
Literally just a set of tools I've created for my own usage for administering various aspects of my very large (and still growing) library of music. While there are other programs out there that would do each and every thing in these tools, I wanted to try and learn Python and this seemed like a good place for me to start. It's still a work in progress as I'm constantly tweaking it based on new things I find. This has been an evolving project over the last 2 or so years as I've slowly learned more and more about Python. I'm sure there's a lot I still have to learn since it's not what I use in my everyday job.

## The Tools
### Audio Converter
```
py convert.py [-h] [-f, --folder FOLDER] [-s, --source-format LIST_OF_FORMATS] [-t, --destination-format CONVERT_TO_FORMAT] [-d, --delete], [-o, --conversion-args LIST_OF_CONVERSION_ARGS] [-n, --file-args LIST_OF_FILE_ARGS] [-c, --cover-args LIST_OF_COVER_ARGS] [-a, --args-help]
```
Used for converting files in a specified library or folder from one supported file type to another. Only allows converting from lossless types (FLAC, WAV, M4A Lossless). Copies over metadata tags from the old file to the new.

Currently supported formats (sort of): FLAC, WAV, M4A, MP3

NB: Requires ffmpeg be installed and available on the user's PATH.

#### Arguments
- Any arguments used will supercede their configured values in config.toml
- -f, --folder FOLDER: A location to search (recursively) for files to convert
    - This can one of 3 strings:
        - A library name as configured in the "libraries" section of configs.toml
        - An absolute path to a folder (has not been tested with symlinks)
        - A relative path that starts with a library name and goes deeper into its file structure
            - e.g. 'library1/Gammer' if library1 is defined in configs.toml
- -s, --source-format LIST_OF_FORMATS: One or more file formats to search for to convert from
    - Default: Checks what the default destination format is on configs.toml and filters that from the list of available formats
        - Essentially, FLAC, WAV, M4A at the moment
- -t, --destination-format CONVERT_TO_FORMAT: 
    - Default: Configured by "file_type" in the "convert" section of configs.toml
- -d, --delete: 
    - Choices: 0 or 1.
        - 0: Do not delete the source file after conversion
        - 1: Delete the source file after conversion
    - Default: Configured by "delete_source" in the "convert" section of configs.toml
- -o, --conversion-args LIST_OF_CONVERSION_ARGS: 
    - Command line arguments used for converting the file that will be passed to ffmpeg. (run --args-help for more info)
        - Will need to be passed in as a single string. See configs_example.toml for an example of mp3 args.
    - Default: Defaults can be configured within sections labeled as "convert.parameters.{format}"
- -n, --file-args LIST_OF_FILE_ARGS: 
    - Arguments for what to do when saving a new file after conversion. (run --args-help for more info)
    - Default: Defaults can be configured within sections labeled as "saving.{format}"
- -a, --args-help: 
    - If specified, will print out some extra info about conversion and file arguments.
    - If a destination format is specified at the same time, it will only print out arguments related to that format.
- --logging-level: LOGGING_LEVEL
    - The program will log messages in "logs/convert.log". This controls the level of logging to be saved.
    - Choices: debug, info, warning, error, critical
    - Default: Configured by "level" in the "logging" section of configs.toml

### Lyric Finder
```
py lyrics.py [-h] [-f, --folder FOLDER] [-m, --mode MODE] [-y, --synced SYNCED_ANDOR_UNSYNCED] [-l, --length LENGTH_DIFF] [-e, --embed-in-file EMBED] [-s, --save-to-folder SAVE] [-o, --overwrite OVERWRITE] [-i, --id ID] [--lang LANG] [--insert-empty INS_EMPTY] [--logging-level LOGGING_LEVEL] 
```
Used to search LRCLIB for lyrics of songs and attach them either by saving them to the file system, embedding them in the file, or both.

#### Arguments
- Any arguments used will supercede their configured values in config.toml
- -f, --folder FOLDER: A location to search (recursively) for files to search for lyrics for
    - In auto and manual modes, this can one of 3 strings:
        - A library name as configured in the "libraries" section of configs.toml
        - An absolute path to a folder (has not been tested with symlinks)
        - A relative path that starts with a library name and goes deeper into its file structure
            - e.g. 'library1/Gammer' if library1 is defined in configs.toml
    - In direct mode, this must instead be the path to a single song
- -m, --mode: MODE
    - Choices: auto, manual, direct
        - auto: Will search LRCLIB using a track's artist, name, and album. The program will then search through the results (if any) and pick the first one that is within the time differential and that has either synced or unsynced lyrics, depending on which is first if both are in the the "synced" parameter
        - manual: Does the same search as auto, but will then output up to 5 results, displaying the LRCLIB id, artist, track name, album, synced lyrics (up to 3 lines), unsynced lyrics (up to 3 lines), and whether or not the track is set as "instrumental" within LRCLIB, allowing the user to select one of the lyrics to be saved.
        - direct: This mode will not search anything. The user is expected to give the path of a file and an ID from the LRCLIB website and the program will fetch those specific lyrics and save them to the file.
    - Default: Configured by "mode" in the "lyrics" section of configs.toml
- -y, --synced: SYNCED_ANDOR_UNSYNCED
    - Choices: 'synced' and/or 'unsynced'
    - One or both of 'synced' and 'unsynced' can be specified. If both are specified, the system will select the first one specified that exists within the results. In auto mode, this means it will search through all results looking for the first specified, then, if it doesn't find any, search through the results again for the second.
- -l, --length: LENGTH_DIFF
    - The amount of time (in seconds) to make the range of possible times in results from LRCLIB
        - e.g. a LENGTH_DIFF of 2 on a song that's 145 seconds long will allow for anything between 143 and 147
    - Default: Configured by "length_diff" in the "lyrics" section of configs.toml
- -e, --embed-in-file: EMBED
    - Controls whether or not to embed the lyrics into the track file.
        - All lyrics, synced or unsynced, are saved into the equivalent unsynced tag as that has more compatibility (at least for my uses)
    - Choices: "remove", "leave", or "embed"
        - "remove": Remove any lyrics embedded into the file.
        - "leave": If any lyrics are found embedded within the file, do nothing to it. (unless overwriting)
        - "embed": Embed the lyrics.
    - Default: Configured by "embed_in_file" in the "lyrics" section of configs.toml
- -s, --save-to-folder: SAVE
    - Controls whether or not to save the selected lyrics to a file in the same folder as the track.
    - Choices: "remove", "leave", or "save"
        - "remove": Remove any lyric file with the same name as the track file.
        - "leave": If any lyric file is found with the same name as the track file, do nothing to it. (unless overwriting)
        - "save": Save the lyrics to a lyric file with the same name as the track file.
    - Default: Configured by "save_to_folder" in the "lyrics" section of configs.toml
- -o, --overwrite:
    - When specified, if any lyrics are found attached to the track, overwrites them. 
    - If not specified and any lyrics are found, the system will not search for new ones in LRCLIB but will either save them to the folder or embed them in the file if requested and they're not already there.
- -i, --id: ID
    - LRCLIB lyric ID for use in direct mode. 
        - These IDs can be found either during a manual search (as the output will show them) or through using the network inspector in your browser when searching on LRCLIB.
- --lang: LANG
    - A three letter code denoting the language of the lyrics. Only really necessary for MP3 files as the ID3 Frames for both synced and unsynced lyrics (SYLT and USLT respectively) allow for attaching lyrics in multiple languages (but only 1 per language).
        - The program will save them as all caps
        - The three letter codes used are generally either "XXX" or from the ISO 639-3 standard (https://en.wikipedia.org/wiki/ISO_639-3)
    - Default: Configured by "lang" in the "lyrics" section of configs.toml
- --insert-empty: INS_EMPTY
    - Controls whether or not to save an empty lyric file if no lyrics are found (or the song was an instrumental)
        - When used with not overwriting, useful for skipping tracks which are instrumental or have no results if the program is repeatedly run on the same file or folders
        - The "language" of the empty lyrics defaults to "XXX"
    - Choices: 0 or 1.
        - 0: Do not save empty lyrics
        - 1: Save empty lyrics
    - Default: Configured by "save_to_folder" in the "lyrics" section of configs.toml
- --logging-level: LOGGING_LEVEL
    - The program will log messages in "logs/lyrics.log". This controls the level of logging to be saved.
    - Choices: debug, info, warning, error, critical
    - Default: Configured by "level" in the "logging" section of configs.toml

### Cover Art Finder
```
py covers.py [-h] [-f, --folder FOLDER] [-x, --max-size MAX_SIZE] [-n, --min-size MIN_SIZE] [-r, --resize RESIZE] [-e, --embed-in-file EMBED] [-s, --save-to-folder SAVE] [-l, --cover-name COVER_NAME] [--logging-level LOGGING_LEVEL] 
```
Used to search for cover art for an album and either embed it into track files or save the art to the same folder as the file. Can also be used to resize existing cover art (only smaller, not larger). If any cover art is found in either a file or its folder, and that cover art is the same size as (or larger than) the given minimum size, it will use that file, otherwise, it'll use the "COV Integration Tool" from Music Hoarders to search https://covers.musichoarders.xyz/. 

NB: Searching Music Hoarders requres that the "COV Integration Tool" has been downloaded and placed into the "external_tools" folder. I don't know the legality of distributing the file myself nor which a user might need as it's written for Windows, Mac OS (Intel and Arm) and Linux.

#### Arguments
- Any arguments used will supercede their configured values in config.toml
- -f, --folder FOLDER: A location to search (recursively) for files to search for cover art for
    - This can one of 3 strings:
        - A library name as configured in the "libraries" section of configs.toml
        - An absolute path to a folder (has not been tested with symlinks)
        - A relative path that starts with a library name and goes deeper into its file structure
            - e.g. 'library1/Gammer' if library1 is defined in configs.toml
- -x, --max-size MAX_SIZE
    - An integer value denoting the maximum size (in pixels) when searching for a local file to use.
    - Also used as the size to shrink a cover down to when resize is set to 'max'.
    - Default: Configured by "max_size" in the "covers" section of configs.toml
- -n, --min-size MIN_SIZE
    - An integer value denoting the minimum size (in pixels) when searching for a local file to use as well as when searching on Music Hoarders.
    - Also used as the size to shrink a cover down to when resize is set to 'min'.
    - Default: Configured by "min_size" in the "covers" section of configs.toml
- -r, --resize RESIZE
    - Specifies whether or not to resize cover art that's been found either locally or through Music Hoarders.
    - Choices: max, min, original
        - "max" and "min" tell the program to use the maximum and minimum configured sizes respectively.
        - "original" leaves the file as is.
    - Default: Configured by "resize" in the "covers" section of configs.toml
- -e, --embed-in-file: EMBED
    - Controls whether or not to embed the cover art into the track file.
    - Choices: "remove", "leave", "embed"
        - "remove": Remove any cover art embedded into the file.
        - "leave": If any cover art is found embedded within the file, do nothing to it.
        - "embed": Embed the cover art.
    - Default: Configured by "embed_in_file" in the "covers" section of configs.toml
- -s, --save-to-folder: SAVE
    - Controls whether or not to save the cover art to a file in the same folder as the track.
    - Choices: "save" or "nosave"
        - nosave: Do not save the cover art in the same folder as the file.
        - save: Save the cover art in the same folder as the file.
    - Default: Configured by "save_to_folder" in the "covers" section of configs.toml
- -l, --cover-name COVER_NAME
    - Specifies the naming of the file when --save-to-folder is set to "save"
    - Default: Configured by "filename" in the "covers" section of configs.toml
- --logging-level: LOGGING_LEVEL
    - The program will log messages in "logs/covers.log". This controls the level of logging to be saved.
    - Choices: debug, info, warning, error, critical
    - Default: Configured by "level" in the "logging" section of configs.toml


## Some things I Still Want To Do
- Add more logging to the cover art finder
- Add any logging to the conversion script
- Add a script for formatting the folder structure
- Add support for naming a cover file based off the metadata of a track
- Maybe add support for searchhing MusicBrainz?
- Probably some other things I'm not thinking about right now.