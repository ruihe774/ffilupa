from collections import namedtuple, OrderedDict
from asyncio import subprocess as sp
from itertools import zip_longest, chain
from pathlib import Path
from distutils.ccompiler import new_compiler
import tempfile
import asyncio
import shlex
import sys
import re
import os
import cffi
import semantic_version as sv

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


async def run_cmd(*args, input=None, cwd=None):
    process = await sp.create_subprocess_exec(
        *args, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE, cwd=cwd
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
            [sv.Version(pkg[5].strip())],
        )
    )


async def findlua_by_pkg():
    LUA = 'lua'
    VERSIONS = ('52', '53',)
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


async def cmake(cmakelists):
    with tempfile.TemporaryDirectory() as d:
        with Path(d, 'CMakeLists.txt').open('w') as f:
            f.write(cmakelists)
        rst = await run_cmd('cmake', '.', cwd=d)
        if rst:
            return parse_cmake(rst[1].decode())


def parse_cmake(rst):
    lns = [ln.rstrip() for ln in rst.splitlines()]
    if lns[0] == 'FOUND':
        return PkgInfo(
            libraries=lns[1].split(';'),
            include_dirs=lns[2].split(';'),
            version=sv.Version(lns[3]),
            extra_compile_args=[],
            extra_link_args=[],
            library_dirs=[],
        )


async def findlua_by_cmake():
    LUA = 'lua'
    VERSIONS = ('52', '53')
    CMK_VERSIONS = ('5.2', '5.3')
    cmakelists_template = read_resource('CMakeLists_template.txt')
    return {
        modname: lua
        for modname, lua in zip(
            [LUA + ver for ver in VERSIONS],
            await asyncio.gather(
                *[cmake(cmakelists_template % ver) for ver in CMK_VERSIONS],
                return_exceptions=True
            ),
        )
        if isinstance(lua, PkgInfo)
    }


def process_cdef(ver, cdef):
    ver_sign = re.compile(r'\/\/\s*VER:\s*(.+)$')
    lns = []
    for ln in cdef.splitlines():
        match = ver_sign.search(ln.rstrip())
        if not match or sv.Spec(match.group(1)).match(ver):
            lns.append(ln)
    return '\n'.join(lns)


def read_resource(filename):
    with (Path(__file__).parent / filename).open() as f:
        return f.read()


def make_builders(mods):
    MOD = 'ffilupa._{}'
    EMBED_LIB = '_ffilupa_embedding_{}'
    builders = []
    lua_cdef, caller_cdef, source = (
        read_resource('lua_cdef.h'),
        read_resource('cdef.h'),
        read_resource('source.c'),
    )
    embedding_api, embedding_source, embedding_init_code = (
        read_resource('embedding.h'),
        read_resource('embedding.c'),
        read_resource('embedding-template.py'),
    )
    cdef = '\n'.join((lua_cdef, caller_cdef))
    cc = new_compiler()
    lib_format = cc.shared_lib_format % ('\ufffd', cc.shared_lib_extension)
    lib_name_pos = lib_format.index('\ufffd')
    lib_name_range = slice(lib_name_pos, lib_name_pos + 1 - len(lib_format))
    for name, info in mods.items():
        ffi = cffi.FFI()
        options = info._asdict().copy()
        options.pop('version')
        origin_libraries = options['libraries']
        options['libraries'] = []
        for lib in origin_libraries:
            if os.path.isabs(lib):
                options['libraries'].append(os.path.basename(lib)[lib_name_range])
                options['library_dirs'].append(os.path.dirname(lib))
            else:
                options['libraries'].append(lib)
        ffi.set_source(MOD.format(name), source, **options)
        ffi.cdef(process_cdef(info.version, cdef))
        builders.append(ffi)

        # make embedding
        if info.version not in sv.Spec('>=5.2'):
            continue
        ffi = cffi.FFI()
        libname = EMBED_LIB.format(name)
        ffi.set_source(libname, embedding_source, **options)
        ffi.embedding_api(embedding_api)
        ffi.embedding_init_code(embedding_init_code.format(libname=libname))

        builders.append(ffi)
    return builders


async def findlua():
    pkg, cmk = await asyncio.gather(findlua_by_pkg(), findlua_by_cmake())
    rst = cmk.copy()
    rst.update(pkg)
    return rst


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
