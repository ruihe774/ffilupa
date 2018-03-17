from collections import namedtuple
from asyncio import subprocess as sp
from itertools import zip_longest
import asyncio
import shlex
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
        return PkgInfo(
            *(
                [
                    parse_pkg_result(result[0].decode())
                    for result in results[:-1]
                ] +
                [tuple(results[-1][0].decode().strip().split('.'))]
            )
        )


def parse_pkg_result(arg):
    return tuple(shlex.split(opt[2:])[0] for opt in shlex.split(arg.strip()))


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
        match = ver_sign.search(ln.rstrip())
        if match:
            if compare_version(match.group(2).split('.'), ver) in (
                (1,) if match.group(1) == '>=' else (-1, 0)
            ):
                continue

        lns.append(ln)
    return '\n'.join(lns)


async def compile_all():
    MOD = 'ffilupa._{}'
    mods = await findlua_by_pkg()
    with open('lua_cdef.h', 'r') as f:
        cdef = f.read()
    for name, info in mods.items():
        ffi = cffi.FFI()
        options = info._asdict().copy()
        options.pop('version')
        ffi.set_source(
            MOD.format(name),
            '#include "lua.h"\n#include "lauxlib.h"',
            **options
        )
        ffi.cdef(process_cdef(info.version, cdef))
        ffi.compile(verbose=True)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(compile_all())
