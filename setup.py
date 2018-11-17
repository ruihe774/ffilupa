import sys
try:
    import cffi, semantic_version
except ImportError:
    from subprocess import check_call, run
    check_call((sys.executable, '-mpip', 'install', '-r', 'requirements.txt'))
    p = run((sys.executable, *sys.argv))
    sys.exit(p.returncode)

with open('requirements.txt') as f:
    setup_requires = [p.rstrip() for p in f.readlines()]

from setuptools import setup
from pathlib import Path
import asyncio
import json
import semantic_version as sv
import findlua
from findlua import read_resource


def has_option(name):
    if name in sys.argv[1:]:
        sys.argv.remove(name)
        return True
    return False

BUNDLE_LUA_VERSION = '5.3.5'

def get_bundle_builder():
    lua_sources = \
        ['lapi.c', 'lcode.c', 'lctype.c', 'ldebug.c', 'ldo.c', 'ldump.c', 'lfunc.c', 'lgc.c', 'llex.c', 'lmem.c',
         'lobject.c', 'lopcodes.c', 'lparser.c', 'lstate.c', 'lstring.c', 'ltable.c', 'ltm.c', 'lundump.c', 'lvm.c',
         'lzio.c', 'lauxlib.c', 'lbaselib.c', 'lbitlib.c', 'lcorolib.c', 'ldblib.c', 'liolib.c', 'lmathlib.c',
         'loslib.c', 'lstrlib.c', 'ltablib.c', 'lutf8lib.c', 'loadlib.c', 'linit.c']
    bundle_lua_path = 'third-party/lua/'
    MODNAME = 'ffilupa._bundle'
    lua_cdef, caller_cdef, source = (
        read_resource('lua_cdef.h'),
        read_resource('cdef.h'),
        read_resource('source.c'),
    )
    cdef = '\n'.join((lua_cdef, caller_cdef))
    ffi = cffi.FFI()
    ffi.set_source(MODNAME, source, sources=[bundle_lua_path + 'src/' + p for p in lua_sources], include_dirs=[bundle_lua_path + 'src/'])
    ffi.cdef(findlua.process_cdef(sv.Version(BUNDLE_LUA_VERSION), cdef))
    return ffi

def gen_ext():
    findlua.init_loop()
    loop = asyncio.get_event_loop()
    mods = loop.run_until_complete(findlua.findlua())
    loop.close()
    if not mods:
        print('Warning: No Lua distribution found.', file=sys.stderr)
    ext_modules = [
        builder.distutils_extension()
        for builder in findlua.make_builders(mods, has_option('embedding'))
    ]
    use_bundle = (has_option('--use-bundle') or sys.platform == 'win32') and not has_option('--no-bundle')
    if use_bundle:
        ext_modules.append(get_bundle_builder().distutils_extension())
    class MyJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, sv.Version):
                return str(o)
            else:
                return super().default(o)
    with Path('ffilupa', 'lua.json').open('w', encoding='ascii') as f:
        d = {k: v._asdict() for k, v in mods.items()}
        if use_bundle:
            d['bundle'] = {
                'libraries': [],
                'include_dirs': [],
                'version': BUNDLE_LUA_VERSION,
                'extra_compile_args': [],
                'extra_link_args': [],
                'library_dirs': [],
            }
        json.dump(d, f, cls=MyJSONEncoder, indent=4)
    return ext_modules

def read_version():
    from os import path
    global VERSION
    with open(path.join('ffilupa', 'version.txt')) as f:
        VERSION = f.read().rstrip()
read_version(); del read_version

setup(
    name='ffilupa',
    version=VERSION,
    author="TitanSnow",
    author_email="tttnns1024@gmail.com",
    url='https://github.com/TitanSnow/ffilupa',
    description='cffi binding of lua for python',
    long_description=open('README.rst', encoding='utf8').read(),
    license='LGPLv3',
    classifiers=(
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Other Scripting Engines',
        'Operating System :: OS Independent',
        'Topic :: Software Development',
    ),
    packages=('ffilupa',),
    package_data={
        'ffilupa': ('lua.json', 'version.txt'),
    },
    include_package_data=True,
    setup_requires=setup_requires,
    install_requires=('cffi~=1.10', 'semantic_version~=2.2',),
    ext_modules=gen_ext(),
)
