from __future__ import absolute_import, unicode_literals
__all__ = ('LuaObject', 'pull', 'LuaIter', 'LuaKIter', 'LuaVIter', 'LuaKVIter')

from threading import Lock
import six
from .lua.lib import *
from .lua import ffi
from .util import *
from .exception import *
from .py_to_lua import push, PYOBJ_SIG
from .compile import *


@python_2_unicode_compatible
@python_2_bool_compatible
class LuaObject(CompileHub):
    _clock = 0
    _ref_format = '_ffilupa.{}.{}'
    _clock_lock = Lock()
    _compile_lock = Lock()

    @classmethod
    def _peek_key(cls):
        return cls._ref_format.format(cls, cls._clock)

    @classmethod
    def _inc_clock(cls):
        cls._clock += 1

    @classmethod
    def _alloc_key(cls):
        cls._clock_lock.acquire()
        try:
            key = cls._peek_key()
            cls._inc_clock()
            return key
        finally:
            cls._clock_lock.release()

    def _ref_to_key(self, key):
        self._ref = key

    def _ref_to_index(self, runtime, index):
        with lock_get_state(runtime) as L:
            with assert_stack_balance(L):
                index = lua_absindex(L, index)
                key = self.__class__._alloc_key().encode(runtime.source_encoding)
                lua_pushlstring(L, key, len(key))
                lua_pushvalue(L, index)
                lua_settable(L, LUA_REGISTRYINDEX)
                self._ref_to_key(key)

    def __init__(self, runtime, index):
        self._runtime = runtime
        self._ref_to_index(runtime, index)
        if self.__class__._compile_lock.acquire(False):
            try:
                super().__init__(runtime)
            finally:
                self.__class__._compile_lock.release()

    def __del__(self):
        key = self._ref
        with lock_get_state(self._runtime) as L:
            with assert_stack_balance(L):
                lua_pushlstring(L, key, len(key))
                lua_pushnil(L)
                lua_settable(L, LUA_REGISTRYINDEX)

    def _pushobj(self):
        key = self._ref
        with lock_get_state(self._runtime) as L:
            lua_pushlstring(L, key, len(key))
            lua_gettable(L, LUA_REGISTRYINDEX)

    def __int__(self):
        isnum = ffi.new('int*')
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                value = lua_tointegerx(L, -1, isnum)
        isnum = isnum[0]
        if isnum:
            return value
        else:
            raise ValueError('not a integer')

    def __float__(self):
        isnum = ffi.new('int*')
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                value = lua_tonumberx(L, -1, isnum)
        isnum = isnum[0]
        if isnum:
            return value
        else:
            raise ValueError('not a number')

    def __bool__(self):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                return bool(lua_toboolean(L, -1))

    def __bytes__(self):
        sz = ffi.new('size_t*')
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                value = lua_tolstring(L, -1, sz)
                sz = sz[0]
                if value == ffi.NULL:
                    raise ValueError('not a string')
                else:
                    return ffi.unpack(value, sz)

    def __str__(self):
        if self._runtime.encoding is not None:
            return bytes(self).decode(self._runtime.encoding)
        else:
            raise ValueError('encoding not specified')

    def type(self):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                return lua_type(L, -1)

    typename = Compile("""
        function(self)
            return type(self)
        end
    """, return_hook=lambda name: name.decode('ascii'))

    def _arith(self, obj, op):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                push(self._runtime, obj)
                lua_arith(L, op)
                return LuaObject(self._runtime, -1)

    __add__ = lambda self, obj: self._arith(obj, LUA_OPADD)
    __sub__ = lambda self, obj: self._arith(obj, LUA_OPSUB)
    __mul__ = lambda self, obj: self._arith(obj, LUA_OPMUL)
    __truediv__ = lambda self, obj: self._arith(obj, LUA_OPDIV)
    __floordiv__ = lambda self, obj: self._arith(obj, LUA_OPIDIV)
    __mod__ = lambda self, obj: self._arith(obj, LUA_OPMOD)
    __pow__ = lambda self, obj: self._arith(obj, LUA_OPPOW)
    __invert__ = lambda self, obj: self._arith(obj, LUA_OPBNOT)
    __and__ = lambda self, obj: self._arith(obj, LUA_OPBAND)
    __or__ = lambda self, obj: self._arith(obj, LUA_OPBOR)
    __xor__ = lambda self, obj: self._arith(obj, LUA_OPBXOR)
    __lshift__ = lambda self, obj: self._arith(obj, LUA_OPSHL)
    __rshift__ = lambda self, obj: self._arith(obj, LUA_OPSHR)

    def __neg__(self):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                lua_arith(L, LUA_OPUNM)
                return LuaObject(self._runtime, -1)

    def __call__(self, *args):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                oldtop = lua_gettop(L)
                self._runtime._pushvar(b'debug', b'traceback')
                self._pushobj()
                for obj in args:
                    push(self._runtime, obj)
                status = lua_pcall(L, len(args), LUA_MULTRET, -len(args) - 2)
                if status != LUA_OK:
                    self._runtime._reraise_exception()
                    raise LuaError(pull(self._runtime, -1))
                else:
                    rv = [pull(self._runtime, i) for i in range(oldtop + 2, lua_gettop(L) + 1)]
                    if len(rv) > 1:
                        return tuple(rv)
                    elif len(rv) == 1:
                        return rv[0]
                    else:
                        return

    def __len__(self):
        with lock_get_state(self._runtime) as L:
            self._pushobj()
            return luaL_len(L, -1)

    def _cmp(self, obj, op):
        with lock_get_state(self._runtime) as L:
            self._pushobj()
            push(self._runtime, obj)
            return bool(lua_compare(L, -2, -1, op))

    __eq__ = lambda self, obj: self._cmp(obj, LUA_OPEQ)
    __lt__ = lambda self, obj: self._cmp(obj, LUA_OPLT)
    __le__ = lambda self, obj: self._cmp(obj, LUA_OPLE)

    def _gettable(self, key):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                push(self._runtime, key)
                lua_gettable(L, -2)
                return pull(self._runtime, -1)

    def _settable(self, key, value):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                push(self._runtime, key)
                push(self._runtime, value)
                lua_settable(L, -3)

    __getitem__ = _gettable
    __setitem__ = _settable

    def keys(self):
        return LuaKIter(self)

    def values(self):
        return LuaVIter(self)

    def items(self):
        return LuaKVIter(self)

    def pull(self):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                return pull(self._runtime, -1)


class LuaIter(six.Iterator):
    def __init__(self, obj):
        self._obj = obj
        with lock_get_state(obj._runtime) as L:
            with ensure_stack_balance(L):
                lua_pushnil(L)
                self._key = LuaObject(obj._runtime, -1)

    def __iter__(self):
        return self

    def __next__(self):
        with lock_get_state(self._obj._runtime) as L:
            with ensure_stack_balance(L):
                self._obj._pushobj()
                self._key._pushobj()
                if lua_next(L, -2) == 0:
                    raise StopIteration
                else:
                    key = pull(self._obj._runtime, -2)
                    value = pull(self._obj._runtime, -1)
                    self._key = LuaObject(self._obj._runtime, -2)
                    return self._filterkv(key, value)

    def _filterkv(self, key, value):
        raise NotImplementedError


class LuaKIter(LuaIter):
    def _filterkv(self, key, value):
        return key


class LuaVIter(LuaIter):
    def _filterkv(self, key, value):
        return value


class LuaKVIter(LuaIter):
    def _filterkv(self, key, value):
        return key, value


def pull(runtime, index):
    obj = LuaObject(runtime, index)
    tp = obj.type()
    if tp == LUA_TNIL:
        return None
    elif tp == LUA_TNUMBER:
        try:
            return int(obj)
        except ValueError:
            return float(obj)
    elif tp == LUA_TBOOLEAN:
        return bool(obj)
    elif tp == LUA_TSTRING:
        return six.binary_type(obj)
    else:
        with lock_get_state(runtime) as L:
            with ensure_stack_balance(L):
                obj._pushobj()
                if lua_getmetatable(L, -1):
                    lua_pushstring(L, PYOBJ_SIG)
                    lua_gettable(L, LUA_REGISTRYINDEX)
                    if lua_rawequal(L, -2, -1):
                        handle = ffi.cast('_py_handle*', lua_touserdata(L, -3))[0]
                        return ffi.from_handle(handle._origin_obj) if handle._origin_obj != ffi.NULL \
                            else ffi.from_handle(handle._obj)
        return obj
