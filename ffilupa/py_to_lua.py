from __future__ import absolute_import, unicode_literals
__all__ = ('push',)


def push(L, obj):
    from .py_from_lua import LuaObject
    if isinstance(obj, LuaObject):
        obj._pushobj()
    else:
        raise NotImplementedError
