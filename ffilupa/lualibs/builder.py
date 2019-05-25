import cffi
from ._base import PkgInfo
from ._builder_data import cdef, source
from ..util import ensure_strpath
from distutils.ccompiler import new_compiler
from distutils.core import Extension
import os
from typing import *
import re
from packaging.version import Version
from packaging.specifiers import SpecifierSet


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


def extension_from_pkginfo(mod_name: str, info: PkgInfo, tmpdir: Union[os.PathLike, str]) -> Extension:
    ffi = cffi.FFI()
    options = {}
    for opt in ('sources', 'libraries', 'include_dirs', 'library_dirs', 'extra_compile_args', 'extra_link_args',):
        value = getattr(info, opt)
        if value is not None:
            options[opt] = value
    origin_libraries = options.get('libraries')
    if origin_libraries:
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
    return ffi.distutils_extension(tmpdir=ensure_strpath(tmpdir))


bundle_lua_pkginfo = PkgInfo(
    version='5.3.5',
    module_location=None,
)
