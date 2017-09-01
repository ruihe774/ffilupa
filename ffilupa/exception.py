from __future__ import absolute_import, unicode_literals
__all__ = ('LuaError', 'LuaSyntaxError')


class LuaError(Exception):
    pass


class LuaSyntaxError(LuaError):
    pass
