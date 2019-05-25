__all__ = ('PkgInfo',)


from dataclasses import dataclass
from datetime import datetime
from packaging.version import Version
from packaging.specifiers import SpecifierSet
from typing import *
from pathlib import Path
from ..__version__ import __version__


@dataclass(frozen=True)
class PkgInfo:
    """PkgInfo contains infomation about a lua library to create LuaLib"""
    # version info
    version: Version
    ffilupa_version: Version = Version(__version__)
    # module location
    module_location: Optional[Path] = None
    # build info (not used)
    sources: Optional[Tuple[str]] = None
    libraries: Optional[Tuple[str]] = None
    include_dirs: Optional[Tuple[str]] = None
    library_dirs: Optional[Tuple[str]] = None
    extra_compile_args: Optional[Tuple[str]] = None
    extra_link_args: Optional[Tuple[str]] = None
    build_time: Optional[datetime] = None
