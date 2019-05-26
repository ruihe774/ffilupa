__all__ = ('PkgInfo',)


from dataclasses import dataclass, asdict
from datetime import datetime
from packaging.version import Version
from packaging.specifiers import SpecifierSet
from typing import *
from pathlib import Path
import tomlkit
from tomlkit.toml_document import TOMLDocument
from ..__version__ import __version__


@dataclass(frozen=True)
class PkgInfo:
    """PkgInfo contains infomation about a lua library to create LuaLib"""
    # version info
    version: Version
    ffilupa_version: Version = Version(__version__)
    lua_variant: str = 'lua'
    # module location
    module_location: Optional[Path] = None
    # build info (not used)
    sources: Tuple[str] = ()
    libraries: Tuple[str] = ()
    include_dirs: Tuple[str] = ()
    library_dirs: Tuple[str] = ()
    define_macros: Tuple[str] = ()
    extra_compile_args: Tuple[str] = ()
    extra_link_args: Tuple[str] = ()
    build_time: Optional[datetime] = None

    def to_toml(self, doc: TOMLDocument) -> None:
        table = tomlkit.table()
        for k, v in asdict(self).items():
            if isinstance(v, Version):
                w = str(v)
            elif isinstance(v, Path):
                w = str(v)
            elif v is None:
                continue
            elif isinstance(v, tuple):
                w = list(v)
            else:
                w = v
            table[k] = w
        doc[str(hash(self))] = table

    @classmethod
    def from_toml(cls, doc: TOMLDocument, section: str) -> 'PkgInfo':
        table = doc[section]
        info = PkgInfo(
            # version info
            version=Version(table['version']),
            ffilupa_version=Version(table['ffilupa_version']),
            lua_variant=table['lua_variant'],
            # module location
            module_location=None if 'module_location' not in table else Path(table['module_location']),
            # build info (not used)
            sources=tuple(table['sources']),
            libraries=tuple(table['libraries']),
            include_dirs=tuple(table['include_dirs']),
            library_dirs=tuple(table['library_dirs']),
            define_macros=tuple(table['define_macros']),
            extra_compile_args=tuple(table['extra_compile_args']),
            extra_link_args=tuple(table['extra_link_args']),
            build_time=table.get('build_time'),
        )
        assert hash(info) == int(section)
        return info
