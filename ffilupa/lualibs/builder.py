import os
from pathlib import Path
from typing import Union, Tuple, Collection

from packaging.version import Version

from ._build_options import *
from ._builder_data import *
from .. import ensure_strpath
from cffi import FFI
from cffi import pkgconfig as pc
from setuptools import Extension


def create_ffibuilder(name: str, build_options: BuildOptions, apis: Collection[CAPI] = lua_apis, *, embedding: bool = False) -> FFI:
    ffi = FFI()
    opts = build_options.asopts()
    if os.name == "nt":
        del opts["runtime_library_dirs"]
    if embedding:
        raise NotImplementedError
    else:
        cdef, source = generate_cdef_and_source(build_options.version, apis)
        ffi.set_source(name, source, **opts)
        ffi.cdef(cdef)
    return ffi


def create_extension(name: str, build_options: BuildOptions, apis: Collection[CAPI] = lua_apis, *, tmpdir: Union[os.PathLike, str] = "build") -> Extension:
    return create_ffibuilder(name, build_options, apis).distutils_extension(tmpdir=ensure_strpath(tmpdir))



def build(name: str, build_options: BuildOptions, apis: Collection[CAPI] = lua_apis, *, tmpdir: Union[os.PathLike, str] = "build", embedding: bool = False) -> Path:
    return Path(
        create_ffibuilder(name, build_options, apis, embedding=embedding).compile(tmpdir=tmpdir)
    )


def pkgconfig(libname: str) -> BuildOptions:
    version = pc.call(libname, "--modversion")
    flags = pc.flags_from_pkgconfig((libname,))
    opts = BuildOptions(
        version=Version(version), **({k: tuple(v) for k, v in flags.items()})
    )
    return opts


