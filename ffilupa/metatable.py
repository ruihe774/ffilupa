import operator
import functools
from collections.abc import *
from .py_from_lua import LuaObject
from .py_to_lua import push
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
        self.init_lib(ffi, lib)
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

def normal_args(func):
    @functools.wraps(func)
    def _(runtime, *args):
        return func(*[arg.pull() for arg in args])
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

@std_metatable.register(b'__call')
def _(runtime, obj, *args):
    return obj.pull(autounpack=False)(*[arg.pull() for arg in args])

@std_metatable.register(b'__index')
def _(runtime, obj, key):
    wrap = obj.pull(autounpack=False)
    ukey = key.pull(autodecode=True)
    bkey = key.pull(autodecode=False)
    if isinstance(wrap, IndexProtocol):
        protocol = wrap.index_protocol
    else:
        protocol = IndexProtocol.ATTR
    obj = obj.pull()
    if protocol == IndexProtocol.ATTR:
        result = getattr(obj, ukey, runtime.nil)
    elif protocol == IndexProtocol.ITEM:
        try:
            result = obj[bkey]
        except (LookupError, TypeError):
            result = obj.get(ukey, runtime.nil)
    else:
        raise ValueError('unexcepted index_protocol {}'.format(protocol))
    if result is runtime.nil:
        return result
    elif hasattr(result.__class__, '__getitem__'):
        return IndexProtocol(result, IndexProtocol.ITEM)
    elif protocol == IndexProtocol.ATTR and callable(result):
        return MethodProtocol(result, obj)
    else:
        return result

@std_metatable.register(b'__newindex')
def _(runtime, obj, key, value):
    wrap = obj.pull(autounpack=False)
    if isinstance(wrap, IndexProtocol):
        protocol = wrap.index_protocol
    else:
        protocol = IndexProtocol.ATTR
    obj = obj.pull()
    value = value.pull()
    if protocol == IndexProtocol.ATTR:
        setattr(obj, key.pull(autodecode=True), value)
    elif protocol == IndexProtocol.ITEM:
        obj[key.pull()] = value
    else:
        raise ValueError('unexcepted index_protocol {}'.format(protocol))

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
        it = iter(obj)
    else:
        it = enumerate(obj)
    got = []
    def nnext(obj, index):
        if isinstance(index, bytes):
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
