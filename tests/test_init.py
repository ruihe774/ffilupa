from os import path
import ffilupa


versionfile_path = path.join(path.dirname(ffilupa.__file__), 'version.txt')
version = open(versionfile_path).read().rstrip()


def test_version():
    assert ffilupa.__version__ == version


def test_all():
    assert isinstance(ffilupa.__all__, tuple)


def test_read_version():
    from importlib import reload
    import builtins
    global ffilupa
    open_ = open
    def _open(*args, **kwargs):
        if args and args[0] == versionfile_path:
            raise OSError(2, versionfile_path)
        else:
            return open_(*args, **kwargs)
    builtins.open = _open
    ffilupa = reload(ffilupa)
    assert ffilupa.__version__ == version
    builtins.open = open_
