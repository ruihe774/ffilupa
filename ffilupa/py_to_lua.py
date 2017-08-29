from __future__ import absolute_import, unicode_literals
__all__ = ('push',)

import six
from .util import *
from .lua.lib import *
from .lua import ffi


def push(runtime, obj):
    from .py_from_lua import LuaObject, pull
    if isinstance(obj, LuaObject):
        if obj._runtime == runtime:
            obj._pushobj()
        else:
            with lock_get_state(obj._runtime) as L:
                with ensure_stack_balance(L):
                    obj._pushobj()
                    newobj = pull(obj._runtime, -1)
                    if isinstance(newobj, LuaObject):
                        raise NotImplementedError('transfer non-serializable data between two different lua runtime')
            return push(runtime, newobj)
    else:
        with lock_get_state(runtime) as L:
            if isinstance(obj, bool):
                lua_pushboolean(L, int(obj)); return
            if isinstance(obj, six.integer_types):
                if ffi.cast('lua_Integer', obj) == obj:
                    lua_pushinteger(L, obj); return
                else:
                    obj = float(obj)
            if isinstance(obj, float):
                lua_pushnumber(L, obj); return
            if isinstance(obj, six.text_type):
                if runtime.encoding is None:
                    raise ValueError('encoding not specified')
                else:
                    obj = obj.encode(runtime.encoding)
            if isinstance(obj, six.binary_type):
                lua_pushlstring(L, obj, len(obj)); return
    raise NotImplementedError
