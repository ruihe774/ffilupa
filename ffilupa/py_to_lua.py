"""module to "push" python object to lua"""


from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('push', 'init_pyobj', 'PYOBJ_SIG')))

import operator
import inspect
from collections import *
import six
from singledispatch import singledispatch
from .util import *
from .lua.lib import *
from .lua import ffi
from .callback import *
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
    obj = as_is(obj)
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

def _(obj, runtime, L):
    if ffi.cast('lua_Integer', obj) == obj:
        lua_pushinteger(L, obj)
    else:
        lua_pushnumber(L, obj)
_push.register(int)(_)
try:
    _push.register(long)(_)
except NameError:
    pass

@_push.register(float)
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


PYOBJ_SIG = b'PyObject'


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

        if index_protocol == Py2LuaProtocol.FUNC:
            lua_pushcclosure(L, caller, 1)


def callback(func):
    @six.wraps(func)
    def newfunc(L):
        locked = False
        try:
            with assert_stack_balance(L):
                upindex = lua_upvalueindex(1)
                if lua_type(L, upindex) == LUA_TNIL:
                    handle = ffi.cast('_py_handle*', lua_touserdata(L, 1))[0]
                    bottom = 2
                else:
                    handle = ffi.cast('_py_handle*', lua_touserdata(L, upindex))[0]
                    bottom = 1
                runtime = ffi.from_handle(handle._runtime)
                obj = ffi.from_handle(handle._obj)
                with runtime.lock():
                    L_bak = runtime._state
                    runtime._state = L
                    args = [LuaObject.new(runtime, i) for i in range(bottom , lua_gettop(L) + 1)]
            rv = func(L, handle, runtime, obj, *args)
            runtime.lock()
            locked = True
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
        finally:
            try:
                runtime._state = L_bak
            except UnboundLocalError:
                pass
            if locked:
                runtime.unlock()
    name, cb = alloc_callback()
    ffi.def_extern(name)(newfunc)
    return cb


class register_metafield(dict):
    def __call__(self, field):
        def wrapper(func):
            self[field] = func
        return wrapper
register_metafield = register_metafield()


def init_metafields():
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
    for k, v in operators.items():
        register_metafield(k.encode('ascii'))(callback(partial(pyobj_operator, v)))

    @register_metafield(b'__index')
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

    @register_metafield(b'__newindex')
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

    @register_metafield(b'__gc')
    @callback
    def __gc(L, handle, runtime, obj):
        runtime.refs.discard(handle._runtime)
        runtime.refs.discard(handle._obj)

    @register_metafield(b'__pairs')
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
        return as_function(nnext), obj, None

    @register_metafield(b'__tostring')
    @callback
    def __tostring(L, handle, runtime, obj):
        return str(obj)

init_metafields()
caller = register_metafield[b'__call']


def init_pyobj(runtime):
    """
    Init the metatable for the wrapped python objects in lua
    for ``runtime``.
    """
    with lock_get_state(runtime) as L:
        with ensure_stack_balance(L):
            luaL_newmetatable(L, PYOBJ_SIG)
            for k, v in register_metafield.items():
                lua_pushstring(L, k)
                lua_pushnil(L)
                lua_pushcclosure(L, v, 1)
                lua_rawset(L, -3)
