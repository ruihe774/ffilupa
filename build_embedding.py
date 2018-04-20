import argparse, uuid, json
from pathlib import Path
import semantic_version as sv
from findlua import PkgInfo, make_builders


def build(name, mod, verbose=True, target=None):
    builders = make_builders({name: mod})
    for builder in builders:
        builder.compile(verbose=verbose, target=target)

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
    ap.add_argument('--version', required=True, type=sv.Version)
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--target')
    opt = ap.parse_args()
    info = vars(opt).copy()
    info.pop('name')
    info.pop('verbose')
    info.pop('target')
    info = PkgInfo(**info)
    build(opt.name, info, verbose=opt.verbose, target=opt.target)


assert __name__ == '__main__'
main()
