from tomlkit import parse, dumps
from pathlib import Path
from sys import stdout as sysstdout
from logging import getLogger as log_getLogger, \
                    basicConfig as log_basicConfig, \
                    DEBUG, INFO, WARNING, ERROR, CRITICAL

supported_formats = [
    'flac',
    'wav',
    'mp3',
    'm4a'
]

log = log_getLogger(__name__)
logging_levels = {
    'debug': DEBUG,
    'info': INFO,
    'warning': WARNING,
    'error': ERROR,
    'critical': CRITICAL
}

class utils(object):
    working_dir = Path().cwd()

    @staticmethod
    def get_configs(*args, config_file='configs.toml', default=None):
        config_path = Path(config_file)
        if not config_path.exists():
            raise Exception(f'Unable to find config file at {config_path.resolve()}')
        with open(config_file, 'r') as f:
            configs = parse(f.read())
        for arg in args:
            if arg in configs:
                configs = configs[arg]
            else:
                configs = default
                break
        if isinstance(configs, dict):
            configs = {k:v for k, v in configs.items() if not isinstance(v, dict)}
        return configs

    @staticmethod
    def set_configs(section=None, key=None, val=None, config_file='configs.toml', overwrite=True):
        config_path = Path(config_file)
        if not config_path.exists():
            raise Exception(f'Unable to find config file at {config_path.resolve()}')

        with open(config_file, 'r') as f:
            configs = parse(f.read())

        if section is not None:
            if section not in configs:
                configs[section] = {}
            if (key in configs[section] and overwrite) \
                or key not in configs[section]:
                configs[section].update({key: val})
        
        with open(config_file, 'w') as f:
            f.write(dumps(configs))

    @staticmethod
    def get_default_args(arg_type, *args, default=None):
        val = utils.get_configs(*args)
        
        if val is None:
            return default
        elif arg_type == bool and not val:
            return 'store_true'
        elif arg_type == bool and val:
            return 'store_false'
        elif arg_type == str and type(val) != str:
            return str(val)
        elif arg_type == list and type(val) in (set, tuple):
            return list(val)
        elif arg_type == list and not isinstance(val, (list)):
            return [val]
        elif arg_type in (float, int) and not isinstance(val, (arg_type)):
            return arg_type(val)
        else:
            return val

    @staticmethod
    def set_working_dir(dir_in=''):
        dir_in = dir_in.replace('\\', '/')

        # First try a library
        a_dir_in = dir_in.split('/')
        dir = utils.get_configs('libraries', a_dir_in[0])
        if dir:
            full_dir = Path(dir + '/' + '/'.join(a_dir_in[1:]))
            if full_dir.exists():
                utils.working_dir = full_dir
                return utils.working_dir
        
        # Next, try a relative path
        dir = Path.cwd() / dir_in
        if dir.exists():
            utils.working_dir = dir
            return dir

        # Finally, try an absolute path
        dir = Path(dir_in)
        if dir.exists():
            utils.working_dir = dir
            return dir
        
        # Cannot use whatever was sent in.
        raise Exception(f'{dir} does not exist or is not accessible.')

    @staticmethod
    def get_supported_formats(chk=supported_formats, filt=None):
        for form in chk:
            if form not in supported_formats:
                raise Exception(f'Format {chk} is not supported for this operation.')
        supported = [form for form in chk if form != filt]
        return supported

    @staticmethod
    def check_supported_format(chk):
        chk = chk.lower()
        if chk not in supported_formats:
            raise Exception(f'Format {chk} is not supported for this operation.')
        return chk

    @staticmethod
    def get_files(suffixes=supported_formats):
        files = [file for suffix in suffixes for file in utils.working_dir.rglob(f'**/*.{suffix}')]
        return files
    
    @staticmethod
    def progressbar(items, prefix="", size=50, out=sysstdout):
        count = len(items)
        def show(i, item):
            pct = int(size*i/count)
            item_str = f'| {item:150}'
            print_str = f"{prefix}[{u'█'*pct}{('.'*(size-pct))}] {i}/{count} {item_str}"[:160]
            print(f'{print_str:160}', end='\r', file=out, flush=True)
        for i, item in enumerate(items):
            show(i+1, item)
            yield item
        print("", flush=True, file=out)

    @staticmethod
    def start_log(fname, level):
        fname = Path().cwd() / 'logs' / fname
        log_basicConfig(filename=fname, 
                            level=logging_levels[level], 
                            format='%(asctime)s,%(msecs)03d %(levelname)-8s [%(filename)s:%(lineno)d] %(message)s',
                            datefmt='%Y-%m-%dT%H:%M:%S')
        log.info(f'Begin logging.')