__all__ = (
    "PkgInfo",
    "LuaLib",
    "get_lualibs",
    "set_default_lualib",
    "get_default_lualib",
    "register_lualib",
)


from packaging.version import Version
from packaging.specifiers import SpecifierSet
from typing import *
from importlib import util as importutil
from importlib.machinery import ModuleSpec
import types
from pathlib import Path
from ._pkginfo import *
from ._builder_data import bundle_lua_pkginfo
from ._datadir import *
import json
import os
from contextlib import contextmanager
import sys


if os.name == 'nt':
    if sys.version_info[1] <= 7:
        @contextmanager
        def add_runtime_library_dirs(dirs: Tuple[str]) -> None:
            path = os.environ['PATH']
            os.environ['PATH'] += ';' + ';'.join(dirs)
            try:
                yield
            finally:
                os.environ['PATH'] = path
    else:
        @contextmanager
        def add_runtime_library_dirs(dirs: Tuple[str]) -> None:
            ds = [os.add_dll_directory(d) for d in dirs]
            try:
                yield
            finally:
                for o in ds:
                    o.close()
else:
    @contextmanager
    def add_runtime_library_dirs(dirs: Tuple[str]) -> None:
        yield


class LuaLib:
    """LuaLib represents a lua library to be used by LuaRuntime"""

    def __init__(self, info: PkgInfo) -> None:
        self.info = info
        self._mod: Optional[types.ModuleType] = None

    @property
    def name(self) -> str:
        """name of the lua lib"""
        return self.info.module_name or self.info.module_location

    @property
    def version(self) -> Version:
        """lua version from PkgInfo"""
        return self.info.version

    @property
    def lua_version(self) -> Version:
        """lua version from LUA_RELEASE. (will import module)"""
        mod = self.import_mod()
        return Version(mod.ffi.string(mod.lib.LUA_RELEASE).decode()[4:])

    def _get_mod_spec(self) -> ModuleSpec:
        mod_loc = self.info.module_location
        if isinstance(mod_loc, str):
            mod = importutil.find_spec(mod_loc)
            if mod is None:
                raise ModuleNotFoundError(f"No module named '{mod_loc}'", name=mod_loc)
            else:
                return mod
        elif isinstance(mod_loc, Path):
            assert self.info.module_name is not None
            mod = importutil.spec_from_file_location(
                self.info.module_name, str(mod_loc)
            )
            if mod is None:
                raise ModuleNotFoundError(
                    f"No module at '{mod_loc}'", path=str(mod_loc)
                )
            else:
                return mod
        else:
            raise ValueError(
                "module location not specified (maybe the pkg is not compiled)"
            )

    def import_mod(self) -> types.ModuleType:
        """import and return the lua module"""
        if self._mod is not None:
            return self._mod
        else:
            spec = self._get_mod_spec()
            with add_runtime_library_dirs(self.info.runtime_library_dirs):
                self._mod = importutil.module_from_spec(spec)
                spec.loader.exec_module(self._mod)
            return self._mod


_lualibs = None
_default_lualib = None


def get_lualibs() -> List[LuaLib]:
    """get lua libs"""
    global _lualibs, _default_lualib
    if _lualibs is None:
        bundle_lualib = LuaLib(bundle_lua_pkginfo)
        _lualibs = [bundle_lualib]
        for data_dir in (get_data_dir(), get_global_data_dir()):
            if data_dir is not None:
                try:
                    with (data_dir / "ffilupa.json").open() as f:
                        config = json.load(f)
                        for pkg in config["lua_pkgs"]:
                            try:
                                _lualibs.append(LuaLib(PkgInfo.deserialize(pkg)))
                            except (VersionIncompatible, AbiIncompatible):
                                pass
                except (FileNotFoundError, KeyError):
                    pass
        _default_lualib = bundle_lualib
    return _lualibs


def set_default_lualib(lualib: LuaLib) -> None:
    """set the default lua lib"""
    global _default_lualib
    get_lualibs()
    _default_lualib = lualib


def get_default_lualib() -> LuaLib:
    """get the default lua lib"""
    get_lualibs()
    return _default_lualib


def register_lualib(lualib: LuaLib) -> None:
    """register a new lua lib"""
    get_lualibs()
    _lualibs.append(lualib)
