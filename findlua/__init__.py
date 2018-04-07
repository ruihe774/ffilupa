from collections import namedtuple
from asyncio import subprocess as sp
from itertools import zip_longest, chain
from pathlib import Path
import asyncio
import shlex
import sys
import re
import cffi

PkgInfo = namedtuple(
    'PkgInfo',
    (
        'include_dirs',
        'library_dirs',
        'libraries',
        'extra_compile_args',
        'extra_link_args',
        'version',
    ),
)


async def run_cmd(*args, input=None):
    process = await sp.create_subprocess_exec(
        *args, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE
    )
    result = await process.communicate(input)
    if process.returncode == 0:
        return result


async def pkg_config(modname):
    PKG = 'pkg-config'
    results = await asyncio.gather(
        run_cmd(PKG, modname, '--cflags-only-I'),
        run_cmd(PKG, modname, '--libs-only-L'),
        run_cmd(PKG, modname, '--libs-only-l'),
        run_cmd(PKG, modname, '--cflags-only-other'),
        run_cmd(PKG, modname, '--libs-only-other'),
        run_cmd(PKG, modname, '--modversion'),
    )
    if None not in results:
        return parse_pkg([r[0].decode() for r in results])


def parse_pkg(pkg):
    assert len(pkg) == 6
    split_once = lambda c: shlex.split(c.strip())
    split_twice = lambda cs: [split_once(c[2:])[0] for c in split_once(cs)]
    return PkgInfo(
        *chain(
            map(split_twice, pkg[:3]),
            map(split_once, pkg[3:5]),
            [tuple(pkg[5].strip().split('.'))],
        )
    )


async def findlua_by_pkg():
    LUA = 'lua'
    VERSIONS = ('51', '52', '53', 'jit')
    return {
        modname: lua
        for modname, lua in zip(
            [LUA + ver for ver in VERSIONS],
            await asyncio.gather(
                *[pkg_config(LUA + ver) for ver in VERSIONS],
                return_exceptions=True
            ),
        )
        if isinstance(lua, PkgInfo)
    }


def compare_version(l, r):
    for a, b in zip_longest(map(int, l), map(int, r), fillvalue=0):
        if a < b:
            return -1

        elif a > b:
            return 1

    return 0


def process_cdef(ver, cdef):
    ver_sign = re.compile(r'\/\/(>=|<)\s*(\d+(?:\.\d+)*)$')
    lns = []
    for ln in cdef.splitlines():
        match = True
        while match:
            match = ver_sign.search(ln.rstrip())
            if match:
                if compare_version(match.group(2).split('.'), ver) in (
                    (1,) if match.group(1) == '>=' else (-1, 0)
                ):
                    break

                else:
                    ln = ln[:match.span()[0]]
        else:
            lns.append(ln)
    return '\n'.join(lns)


def read_resource(filename):
    with (Path(__file__).parent / filename).open() as f:
        return f.read()


def make_builders(mods):
    MOD = 'ffilupa._{}'
    builders = []
    lua_cdef, caller_cdef, source = (
        read_resource('lua_cdef.h'),
        read_resource('caller_cdef.h'),
        read_resource('source.c'),
    )
    cdef = '\n'.join((lua_cdef, caller_cdef))
    for name, info in mods.items():
        ffi = cffi.FFI()
        options = info._asdict().copy()
        options.pop('version')
        ffi.set_source(MOD.format(name), source, **options)
        ffi.cdef(process_cdef(info.version, cdef))
        builders.append(ffi)
    return tuple(builders)


async def findlua():
    return await findlua_by_pkg()


async def compile_all():
    for ffi in make_builders(await findlua()):
        ffi.compile(verbose=True)


def init_loop():
    if sys.platform == 'win32':
        asyncio.set_event_loop(asyncio.ProactorEventLoop())


if __name__ == '__main__':
    init_loop()
    loop = asyncio.get_event_loop()
    loop.run_until_complete(compile_all())
    loop.close()
