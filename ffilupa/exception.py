from __future__ import absolute_import, unicode_literals
__all__ = (
    'LuaErr',
    'LuaOK',
    'LuaYield',
    'LuaErrRun',
    'LuaErrSyntax',
    'LuaErrMem',
    'LuaErrGCMM',
    'LuaErrErr',
)

import six
if six.PY2:
    import autosuper
from .lua.lib import *


class LuaErr(Exception):
    @staticmethod
    def newerr(status, err_msg, encoding=None):
        if isinstance(err_msg, six.binary_type) and encoding is not None:
            err_msg = err_msg.decode(encoding)
        return {
            LUA_OK: LuaOK,
            LUA_YIELD: LuaYield,
            LUA_ERRRUN: LuaErrRun,
            LUA_ERRSYNTAX: LuaErrSyntax,
            LUA_ERRMEM: LuaErrMem,
            LUA_ERRGCMM: LuaErrGCMM,
            LUA_ERRERR: LuaErrErr,
        }[status](status, err_msg)
    def __init__(self, status, err_msg):
        super().__init__(status, err_msg)
        self.status, self.err_msg = status, err_msg

class LuaOK(LuaErr):
    pass
class LuaYield(LuaErr):
    pass
class LuaErrRun(LuaErr):
    pass
class LuaErrSyntax(LuaErr):
    pass
class LuaErrMem(LuaErr):
    pass
class LuaErrGCMM(LuaErr):
    pass
class LuaErrErr(LuaErr):
    pass
