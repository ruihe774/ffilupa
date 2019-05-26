__all__ = ('extension_from_pkginfo', 'bundle_lua_pkginfo', 'pkginfo_from_pkgconfig', 'add_pkg')


import cffi
from cffi import pkgconfig
from ._base import PkgInfo
from ._builder_data import *
from ..util import ensure_strpath
from distutils.ccompiler import new_compiler
from distutils.core import Extension
import os
from typing import *
import re
from packaging.version import Version
from packaging.specifiers import SpecifierSet
from pathlib import Path
from uuid import uuid4
import tempfile


cc = new_compiler()
lib_format = cc.shared_lib_format % ('\ufffd', cc.shared_lib_extension)
lib_name_pos = lib_format.index('\ufffd')
lib_name_range = slice(lib_name_pos, lib_name_pos + 1 - len(lib_format))
del cc
del lib_format
del lib_name_pos


def process_cdef(ver: Version, cdef: str) -> str:
    ver_sign = re.compile(r'\/\/\s*VER:\s*(.+)$')
    lns = []
    for ln in cdef.splitlines():
        match = ver_sign.search(ln.rstrip())
        if not match or SpecifierSet(match.group(1)).contains(ver):
            lns.append(ln)
    return '\n'.join(lns)


def ffibuilder_from_pkginfo(mod_name: str, info: PkgInfo) -> cffi.FFI:
    ffi = cffi.FFI()
    options = {}
    for opt in ('sources', 'libraries', 'include_dirs', 'library_dirs', 'extra_compile_args', 'extra_link_args',):
        options[opt] = list(getattr(info, opt))
    origin_libraries = options['libraries']
    options['libraries'] = []
    options['library_dirs'] = []
    for lib in origin_libraries:
        if os.path.isabs(lib):
            options['libraries'].append(os.path.basename(lib)[lib_name_range])
            options['library_dirs'].append(os.path.dirname(lib))
        else:
            options['libraries'].append(lib)
    ffi.set_source(mod_name, source, **options)
    ffi.cdef(process_cdef(info.version, cdef))
    return ffi


def extension_from_pkginfo(mod_name: str, info: PkgInfo, tmpdir: Union[os.PathLike, str] = 'build') -> Extension:
    return ffibuilder_from_pkginfo(mod_name, info).distutils_extension(tmpdir=ensure_strpath(tmpdir))


def compile_pkg(mod_name: str, info: PkgInfo, tmpdir: Union[os.PathLike, str] = 'build') -> Path:
    return Path(ffibuilder_from_pkginfo(mod_name, info).compile(tmpdir=tmpdir))


def pkginfo_from_pkgconfig(libname: str) -> PkgInfo:
    version = pkgconfig.call(libname, '--modversion')
    flags = pkgconfig.flags_from_pkgconfig((libname,))
    info = PkgInfo(
        version=Version(version),
        **({k: tuple(v) for k, v in flags.items()})
    )
    return info
