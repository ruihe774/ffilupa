from dataclasses import dataclass
import dataclasses
from typing import Tuple, Union, Optional

from packaging.version import Version
from packaging.tags import sys_tags


__all__ = ('BuildOptions', 'support_py_limited_api')


support_py_limited_api = bool(next((tag for tag in sys_tags() if tag.abi == 'abi3'), False))


@dataclass
class BuildOptions:
    version: Version
    sources: Tuple[str, ...] = ()
    include_dirs: Tuple[str, ...] = ()
    define_macros: Tuple[Union[Tuple[str], Tuple[str, Optional[str]]], ...] = ()
    library_dirs: Tuple[str, ...] = ()
    libraries: Tuple[str, ...] = ()
    runtime_library_dirs: Tuple[str, ...] = ()
    extra_objects: Tuple[str, ...] = ()
    extra_compile_args: Tuple[str, ...] = ()
    extra_link_args: Tuple[str, ...] = ()
    export_symbols: Tuple[str, ...] = ()
    depends: Tuple[str, ...] = ()
    language: str = 'c'
    py_limited_api: bool = support_py_limited_api

    def asopts(self):
        d = {k: list(v) if isinstance(v, tuple) else v for k, v in dataclasses.asdict(self).items()}
        del d['version']
        return d
