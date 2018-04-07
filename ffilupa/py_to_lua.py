"""module to "push" python object to lua"""


from __future__ import absolute_import, unicode_literals
__all__ = (str('push'),)

import operator
import inspect
from collections import *
from functools import singledispatch
from .util import *
from .protocol import *
from .py_from_lua import LuaObject


def push(runtime, obj):
    """
    Push ``obj`` onto the top of the lua stack of ``runtime``.

    For simple objects typed ``bool``, ``int``, ``float``,
    string type and NoneType, they will be translated to
    native lua type.

    For Py2LuaProtocol objects, the behavior is controlled by themselves.

    For other python objects, they will be wrapped and in lua
    their typename will be "PyObject". The wrapped python object
    still supports many operations because it has a metatable in lua.
    The original python object won't be garbage collected until
    the wrapper in lua is garbage collected.
    """
    with lock_get_state(runtime) as L:
        return _push(obj, runtime, L)

@singledispatch
def _push(obj, runtime, L):
    obj = autopack(obj)
    _push(obj, runtime, L)

@_push.register(LuaObject)
def _(obj, runtime, L):
    with lock_get_state(obj._runtime) as fr:
        obj._pushobj()
        if fr != L:
            runtime.lib.lua_xmove(fr, L, 1)

@_push.register(bool)
def _(obj, runtime, L):
    runtime.lib.lua_pushboolean(L, int(obj))

def _(obj, runtime, L):
    if runtime.ffi.cast('lua_Integer', obj) == obj:
        runtime.lib.lua_pushinteger(L, obj)
    else:
        runtime.lib.lua_pushnumber(L, obj)
_push.register(int)(_)
try:
    _push.register(long)(_)
except NameError:
    pass

@_push.register(float)
def _(obj, runtime, L):
    runtime.lib.lua_pushnumber(L, obj)

@_push.register(str)
def _(obj, runtime, L):
    if runtime.encoding is None:
        raise ValueError('encoding not specified')
    else:
        b = obj.encode(runtime.encoding)
        runtime.lib.lua_pushlstring(L, b, len(b))

@_push.register(bytes)
def _(obj, runtime, L):
    runtime.lib.lua_pushlstring(L, obj, len(obj))

@_push.register(type(None))
def _(obj, runtime, L):
    runtime.lib.lua_pushnil(L)

@_push.register(Py2LuaProtocol)
def _(obj, runtime, L):
    from .metatable import PYOBJ_SIG
    ffi = runtime.ffi
    lib = runtime.lib
    if obj.push_protocol == PushProtocol.Naked:
        obj = obj.obj
    elif callable(obj.push_protocol):
        obj.push_protocol(runtime, L)
        return
    handle = ffi.new_handle(obj)
    runtime.refs.add(handle)
    lib.lua_pushlightuserdata(L, handle)
    lib.luaL_setmetatable(L, PYOBJ_SIG)
