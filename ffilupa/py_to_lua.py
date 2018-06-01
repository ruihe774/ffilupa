"""module to "push" python object to lua"""


__all__ = ('Pusher', 'std_pusher')

import functools
import inspect

from .protocol import *
from .py_from_lua import LuaObject
from .util import *


class Pusher(Registry):
    def _convert_func(self, func):
        ins = inspect.getfullargspec(func)
        @functools.wraps(func)
        def _(_, runtime, L, obj, **kwargs):
            original_kwargs = self._kw_store[runtime].copy()
            original_kwargs['self'] = self
            original_kwargs.update(kwargs)
            kwargs = original_kwargs
            if not ins.varkw:
                kwargs = {k: kwargs[k] for k in ins.kwonlyargs if k in kwargs}
            return func(runtime, L, obj, **kwargs)
        return _

    @staticmethod
    def _convert_call(func):
        @functools.wraps(func)
        def _(runtime, L, obj, **kwargs):
            return func(obj, runtime, L, obj, **kwargs)
        return _

    def __init__(self):
        super().__init__()
        self._default_func = None
        def fallback(runtime, L, obj):
            if self._default_func is not None:
                return self._default_func(runtime, L, obj)
            else:
                raise TypeError('no pusher registered for type \'' + type(obj).__name__ + '\'')
        self._fallback = fallback
        self._func = functools.singledispatch(self._convert_func(self._fallback))
        self.internal_push = self._convert_call(self._func)
        self._kw_store = {}

    def __call__(self, runtime, obj, **kwargs):
        try:
            with lock_get_state(runtime) as L:
                self._kw_store[runtime] = kwargs
                return self.internal_push(runtime, L, obj)
        finally:
            try:
                del self._kw_store[runtime]
            except KeyError:
                pass

    def register_default(self, func):
        self._default_func = self._convert_call(self._convert_func(func))

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
def _(runtime, L, obj, *, self):
    return self.internal_push(runtime, L, as_is(obj))

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
def _(runtime, L, obj, *, self):
    if runtime.ffi.cast('lua_Integer', obj) == obj:
        runtime.lib.lua_pushinteger(L, obj)
    else:
        return self.internal_push(runtime, L, as_is(obj))

@std_pusher.register(float)
def _(runtime, L, obj):
    runtime.lib.lua_pushnumber(L, obj)

@std_pusher.register(str)
def _(runtime, L, obj, *, self):
    if runtime.encoding is None:
        raise ValueError('encoding not specified')
    else:
        b = obj.encode(runtime.encoding)
        return self.internal_push(runtime, L, b)

@std_pusher.register(bytes)
def _(runtime, L, obj):
    runtime.lib.lua_pushlstring(L, obj, len(obj))

@std_pusher.register(type(None))
def _(runtime, L, obj):
    runtime.lib.lua_pushnil(L)

@std_pusher.register(Py2LuaProtocol)
def _(runtime, L, obj, *, self, set_metatable=True):
    from .metatable import PYOBJ_SIG
    ffi = runtime.ffi
    lib = runtime.lib
    if obj.push_protocol == PushProtocol.Naked:
        obj = obj.obj
    elif callable(obj.push_protocol):
        kwargs = self._kw_store[runtime].copy()
        kwargs['pusher'] = self
        ins = inspect.getfullargspec(obj.push_protocol)
        if not ins.varkw:
            kwargs = {k: kwargs[k] for k in ins.kwonlyargs if k in kwargs}
        return obj.push_protocol(runtime, L, **kwargs)
    handle = ffi.new_handle(obj)
    ffi.cast('void**', lib.lua_newuserdata(L, ffi.sizeof(handle)))[0] = handle
    if set_metatable:
        runtime.refs.add(handle)
        lib.luaL_setmetatable(L, PYOBJ_SIG)
    return handle
