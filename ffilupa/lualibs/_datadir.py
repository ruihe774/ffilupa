__all__ = ('get_data_dir',)


from pathlib import Path
import os


def get_nt_data_dir_prefix() -> Path:
    try:
        return Path(os.environ['APPDATA'])
    except KeyError as e:
        raise ValueError('%APPDATA% is not set') from e


def is_root() -> bool:
    return os.geteuid() == 0


def get_posix_data_dir_prefix() -> Path:
    if is_root():
        return Path(os.environ.get('XDG_DATA_DIRS', '/usr/local/share/:/usr/share/').split(':')[0])
    else:
        return Path(os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share')))


def get_data_dir_prefix() -> Path:
    if os.name == 'nt':
        return get_nt_data_dir_prefix()
    elif os.name == 'posix':
        return get_posix_data_dir_prefix()
    else:
        raise ValueError(f'platform "{os.name}" is not supported')


def get_data_dir() -> Path:
    prefix = get_data_dir_prefix()
    datadir = prefix / 'ffilupa'
    datadir.mkdir(parents=True, exist_ok=True)
    return datadir