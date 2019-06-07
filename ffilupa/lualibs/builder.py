__all__ = (
    "PkgInfo",
    "bundle_lua_pkginfo",
    "pkginfo_from_pkgconfig",
    "extension_from_pkginfo",
    "compile_pkg",
    "write_pkginfo_to_configfile",
    "add_lua_pkg",
)


import cffi
from cffi import pkgconfig
from ._pkginfo import PkgInfo
from ._builder_data import *
from ._datadir import get_data_dir
from .. import ensure_strpath
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
from datetime import datetime


def process_cdef(ver: Version, cdef: str) -> str:
    ver_sign = re.compile(r"\/\/\s*VER:\s*(.+)$")
    lns = []
    for ln in cdef.splitlines():
        match = ver_sign.search(ln.rstrip())
        if not match or SpecifierSet(match.group(1)).contains(ver):
            lns.append(ln)
    return "\n".join(lns)


def ffibuilder_from_pkginfo(mod_name: Optional[str], info: PkgInfo) -> cffi.FFI:
    if mod_name is None:
        if isinstance(info.module_location, str):
            mod_name = info.module_location
        elif info.module_name is not None:
            mod_name = info.module_name
    if mod_name is None:
        raise ValueError("module name not provided")
    ffi = cffi.FFI()
    options = {k: list(v) for k, v in info.get_build_options().items()}
    if info.python_tag[1] == 'abi3':
        options['py_limited_api'] = True
    ffi.set_source(mod_name, source, **options)
    ffi.cdef(process_cdef(info.version, cdef))
    return ffi


def extension_from_pkginfo(
    mod_name: Optional[str], info: PkgInfo, tmpdir: Union[os.PathLike, str] = "build"
) -> Extension:
    return ffibuilder_from_pkginfo(mod_name, info).distutils_extension(
        tmpdir=ensure_strpath(tmpdir)
    )


def compile_pkg(
    mod_name: Optional[str], info: PkgInfo, tmpdir: Union[os.PathLike, str] = "build"
) -> Path:
    return Path(ffibuilder_from_pkginfo(mod_name, info).compile(tmpdir=tmpdir))


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
        output = compile_pkg(mod_name, info, tmpdir)
        shutil.move(output.__fspath__(), pkg_dir)
        td = dataclasses.asdict(info)
        td["module_location"] = pkg_dir / output.name
        td["module_name"] = mod_name
        td["build_time"] = datetime.utcnow()
        new_pkginfo = PkgInfo(**td)
        write_pkginfo_to_configfile(new_pkginfo)
        return new_pkginfo
