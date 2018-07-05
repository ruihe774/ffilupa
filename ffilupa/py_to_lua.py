"""module to "push" python object to lua"""


__all__ = ('PushInfo', 'Pusher', 'std_pusher')

import functools
from collections import namedtuple

from .protocol import *
from .py_from_lua import LuaObject, Proxy, unproxy
from .util import *


_PushInfo = namedtuple('_PushInfo', ('runtime', 'L', 'obj', 'kwargs', 'pusher'))
class PushInfo(_PushInfo):
    def with_new_obj(self, new_obj):
        d = self._asdict()
        d['obj'] = new_obj
        return self.__class__(**d)

class Pusher(Registry):
    """class Pusher"""
    @staticmethod
    def _convert_func(func):
        @functools.wraps(func)
        def _(obj, pi):
            return func(pi)
        return _

    @staticmethod
    def _convert_call(func):
        @functools.wraps(func)
        def _(pi):
            return func(pi.obj, pi)
        return _

    def __init__(self):
        super().__init__()
        self._default_func = None
        def fallback(pi):
            if self._default_func is not None:
                return self._default_func(pi)
            else:
                raise TypeError('no pusher registered for type \'' + type(pi.obj).__name__ + '\'')
        self._fallback = fallback
        self._func = functools.singledispatch(self._convert_func(self._fallback))
        self.internal_push = self._convert_call(self._func)

    def __call__(self, runtime, obj, **kwargs):
        """push ``obj`` to lua"""
        with lock_get_state(runtime) as L:
            return self.internal_push(PushInfo(runtime, L, obj, kwargs, self))

    def register_default(self, func):
        """register default pusher"""
        self._default_func = func

    def __setitem__(self, key, value):
        self._func.register(key)(self._convert_func(value))
        super().__setitem__(key, value)

    def __delitem__(self, key):
        raise NotImplementedError('cannot delete a registered pusher')

    def copy(self):
        o = self.__class__()
        o.update(self)
        o.register_default(self._default_func)
        return o


std_pusher = Pusher()

@std_pusher.register_default
def _(pi):
    return pi.pusher.internal_push(pi.with_new_obj(as_is(pi.obj)))

@std_pusher.register(LuaObject)
def _(pi):
    with lock_get_state(pi.obj._runtime) as fr:
        pi.obj._pushobj()
        if fr != pi.L:
            pi.runtime.lib.lua_xmove(fr, pi.L, 1)

@std_pusher.register(bool)
def _(pi):
    pi.runtime.lib.lua_pushboolean(pi.L, int(pi.obj))

@std_pusher.register(int)
def _(pi):
    if pi.runtime.ffi.cast('lua_Integer', pi.obj) == pi.obj:
        pi.runtime.lib.lua_pushinteger(pi.L, pi.obj)
    else:
        return pi.pusher.internal_push(pi.with_new_obj(as_is(pi.obj)))

@std_pusher.register(float)
def _(pi):
    pi.runtime.lib.lua_pushnumber(pi.L, pi.obj)

@std_pusher.register(str)
def _(pi):
    if pi.runtime.encoding is None:
        raise ValueError('encoding not specified')
    else:
        b = pi.obj.encode(pi.runtime.encoding)
        return pi.pusher.internal_push(pi.with_new_obj(b))

@std_pusher.register(bytes)
def _(pi):
    pi.runtime.lib.lua_pushlstring(pi.L, pi.obj, len(pi.obj))

@std_pusher.register(type(None))
def _(pi):
    pi.runtime.lib.lua_pushnil(pi.L)

@std_pusher.register(Py2LuaProtocol)
def _(pi):
    from .metatable import PYOBJ_SIG
    ffi = pi.runtime.ffi
    lib = pi.runtime.lib
    if pi.obj.push_protocol == PushProtocol.Naked:
        obj = pi.obj.obj
    elif callable(pi.obj.push_protocol):
        return pi.obj.push_protocol(pi)
    else:
        obj = pi.obj
    handle = ffi.new_handle(obj)
    ffi.cast('void**', lib.lua_newuserdata(pi.L, ffi.sizeof(handle)))[0] = handle
    if pi.kwargs.get('set_metatable', True):
        pi.runtime.refs.add(handle)
        lib.luaL_setmetatable(pi.L, PYOBJ_SIG)
    return handle

@std_pusher.register(Proxy)
def _(pi):
    return pi.pusher.internal_push(pi.with_new_obj(unproxy(pi.obj)))
