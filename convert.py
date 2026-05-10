from argparse import ArgumentParser
from utils.utils import utils, log, logging_levels
from utils.track import Track

def convert(args):
    utils.set_working_dir(args.folder)

    new_format = utils.check_supported_format(args.destination_format)
    source_format = utils.get_supported_formats(args.source_format)

    b_delete = (args.delete == 1)
    conversion_args = Track.parse_conversion_args(args.conversion_args)
    file_args = Track.parse_file_args(new_format, args.file_args)

    files = utils.get_files(source_format)
    for file in files:
        trk = Track.open(file)
        trk.convert(new_format, conversion_args, file_args, b_delete)

def show_args_help(args):
    if args.destination_format:
        help = {
            args.destination_format.upper(): {
                'conversion_help': Track.conversion_args_help(args.destination_format),
                'file_help': Track.file_args_help(args.destination_format)
            }
        }
    else:
        help = {}
        for file_type in utils.get_supported_formats():
            help.update({file_type: {
                'conversion_help': Track.conversion_args_help(args.destination_format),
                'file_help': Track.file_args_help(args.destination_format)
            }})
    for file_type, help_strs in help.items():
        print(f'{file_type}:')
        for help_str in help_strs.values():
            print(help_str)

def setup_args():
    default_file_to = utils.get_default_args(str, 'convert', 'file_type')
    default_file_from = utils.get_supported_formats(filt=default_file_to)
    default_conversion_params = utils.get_default_args(list, 'convert', 'parameters', default_file_to, default=[])
    parser = ArgumentParser()
    parser.add_argument('-f', '--folder')
    parser.add_argument('-s', '--source-format', nargs='+', default=default_file_from)
    parser.add_argument('-t', '--destination-format', type=str, default=default_file_to)
    parser.add_argument('-d', '--delete', type=int, default=utils.get_default_args(int, 'convert', 'delete_source'))
    parser.add_argument('-o', '--conversion-args', type=str, nargs='+', default=default_conversion_params)
    parser.add_argument('-n', '--file-args', nargs='+', default=[])
    parser.add_argument('-a', '--args-help', action='store_true')
    parser.add_argument('--logging-level', choices=[l for l in logging_levels.keys()], default=utils.get_default_args(str, 'logging', 'level'))
    return parser

if __name__ == '__main__':
    parser = setup_args()
    args = parser.parse_args()
    if args.args_help:
        show_args_help(args)
    else:
        convert(args)
