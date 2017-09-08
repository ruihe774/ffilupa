from __future__ import unicode_literals

import six

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

def _gen_all():
    global __all__
    if six.PY3:
        from . import runtime as _rt
        from . import exception as _exc
        from . import protocol as _prc
    else:
        import runtime as _rt
        import exception as _exc
        import protocol as _prc
    __all__ = tuple(map(str, _rt.__all__ + _exc.__all__ + _prc.__all__ + ('unpacks_lua_table', 'unpacks_lua_table_method')))
_gen_all()
