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


def cp(src, dst):
    import shutil
    shutil.copy2(src, dst)


if __name__ == '__main__':
    globals()[sys.argv[1]](*sys.argv[2:])
