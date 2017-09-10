from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('push', 'init_pyobj', 'PYOBJ_SIG')))

import operator
import inspect
import numbers
from collections import *
import six
from singledispatch import singledispatch
from .util import *
from .lua.lib import *
from .lua import ffi
from .callback import *
from .protocol import Py2LuaProtocol
from .py_from_lua import LuaObject


def push(runtime, obj):
    with lock_get_state(runtime) as L:
        return _push(obj, runtime, L)

@singledispatch
def _push(obj, runtime, L):
    obj = Py2LuaProtocol(obj)
    _push(obj, runtime, L)

@_push.register(LuaObject)
def _(obj, runtime, L):
    with lock_get_state(obj._runtime) as fr:
        obj._pushobj()
        if fr != L:
            lua_xmove(fr, L, 1)

@_push.register(bool)
def _(obj, runtime, L):
    lua_pushboolean(L, int(obj))

@_push.register(numbers.Integral)
def _(obj, runtime, L):
    if ffi.cast('lua_Integer', obj) == obj:
        lua_pushinteger(L, obj)
    else:
        lua_pushnumber(L, obj)

@_push.register(numbers.Real)
def _(obj, runtime, L):
    lua_pushnumber(L, obj)

@_push.register(six.text_type)
def _(obj, runtime, L):
    if runtime.encoding is None:
        raise ValueError('encoding not specified')
    else:
        b = obj.encode(runtime.encoding)
        lua_pushlstring(L, b, len(b))

@_push.register(six.binary_type)
def _(obj, runtime, L):
    lua_pushlstring(L, obj, len(obj))

@_push.register(type(None))
def _(obj, runtime, L):
    lua_pushnil(L)

@_push.register(Py2LuaProtocol)
def _(obj, runtime, L):
    push_pyobj(runtime, obj.obj, obj.index_protocol)


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
        try:
            with assert_stack_balance(L):
                handle = ffi.cast('_py_handle*', lua_touserdata(L, 1))[0]
                runtime = ffi.from_handle(handle._runtime)
                obj = ffi.from_handle(handle._obj)
                with runtime.lock():
                    args = [LuaObject.new(runtime, i) for i in range(2, lua_gettop(L) + 1)]
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
        except BaseException as e:
            push(runtime, e)
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
    key = key.pull()
    if handle._index_protocol == Py2LuaProtocol.ITEM:
        try:
            return (obj[key],)
        except (LookupError, TypeError):
            try:
                if isinstance(key, six.binary_type):
                    return (obj[key.decode(runtime.encoding)],)
            except (LookupError, TypeError):
                pass
    elif handle._index_protocol == Py2LuaProtocol.ATTR:
        if isinstance(key, six.binary_type):
            key = key.decode(runtime.encoding)
        obj = getattr(obj, key, None)
        if inspect.ismethod(obj):
            obj = six.get_method_function(obj)
        return (obj,)
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


@callback
def __tostring(L, handle, runtime, obj):
    return str(obj)


mapping[b'__index'] = callback_table['__index']
mapping[b'__newindex'] = callback_table['__newindex']
mapping[b'__gc'] = callback_table['__gc']
mapping[b'__pairs'] = callback_table['__pairs']
mapping[b'__tostring'] = callback_table['__tostring']


def init_pyobj(runtime):
    with lock_get_state(runtime) as L:
        with ensure_stack_balance(L):
            luaL_newmetatable(L, PYOBJ_SIG)
            for k, v in mapping.items():
                lua_pushstring(L, k)
                lua_pushcfunction(L, v)
                lua_rawset(L, -3)
