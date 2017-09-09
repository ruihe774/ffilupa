from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('push', 'init_pyobj', 'PYOBJ_SIG')))

import operator
import inspect
from collections import *
import six
from .util import *
from .lua.lib import *
from .lua import ffi
from .callback import *
from .protocol import Py2LuaProtocol


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
    if not isinstance(obj, Py2LuaProtocol):
        obj = Py2LuaProtocol(obj)
    return push_pyobj(runtime, obj.obj, obj.index_protocol)


PYOBJ_SIG = b'_ffilupa.pyobj'
callback_table = {}


def push_pyobj(runtime, obj, index_protocol):
    with lock_get_state(runtime) as L:
        handle = ffi.cast('_py_handle*', lua_newuserdata(L, ffi.sizeof('_py_handle')))[0]
        luaL_setmetatable(L, PYOBJ_SIG)
    o_rt = ffi.new_handle(runtime)
    o_obj = ffi.new_handle(obj)
    handle._runtime = o_rt
    handle._obj = o_obj
    handle._index_protocol = index_protocol
    runtime.refs.add(o_rt)
    runtime.refs.add(o_obj)


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
            if L != runtime.lua_state:
                raise NotImplementedError('callback in different lua state')
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
    func.__name__ = str(k)
    callback(func)
    mapping[k.encode('ascii')] = callback_table[k]


@callback
def __index(L, handle, runtime, obj, key):
    from .py_from_lua import getnil
    key = key.pull()
    if handle._index_protocol == Py2LuaProtocol.ITEM:
        try:
            return obj[key]
        except (LookupError, TypeError):
            try:
                if isinstance(key, six.binary_type):
                    return obj[key.decode(runtime.encoding)]
            except (LookupError, TypeError):
                pass
    elif handle._index_protocol == Py2LuaProtocol.ATTR:
        if isinstance(key, six.binary_type):
            key = key.decode(runtime.encoding)
        obj = getattr(obj, key, None)
        if inspect.ismethod(obj):
            obj = six.get_method_function(obj)
        return obj
    else:
        raise ValueError('unexcepted index_protocol {}'.format(handle._index_protocol))


@callback
def __newindex(L, handle, runtime, obj, key, value):
    key, value = key.pull(), value.pull()
    if handle._index_protocol == Py2LuaProtocol.ITEM:
        obj[key] = value
    elif handle._index_protocol == Py2LuaProtocol.ATTR:
        if isinstance(key, six.binary_type):
            key = key.decode(runtime.encoding)
        setattr(obj, key, value)
    else:
        raise ValueError('unexcepted index_protocol {}'.format(handle._index_protocol))


@callback
def __gc(L, handle, runtime, obj):
    runtime.refs.discard(handle._runtime)
    runtime.refs.discard(handle._obj)


@callback
def __pairs(L, handle, runtime, obj):
    if isinstance(obj, Mapping):
        it = six.iteritems(obj)
    elif isinstance(obj, ItemsView):
        it = iter(obj)
    else:
        it = enumerate(obj)
    got = []
    def nnext(obj, index):
        if isinstance(index, six.binary_type):
            uindex = index.decode(runtime.encoding)
            b = True
        else:
            b = False
        if got and got[-1][0] in ((index,) + ((uindex,) if b else ())) or index == None and not got:
            try:
                got.append(next(it))
                return got[-1]
            except StopIteration:
                return None
        if index == None:
            return got[0]
        marked = False
        for k, v in got:
            if marked:
                return k, v
            elif k == index:
                marked = True
        try:
            while True:
                got.append(next(it))
                if marked:
                    return got[-1]
                if got[-1][0] == index:
                    marked = True
        except StopIteration:
            if b:
                return nnext(obj, uindex)
            else:
                return None
    return nnext, obj, None


mapping[b'__index'] = callback_table['__index']
mapping[b'__newindex'] = callback_table['__newindex']
mapping[b'__gc'] = callback_table['__gc']
mapping[b'__pairs'] = callback_table['__pairs']


def init_pyobj(runtime):
    with lock_get_state(runtime) as L:
        with ensure_stack_balance(L):
            luaL_newmetatable(L, PYOBJ_SIG)
            for k, v in mapping.items():
                lua_pushstring(L, k)
                lua_pushcfunction(L, v)
                lua_rawset(L, -3)
