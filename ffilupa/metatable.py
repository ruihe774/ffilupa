"""module contains metatable for PyObject"""
__all__ = ('Metatable', 'std_metatable', 'PYOBJ_SIG',)

import operator
import functools
import itertools
from collections.abc import *
from .py_from_lua import LuaObject
from .util import *
from .protocol import *


def caller(ffi, lib, L):
    try:
        runtime = ffi.from_handle(ffi.cast('void**', lib.lua_topointer(L, lib.lua_upvalueindex(1)))[0])
        pyobj = ffi.from_handle(ffi.cast('void**', lib.lua_topointer(L, lib.lua_upvalueindex(2)))[0])
        bk = runtime._state
        runtime._state = L
        rv = pyobj(runtime, *[LuaObject.new(runtime, index) for index in range(1, lib.lua_gettop(L) + 1)])
        lib.lua_settop(L, 0)
        if not isinstance(rv, tuple):
            rv = (rv,)
        for v in rv:
            runtime.push(v)
        return len(rv)
    except BaseException as e:
        runtime.push(e)
        runtime._store_exception()
        return -1
    finally:
        try:
            runtime._state = bk
        except UnboundLocalError:
            pass

PYOBJ_SIG = b'PyObject'

class Metatable(Registry):
    """class Metatable"""
    @staticmethod
    def init_lib(ffi, lib):
        """prepare lua lib for setting up metatable"""
        ffi.def_extern('_caller_server')(partial(caller, ffi, lib))

    def init_runtime(self, runtime):
        """set up metatable on ``runtime``"""
        lib = runtime.lib
        ffi = runtime.ffi
        self.init_lib(ffi, lib)
        client = lib._get_caller_client()
        with lock_get_state(runtime) as L:
            with ensure_stack_balance(runtime):
                lib.luaL_newmetatable(L, PYOBJ_SIG)
                for name, func in self.items():
                    lib.lua_pushstring(L, name)
                    runtime.push(as_is(runtime))
                    runtime.push(as_is(func))
                    lib.lua_pushcclosure(L, client, 2)
                    lib.lua_rawset(L, -3)

def normal_args(func):
    @functools.wraps(func)
    def _(runtime, *args):
        return func(*[arg.pull() for arg in args])
    return _

def binary_op(func):
    @normal_args
    @functools.wraps(func)
    def _(o1, o2):
        return func(o1, o2)
    return _

def unary_op(func):
    @normal_args
    @functools.wraps(func)
    def _(o1, o2=None):
        return func(o1)
    return _

std_metatable = Metatable()

std_metatable.update({
    b'__add': binary_op(operator.add),
    b'__sub': binary_op(operator.sub),
    b'__mul': binary_op(operator.mul),
    b'__div': binary_op(operator.truediv),
    b'__mod': binary_op(operator.mod),
    b'__pow': binary_op(operator.pow),
    b'__unm': unary_op(operator.neg),
    b'__idiv': binary_op(operator.floordiv),
    b'__band': binary_op(operator.and_),
    b'__bor': binary_op(operator.or_),
    b'__bxor': binary_op(operator.xor),
    b'__bnot': unary_op(operator.invert),
    b'__shl': binary_op(operator.lshift),
    b'__shr': binary_op(operator.rshift),
    b'__len': unary_op(len),
    b'__eq': binary_op(operator.eq),
    b'__lt': binary_op(operator.lt),
    b'__le': binary_op(operator.le),
    b'__concat': binary_op(lambda a, b: str(a) + str(b)),
})

@std_metatable.register(b'__call')
def _(runtime, obj, *args):
    return obj.pull(autounpack=False)(*[arg.pull() for arg in args])

@std_metatable.register(b'__index')
def _(runtime, obj, key):
    wrap = obj.pull(autounpack=False)
    ukey = key.pull(autodecode=True)
    dkey = key.pull()
    obj = obj.pull()
    wrap = wrap if isinstance(wrap, IndexProtocol) else autopackindex(obj)
    protocol = wrap.index_protocol
    if protocol == IndexProtocol.ATTR:
        result = getattr(obj, ukey, runtime.nil)
    elif protocol == IndexProtocol.ITEM:
        try:
            result = obj[dkey]
        except LookupError:
            return runtime.nil
    else:
        raise ValueError('unexpected index_protocol {}'.format(protocol))
    if protocol == IndexProtocol.ATTR and callable(result) and \
            hasattr(result, '__self__') and getattr(result, '__self__') is obj:
        return MethodProtocol(result, obj)
    else:
        return result

@std_metatable.register(b'__newindex')
def _(runtime, obj, key, value):
    wrap = obj.pull(autounpack=False)
    obj = obj.pull()
    wrap = wrap if isinstance(wrap, IndexProtocol) else autopackindex(obj)
    protocol = wrap.index_protocol
    value = value.pull()
    if protocol == IndexProtocol.ATTR:
        setattr(obj, key.pull(autodecode=True), value)
    elif protocol == IndexProtocol.ITEM:
        obj[key.pull()] = value
    else:
        raise ValueError('unexpected index_protocol {}'.format(protocol))

@std_metatable.register(b'__tostring')
def _(runtime, obj):
    return str(obj.pull())

@std_metatable.register(b'__gc')
def _(runtime, obj):
    runtime.refs.discard(obj.pull(keep_handle=True))

@std_metatable.register(b'__pairs')
def _(runtime, obj):
    obj = obj.pull()
    if isinstance(obj, Mapping):
        it = obj.items()
    elif isinstance(obj, ItemsView):
        it = obj
    else:
        it = enumerate(obj)

    it, it2, it_bk = itertools.tee(it, 3)
    started = False
    def next_or_none(it):
        try:
            return next(it)
        except StopIteration:
            return None
    def nnext(o, index=None):
        nonlocal it, it2, it_bk, started
        indexs = [index]
        if isinstance(index, str):
            try:
                indexs.append(index.encode(runtime.encoding))
            except UnicodeEncodeError:
                pass
        elif isinstance(index, bytes):
            try:
                indexs.append(index.decode(runtime.encoding))
            except UnicodeDecodeError:
                pass

        if index == None and not started:
            started = True
            return next_or_none(it)
        else:
            try:
                k, v = next(it2)
            except StopIteration:
                it, it2, it_bk = itertools.tee(it_bk, 3)
                try:
                    k, v = next(it2)
                except StopIteration:
                    return None
            if k in indexs:
                return next_or_none(it)
            else:
                it, it2, it_bk = itertools.tee(it_bk, 3)
                if index == None:
                    return next_or_none(it)
                else:
                    k, v = next(it)
                    while k not in indexs:
                        next(it2)
                        try:
                            k, v = next(it)
                        except StopIteration:
                            return None
                    next(it2)
                    return next_or_none(it)

    return as_function(nnext), obj, None
