import types
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from packaging.version import Version

from ._build_options import support_py_limited_api


@dataclass
class LuaLib:
    name: str
    version: Version
    module_path: Optional[Path] = None
    runtime_library_dirs: Tuple[str, ...] = ()
    py_limited_api: bool = support_py_limited_api

    def __post_init__(self):
        self._mod: Optional[types.ModuleType] = None
