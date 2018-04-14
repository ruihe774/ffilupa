import sys


def trim_libname(shuffix):
    from pathlib import Path
    for path in Path('.').glob('*' + shuffix):
        try:
            ind = path.name.index('.')
        except ValueError:
            pass
        else:
            path.rename(path.parent / (path.name[:ind] + shuffix))


def mv(*args):
    import shutil
    for src in args[:-1]:
        shutil.move(src, args[-1])


if __name__ == '__main__':
    globals()[sys.argv[1]](*sys.argv[2:])
