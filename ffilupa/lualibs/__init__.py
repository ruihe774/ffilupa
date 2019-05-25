__all__ = ('PkgInfo', 'LuaLib', 'get_lualibs', 'set_default_lualib', 'get_default_lualib', 'register_lualib')


from packaging.version import Version
from packaging.specifiers import SpecifierSet
from typing import *
from importlib import util as importutil
from importlib.machinery import ModuleSpec
import types
from ._base import PkgInfo
from ._builder_data import bundle_lua_pkginfo


class LuaLib:
    """LuaLib represents a lua library to be used by LuaRuntime"""
    def __init__(self, name: str, info: PkgInfo) -> None:
        """init self with ``name`` and ``info``"""
        self.name = name
        self.info = info
        self._mod = None

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
        assert self.info.module_location is not None
        return importutil.spec_from_file_location(self.name, self.info.module_location)

    def import_mod(self) -> types.ModuleType:
        """import and return the lua module"""
        if self._mod is not None:
            return self._mod
        else:
            spec = self._get_mod_spec()
            self._mod = importutil.module_from_spec(spec)
            spec.loader.exec_module(self._mod)
            return self._mod

    @classmethod
    def from_pkginfo(cls, info: PkgInfo) -> 'LuaLib':
        name = f'lua_{hash(info)}'
        return cls(name, info)


class BundleLuaLib(LuaLib):
    def _get_mod_spec(self) -> ModuleSpec:
        return importutil.find_spec('._lua', package='ffilupa')


lualibs = None
default_lualib = None


def get_lualibs() -> List[LuaLib]:
    """get lua libs"""
    global lualibs, default_lualib
    if lualibs is None:
        bundle_lualib = BundleLuaLib.from_pkginfo(bundle_lua_pkginfo)
        lualibs = [bundle_lualib]
        default_lualib = bundle_lualib
    return lualibs


def set_default_lualib(lualib: LuaLib) -> None:
    """set the default lua lib"""
    global default_lualib
    get_lualibs()
    default_lualib = lualib


def get_default_lualib() -> LuaLib:
    """get the default lua lib"""
    get_lualibs()
    return default_lualib


def register_lualib(lualib: LuaLib) -> None:
    """register a new lua lib"""
    get_lualibs()
    lualibs.append(lualib)
