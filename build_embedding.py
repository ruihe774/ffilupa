setup_requires=('cffi~=1.10', 'semantic_version~=2.2',)
try:
    import cffi, semantic_version
except ImportError:
    try:
        from pip import main as pip
    except ImportError:
        # pip >=10.0
        from pip._internal import main as pip
    pip(['install'] + list(setup_requires))


import argparse, uuid, json
import subprocess as sp
from pathlib import Path
import semantic_version as sv
from findlua import PkgInfo, make_builders


def build(name, mod, verbose=True, target=None):
    builders = make_builders({name: mod})
    builders[0].compile(verbose=verbose)
    builders[1].compile(verbose=verbose, target=target)

    class MyJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, sv.Version):
                return str(o)
            else:
                return super().default(o)

    with Path('ffilupa', 'lua.json').open('w', encoding='ascii') as f:
        json.dump({name: mod._asdict()}, f, cls=MyJSONEncoder, indent=4)


def main():
    ap = argparse.ArgumentParser()
    for field in PkgInfo._fields[:-1]:
        ap.add_argument('--' + field, nargs='*', default=[])
    ap.add_argument('--name', default=uuid.uuid4().hex)
    ap.add_argument('--version', type=sv.Version)
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--target')
    ap.add_argument('--lua')
    opt = ap.parse_args()
    if opt.lua:
        opt.version = sv.Version(sp.run((opt.lua, '-v'), check=True, universal_newlines=True, stdout=sp.PIPE).stdout.split()[1])
    info = vars(opt).copy()
    info.pop('name')
    info.pop('verbose')
    info.pop('target')
    info.pop('lua')
    info = PkgInfo(**info)
    build(opt.name, info, verbose=opt.verbose, target=opt.target)


assert __name__ == '__main__'
main()
