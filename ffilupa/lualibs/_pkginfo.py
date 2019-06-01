__all__ = ('PkgInfo',)


from dataclasses import dataclass
from datetime import datetime
from packaging.version import Version
from typing import *
from pathlib import Path
from setuptools import pep425tags
from os import path
from ..__version__ import __version__


@dataclass(frozen=True)
class PkgInfo:
    """PkgInfo contains information about a lua library to build lua module and create LuaLib"""
    # version info
    version: Version
    lua_variant: str = 'lua'
    ffilupa_version: Version = Version(__version__)
    python_tag: Tuple[str, str, str] = (pep425tags.get_abbr_impl() + pep425tags.get_impl_ver(), pep425tags.get_abi_tag(), pep425tags.get_platform())
    # module location
    module_location: Union[Path, str, None] = None
    # build info (not used)
    sources: Tuple[str, ...] = ()
    libraries: Tuple[str, ...] = ()
    include_dirs: Tuple[str, ...] = ()
    library_dirs: Tuple[str, ...] = ()
    define_macros: Tuple[str, ...] = ()
    extra_compile_args: Tuple[str, ...] = ()
    extra_link_args: Tuple[str, ...] = ()
    build_time: Optional[datetime] = None

    @staticmethod
    def _get_build_option_keys():
        return 'sources', 'libraries', 'include_dirs', 'library_dirs', 'define_macros', 'extra_compile_args', 'extra_link_args'

    def get_build_options(self) -> Dict[str, Tuple[str, ...]]:
        d = {}
        for k in self.__class__._get_build_option_keys():
            d[k] = getattr(self, k)
        return d

    def serialize(self) -> dict:
        """serialize into plain dict"""
        d = {
            'version': str(self.version),
            'lua_variant': self.lua_variant,
            'ffilupa_version': str(self.ffilupa_version),
            'python_tag': self.python_tag,
            'module_location': str(self.module_location) if isinstance(self.module_location, Path) else self.module_location,
        }
        for k, v in self.get_build_options().items():
            if v:
                d[k] = v
        if self.build_time:
            d['build_time'] = self.build_time.timestamp()
        d['_hash'] = hash(self)
        return d

    @classmethod
    def deserialize(cls, d: dict) -> 'PkgInfo':
        """deserialize into PkgInfo"""
        if d['ffilupa_version'] != __version__:
            raise ValueError('ffilupa version incompatible')
        mod_loc = d['module_location']
        td = {
            'version': Version(d['version']),
            'lua_variant': d['lua_variant'],
            'ffilupa_version': Version(d['ffilupa_version']),
            'python_tag': tuple(d['python_tag']),
            'module_location': Path(mod_loc) if mod_loc is not None and path.isabs(mod_loc) else mod_loc,
        }
        for k in cls._get_build_option_keys():
            td[k] = tuple(d.get(k, ()))
        td['build_time'] = None if d['build_time'] is None else datetime.fromtimestamp(d['build_time'])
        r = cls(**td)
        if hash(r) != d['_hash']:
            raise ValueError('hash mismatch')
        return r
