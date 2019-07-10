import os
from typing import Union


__version__ = '5.0.0.dev1'


def ensure_strpath(path: Union[str, os.PathLike]) -> str:
    """Cast path to str."""
    return path if isinstance(path, str) else path.__fspath__()

