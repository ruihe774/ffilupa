from __future__ import absolute_import, unicode_literals
__all__ = ('push',)


def push(runtime, obj):
    from .py_from_lua import LuaObject
    if isinstance(obj, LuaObject):
        if obj._runtime == runtime:
            obj._pushobj()
        else:
            raise NotImplementedError
    else:
        raise NotImplementedError
