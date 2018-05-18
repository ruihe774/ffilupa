"""module to "push" python object to lua"""


__all__ = ('Pusher', 'std_pusher')

import functools

from .protocol import *
from .py_from_lua import LuaObject
from .util import *


class Pusher:
    @staticmethod
    def _convert_func(func):
        @functools.wraps(func)
        def _(obj, runtime, L):
            return func(runtime, L, obj)
        return _

    def __init__(self, default_func):
        self._func = functools.singledispatch(self._convert_func(default_func))

    def register(self, cls):
        def _(func):
            self._func.register(cls)(self._convert_func(func))
        return _

    def __call__(self, runtime, obj):
        with lock_get_state(runtime) as L:
            return self._func(obj, runtime, L)

std_pusher = Pusher(lambda runtime, L, obj: std_pusher._func(as_is(obj), runtime, L))

@std_pusher.register(LuaObject)
def _(runtime, L, obj):
    with lock_get_state(obj._runtime) as fr:
        obj._pushobj()
        if fr != L:
            runtime.lib.lua_xmove(fr, L, 1)

@std_pusher.register(bool)
def _(runtime, L, obj):
    runtime.lib.lua_pushboolean(L, int(obj))

@std_pusher.register(int)
def _(runtime, L, obj):
    if runtime.ffi.cast('lua_Integer', obj) == obj:
        runtime.lib.lua_pushinteger(L, obj)
    else:
        runtime.lib.lua_pushnumber(L, obj)

@std_pusher.register(float)
def _(runtime, L, obj):
    runtime.lib.lua_pushnumber(L, obj)

@std_pusher.register(str)
def _(runtime, L, obj):
    if runtime.encoding is None:
        raise ValueError('encoding not specified')
    else:
        b = obj.encode(runtime.encoding)
        runtime.lib.lua_pushlstring(L, b, len(b))

@std_pusher.register(bytes)
def _(runtime, L, obj):
    runtime.lib.lua_pushlstring(L, obj, len(obj))

@std_pusher.register(type(None))
def _(runtime, L, obj):
    runtime.lib.lua_pushnil(L)

@std_pusher.register(Py2LuaProtocol)
def _(runtime, L, obj):
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
    ffi.cast('void**', lib.lua_newuserdata(L, ffi.sizeof(handle)))[0] = handle
    lib.luaL_setmetatable(L, PYOBJ_SIG)
