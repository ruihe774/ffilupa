from __future__ import absolute_import, unicode_literals
__all__ = ('push', 'init_pyobj', 'PYOBJ_SIG')

import operator
from functools import partial
import six
from .util import *
from .lua.lib import *
from .lua import ffi
from .callback import *


def push(runtime, obj, wrapper_none=False):
    from .py_from_lua import LuaObject, pull
    if isinstance(obj, LuaObject):
        if obj._runtime == runtime:
            obj._pushobj(); return
        else:
            newobj = obj.pull()
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
            if obj is None and not wrapper_none:
                lua_pushnil(L); return
    return push_pyobj(runtime, obj)


refs = set()
PYOBJ_SIG = b'_ffilupa.pyobj'
callback_table = {}


def push_pyobj(runtime, obj):
    with lock_get_state(runtime) as L:
        handle = ffi.cast('_py_handle*', lua_newuserdata(L, ffi.sizeof('_py_handle')))[0]
        with assert_stack_balance(L):
            lua_pushstring(L, PYOBJ_SIG)
            lua_gettable(L, LUA_REGISTRYINDEX)
            lua_setmetatable(L, -2)
    if hasattr(obj, '__func__'):
        o_oo = ffi.new_handle(obj)
        obj = obj.__func__
    else:
        o_oo = ffi.NULL
    o_rt = ffi.new_handle(runtime)
    o_obj = ffi.new_handle(obj)
    handle._runtime = o_rt
    handle._obj = o_obj
    handle._origin_obj = o_oo
    refs.add(o_rt)
    refs.add(o_obj)
    refs.add(o_oo)


def callback(func):
    @six.wraps(func)
    def newfunc(L):
        from .py_from_lua import LuaObject
        try:
            with assert_stack_balance(L):
                handle = ffi.cast('_py_handle*', lua_touserdata(L, 1))[0]
                runtime = ffi.from_handle(handle._runtime)
                obj = ffi.from_handle(handle._obj)
                with runtime.lock():
                    args = [LuaObject(runtime, i) for i in range(2, lua_gettop(L) + 1)]
            rv = func(L, handle, runtime, obj, *args)
            with runtime.lock():
                lua_settop(L, 0)
                if not isinstance(rv, tuple):
                    rv = (rv,)
                for v in rv:
                    push(runtime, v)
                return len(rv)
        except BaseException:
            runtime._store_exception()
            return -1
    name, cb = alloc_callback()
    ffi.def_extern(name)(newfunc)
    callback_table[newfunc.__name__] = cb
    return newfunc


def pyobj_operator(func, L, handle, runtime, obj, *args):
    return func(obj, *[arg.pull() for arg in args])


operators = {
    '__add': operator.add,
    '__sub': operator.sub,
    '__mul': operator.mul,
    '__div': operator.truediv,
    '__mod': operator.mod,
    '__pow': operator.pow,
    '__unm': operator.neg,
    '__idiv': operator.floordiv,
    '__band': operator.and_,
    '__bor': operator.or_,
    '__bxor': operator.xor,
    '__bnot': operator.invert,
    '__shl': operator.lshift,
    '__shr': operator.rshift,
    '__len': len,
    '__eq': operator.eq,
    '__lt': operator.lt,
    '__le': operator.le,
    '__call': lambda func, *args: func(*args),
}
mapping = {}
for k, v in operators.items():
    func = partial(pyobj_operator, v)
    func.__name__ = k
    callback(func)
    mapping[k.encode('ascii')] = callback_table[k]


@callback
def __index(L, handle, runtime, obj, key):
    key = key.pull()
    try:
        return obj[key]
    except (LookupError, TypeError):
        try:
            if isinstance(key, six.binary_type):
                return obj[key.decode(runtime.encoding)]
        except (LookupError, TypeError):
            pass


@callback
def __newindex(L, handle, runtime, obj, key, value):
    key, value = key.pull(), value.pull()
    obj[key] = value


@callback
def __gc(L, handle, runtime, obj):
    refs.discard(handle._runtime)
    refs.discard(handle._obj)
    refs.discard(handle._origin_obj)


mapping[b'__index'] = callback_table['__index']
mapping[b'__newindex'] = callback_table['__newindex']
mapping[b'__gc'] = callback_table['__gc']


def init_pyobj(runtime):
    with lock_get_state(runtime) as L:
        with assert_stack_balance(L):
            lua_pushstring(L, PYOBJ_SIG)
            lua_newtable(L)
            for k, v in mapping.items():
                lua_pushstring(L, k)
                lua_pushcfunction(L, v)
                lua_settable(L, -3)
            lua_settable(L, LUA_REGISTRYINDEX)
