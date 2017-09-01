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
        self.edit_mode = False

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

    @compile_lua_method("""
        function(self)
            return type(self)
        end
    """, return_hook=lambda name: name.decode('ascii'))
    def typename(self): pass

    _binary_code = """
        function(a, b)
            return a {} b
        end
    """

    @compile_lua_method(_binary_code.format('+'))
    def __add__(self, obj): pass
    @compile_lua_method(_binary_code.format('-'))
    def __sub__(self, obj): pass
    @compile_lua_method(_binary_code.format('*'))
    def __mul__(self, obj): pass
    @compile_lua_method(_binary_code.format('/'))
    def __truediv__(self, obj): pass
    @compile_lua_method(_binary_code.format('//'))
    def __floordiv__(self, obj): pass
    @compile_lua_method(_binary_code.format('%'))
    def __mod__(self, obj): pass
    @compile_lua_method(_binary_code.format('^'))
    def __pow__(self, obj): pass
    @compile_lua_method(_binary_code.format('&'))
    def __and__(self, obj): pass
    @compile_lua_method(_binary_code.format('|'))
    def __or__(self, obj): pass
    @compile_lua_method(_binary_code.format('~'))
    def __xor__(self, obj): pass
    @compile_lua_method(_binary_code.format('<<'))
    def __lshift__(self, obj): pass
    @compile_lua_method(_binary_code.format('>>'))
    def __rshift__(self, obj): pass
    @compile_lua_method(_binary_code.format('=='))
    def __eq__(self, obj): pass
    @compile_lua_method(_binary_code.format('<'))
    def __lt__(self, obj): pass
    @compile_lua_method(_binary_code.format('<='))
    def __le__(self, obj): pass
    @compile_lua_method(_binary_code.format('>'))
    def __gt__(self, obj): pass
    @compile_lua_method(_binary_code.format('>='))
    def __ge__(self, obj): pass
    @compile_lua_method(_binary_code.format('~='))
    def __ne__(self, obj): pass

    _rbinary_code = """
        function(a, b)
            return b {} a
        end
    """

    @compile_lua_method(_rbinary_code.format('+'))
    def __radd__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('-'))
    def __rsub__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('*'))
    def __rmul__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('/'))
    def __rtruediv__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('//'))
    def __rfloordiv__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('%'))
    def __rmod__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('^'))
    def __rpow__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('&'))
    def __rand__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('|'))
    def __ror__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('~'))
    def __rxor__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('<<'))
    def __rlshift__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('>>'))
    def __rrshift__(self, obj): pass

    _unary_code = """
        function(a)
            return {}a
        end
    """

    @compile_lua_method(_unary_code.format('~'))
    def __invert__(self): pass
    @compile_lua_method(_unary_code.format('-'))
    def __neg__(self): pass
    @compile_lua_method(_unary_code.format('#'))
    def __len__(self): pass

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

    @compile_lua_method("""
        function(a, b)
            return a[b]
        end
    """)
    def __getitem__(self, key): pass

    @compile_lua_method("""
        function(a, b, c)
            a[b] = c
        end
    """)
    def __setitem__(self, key, value): pass

    def __getattr__(self, key):
        try:
            edit_mode = object.__getattribute__(self, 'edit_mode')
        except AttributeError:
            edit_mode = True
        if not edit_mode:
            return self[key]
        return object.__getattribute__(self, key)

    def __setattr__(self, key, value):
        try:
            edit_mode = object.__getattribute__(self, 'edit_mode')
        except AttributeError:
            edit_mode = True
        if not edit_mode:
            try:
                object.__getattribute__(self, key)
                has = True
            except AttributeError:
                has = False
            if not has:
                self[key] = value
                return
        object.__setattr__(self, key, value)

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
