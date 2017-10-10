from __future__ import absolute_import, unicode_literals

import operator
import six
from .py_from_lua import LuaObject
from .py_to_lua import push
from .util import *
from .protocol import *
from . import lua


def caller(ffi, lib, L):
    try:
        runtime = unpack(ffi.from_handle(lib.lua_topointer(L, lib.lua_upvalueindex(1))))
        pyobj = unpack(ffi.from_handle(lib.lua_topointer(L, lib.lua_upvalueindex(2))))
        bk = runtime._state
        runtime._state = L
        rv = pyobj(runtime, *[LuaObject.new(runtime, index) for index in range(1, lib.lua_gettop(L) + 1)])
        lib.lua_settop(L, 0)
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
            runtime._state = bk
        except UnboundLocalError:
            pass

PYOBJ_SIG = b'PyObject'

class Metatable(dict):
    def register(self, name):
        def _(func):
            self[name] = func
            return func
        return _

    def init_lib(self, ffi, lib):
        ffi.def_extern('_caller_server')(partial(caller, ffi, lib))

    def init_runtime(self, runtime):
        lib = runtime.lib
        ffi = runtime.ffi
        client = lib._get_caller_client()
        with lock_get_state(runtime) as L:
            with ensure_stack_balance(runtime):
                lib.luaL_newmetatable(L, PYOBJ_SIG)
                for name, func in self.items():
                    lib.lua_pushstring(L, name)
                    push(runtime, as_is(runtime))
                    push(runtime, as_is(func))
                    lib.lua_pushcclosure(L, client, 2)
                    lib.lua_rawset(L, -3)

def unpack(obj):
    if isinstance(obj, LuaObject):
        obj = obj.pull()
    elif isinstance(obj,Py2LuaProtocol):
        obj = obj.obj
    return obj

def normal_args(func):
    @six.wraps(func)
    def _(runtime, *args):
        return func(*map(unpack, args))
    return _

std_metatable = Metatable()

std_metatable.update({
    b'__add': normal_args(operator.add),
    b'__sub': normal_args(operator.sub),
    b'__mul': normal_args(operator.mul),
    b'__div': normal_args(operator.truediv),
    b'__mod': normal_args(operator.mod),
    b'__pow': normal_args(operator.pow),
    b'__unm': normal_args(operator.neg),
    b'__idiv': normal_args(operator.floordiv),
    b'__band': normal_args(operator.and_),
    b'__bor': normal_args(operator.or_),
    b'__bxor': normal_args(operator.xor),
    b'__bnot': normal_args(operator.invert),
    b'__shl': normal_args(operator.lshift),
    b'__shr': normal_args(operator.rshift),
    b'__len': normal_args(len),
    b'__eq': normal_args(operator.eq),
    b'__lt': normal_args(operator.lt),
    b'__le': normal_args(operator.le),
})

std_metatable.init_lib(lua.ffi, lua.lib)
