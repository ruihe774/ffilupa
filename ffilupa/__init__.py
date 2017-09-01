from __future__ import absolute_import, unicode_literals

def read_version():
    from os import path
    global __version__
    with open(path.join(path.dirname(__file__), 'version.txt')) as f:
        __version__ = f.read().rstrip()
read_version(); del read_version

from .runtime import *
from .exception import *
from .protocol import *
from .util import unpacks_lua_table, unpacks_lua_table_method

from . import runtime as _rt
from . import exception as _exc
from . import protocol as _prc
__all__ = _rt.__all__ + _exc.__all__ + _prc.__all__ + ('unpacks_lua_table', 'unpacks_lua_table_method')
del _rt; del _exc; del _prc
