__all__ = (
    "PkgInfo",
    "bundle_lua_pkginfo",
    "pkginfo_from_pkgconfig",
    "extension_from_pkginfo",
    "compile_pkg",
    "write_pkginfo_to_configfile",
    "add_lua_pkg",
    "compile_embedding",
    "install_embedding"
)


import cffi
from cffi import pkgconfig
from ._pkginfo import PkgInfo
from ._builder_data import *
from ._datadir import get_data_dir
from .. import ensure_strpath, ensure_pathlib_path
from setuptools import Extension
import os
from typing import *
import re
from packaging.version import Version
from packaging.specifiers import SpecifierSet
from pathlib import Path
from uuid import uuid4
import tempfile
import json
import shutil
import dataclasses
from dataclasses import dataclass
from datetime import datetime


def process_cdef(ver: Version, cdef: str) -> str:
    ver_sign = re.compile(r"\/\/\s*VER:\s*(.+)$")
    lns = []
    for ln in cdef.splitlines():
        match = ver_sign.search(ln.rstrip())
        if not match or SpecifierSet(match.group(1)).contains(ver):
            lns.append(ln)
    return "\n".join(lns)


def ffibuilder_from_pkginfo(name: Optional[str], info: PkgInfo, *, embedding: bool = False) -> cffi.FFI:
    if name is None:
        if isinstance(info.module_location, str):
            name = info.module_location
        elif info.module_name is not None:
            name = info.module_name
    if name is None:
        raise ValueError("module name not provided")
    ffi = cffi.FFI()
    options = {k: list(v) for k, v in info.get_build_options().items()}
    if info.python_tag[1] == 'abi3':
        options['py_limited_api'] = True
    if os.name == 'nt':
        del options['runtime_library_dirs']
    if embedding:
        ffi.set_source(name, embedding_source, **options)
        ffi.embedding_api(embedding_api)
        ffi.embedding_init_code(embedding_py)
    else:
        ffi.set_source(name, source, **options)
        ffi.cdef(process_cdef(info.version, cdef))
    return ffi


def extension_from_pkginfo(
    name: Optional[str], info: PkgInfo, *, tmpdir: Union[os.PathLike, str] = "build"
) -> Extension:
    return ffibuilder_from_pkginfo(name, info).distutils_extension(
        tmpdir=ensure_strpath(tmpdir)
    )


def compile_pkg(
    name: Optional[str], info: PkgInfo, *, tmpdir: Union[os.PathLike, str] = "build", embedding: bool = False
) -> Path:
    return Path(ffibuilder_from_pkginfo(name, info, embedding=embedding).compile(tmpdir=tmpdir))


def pkginfo_from_pkgconfig(libname: str) -> PkgInfo:
    version = pkgconfig.call(libname, "--modversion")
    flags = pkgconfig.flags_from_pkgconfig((libname,))
    info = PkgInfo(
        version=Version(version), **({k: tuple(v) for k, v in flags.items()})
    )
    return info


def write_pkginfo_to_configfile(info: PkgInfo) -> None:
    configfile = get_data_dir() / "ffilupa.json"
    with configfile.open("a+") as f:
        if f.tell() == 0:
            config = {"lua_pkgs": []}
        else:
            f.seek(0)
            config = json.load(f)
        config["lua_pkgs"].append(info.serialize())
        f.seek(0)
        f.truncate()
        json.dump(config, f, indent=2)


def add_lua_pkg(info: PkgInfo) -> PkgInfo:
    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = get_data_dir() / "lua_pkgs"
        pkg_dir.mkdir(exist_ok=True)
        mod_name = info.module_name or "lua_" + uuid4().hex
        output = compile_pkg(mod_name, info, tmpdir=tmpdir)
        shutil.move(output.__fspath__(), pkg_dir)
        new_pkginfo = dataclasses.replace(info, module_location=pkg_dir / output.name, module_name=mod_name, build_time=datetime.utcnow())
        write_pkginfo_to_configfile(new_pkginfo)
        return new_pkginfo


def compile_embedding(modname: str, libname: str, info: PkgInfo, *, tmpdir: Union[os.PathLike, str] = "build") -> Tuple[Path, Path]:
    return compile_pkg(modname, info, tmpdir=tmpdir), compile_pkg(libname, info, embedding=True, tmpdir=tmpdir)


def install_embedding(info: PkgInfo, lua_path: Union[os.PathLike, str], lua_cpath: Union[os.PathLike, str]) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        modpath, libpath = compile_embedding('_ffilupa_pymod', '_ffilupa', info, tmpdir=tmpdir)
        new_info = dataclasses.replace(info, module_location=(ensure_pathlib_path(lua_cpath) / modpath.name), module_name='_ffilupa_pymod')
        with (ensure_pathlib_path(lua_path) / 'ffilupa.lua').open('w') as f:
            f.write(embedding_lua_init)
        with (ensure_pathlib_path(lua_cpath) / '_ffilupa.json').open('w') as f:
            json.dump(new_info.serialize(), f)
        shutil.move(ensure_strpath(modpath), ensure_strpath(lua_cpath))
        shutil.move(ensure_strpath(libpath), ensure_strpath(lua_cpath))
