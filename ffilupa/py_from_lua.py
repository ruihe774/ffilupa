from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('LuaObject', 'pull', 'LuaIter', 'LuaKIter', 'LuaVIter', 'LuaKVIter',
                          'LuaNil',
                          'LuaNumber',
                          'LuaString',
                          'LuaBoolean',
                          'LuaTable',
                          'LuaFunction',
                          'LuaThread',
                          'LuaUserdata')))

from threading import Lock
from functools import partial
import warnings
import six
if six.PY2:
    import autosuper
from kwonly_args import first_kwonly_arg
from .lua.lib import *
from .lua import ffi
from .util import *
from .exception import *
from .py_to_lua import push, PYOBJ_SIG
from .compile import *


@python_2_unicode_compatible
@python_2_bool_compatible
class LuaLimitedObject(CompileHub):
    _compile_lock = Lock()

    def _ref_to_key(self, key):
        self._ref = key

    def _ref_to_index(self, runtime, index):
        with lock_get_state(runtime) as L:
            with assert_stack_balance(L):
                index = lua_absindex(L, index)
                key = ffi.new('char*')
                lua_pushlightuserdata(L, key)
                lua_pushvalue(L, index)
                lua_rawset(L, LUA_REGISTRYINDEX)
                self._ref_to_key(key)

    def __init__(self, runtime, index):
        self._runtime = runtime
        self._ref_to_index(runtime, index)
        if self.__class__._compile_lock.acquire(False):
            try:
                super().__init__(runtime)
            finally:
                self.__class__._compile_lock.release()

    @staticmethod
    def new(runtime, index):
        with lock_get_state(runtime) as L:
            tp = lua_type(L, index)
            return {
                LUA_TNIL: LuaNil,
                LUA_TNUMBER: LuaNumber,
                LUA_TBOOLEAN: LuaBoolean,
                LUA_TSTRING: LuaString,
                LUA_TTABLE: LuaTable,
                LUA_TFUNCTION: LuaFunction,
                LUA_TUSERDATA: LuaUserdata,
                LUA_TTHREAD: LuaThread,
                LUA_TLIGHTUSERDATA: LuaUserdata,
            }[tp](runtime, index)

    def __del__(self):
        key = self._ref
        with lock_get_state(self._runtime) as L:
            if L:
                with assert_stack_balance(L):
                    lua_pushlightuserdata(L, key)
                    lua_pushnil(L)
                    lua_rawset(L, LUA_REGISTRYINDEX)

    def _pushobj(self):
        key = self._ref
        with lock_get_state(self._runtime) as L:
            lua_pushlightuserdata(L, key)
            lua_rawget(L, LUA_REGISTRYINDEX)

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

    @first_kwonly_arg('keep')
    def __call__(self, keep=False, *args):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                oldtop = lua_gettop(L)
                try:
                    self._runtime._pushvar(b'debug', b'traceback')
                    if lua_isfunction(L, -1) or LuaObject.new(self._runtime, -1).getmetafield(b'__call') is not None:
                        errfunc = 1
                    else:
                        lua_pop(L, 1)
                        errfunc = 0
                except TypeError:
                    errfunc = 0
                self._pushobj()
                for obj in args:
                    push(self._runtime, obj)
                status = lua_pcall(L, len(args), LUA_MULTRET, (-len(args) - 2) * errfunc)
                if status != LUA_OK:
                    err_msg = pull(self._runtime, -1)
                    try:
                        stored = self._runtime._exception[1]
                    except (IndexError, TypeError):
                        pass
                    else:
                        if err_msg is stored:
                            self._runtime._reraise_exception()
                    self._runtime._clear_exception()
                    raise LuaErr.newerr(status, err_msg, self._runtime.encoding)
                else:
                    rv = [(LuaObject.new if keep else pull)(self._runtime, i) for i in range(oldtop + 1 + errfunc, lua_gettop(L) + 1)]
                    if len(rv) > 1:
                        return tuple(rv)
                    elif len(rv) == 1:
                        return rv[0]
                    else:
                        return

    def pull(self):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                return pull(self._runtime, -1)

    def getmetafield(self, key):
        if isinstance(key, six.text_type):
            key = key.encode(self._runtime.source_encoding)
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                if luaL_getmetafield(L, -1, key) != LUA_TNIL:
                    return pull(self._runtime, -1)


def _not_impl(func, exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, LuaErrRun):
        err_msg = exc_value.err_msg
        if isinstance(err_msg, six.binary_type):
            lns = err_msg.split(b'\n')
        else:
            lns = err_msg.split('\n')
        if len(lns) == 3:
            return func()
    six.reraise(exc_type, exc_value, exc_traceback)
not_impl = partial(_not_impl, lambda: NotImplemented)
def not_impl_error():
    raise NotImplementedError
not_impl_error = partial(_not_impl, not_impl_error)


class LuaObject(LuaLimitedObject):
    @compile_lua_method("""
        function(self)
            return type(self)
        end
    """, return_hook=lambda name: name.decode('ascii'))
    def typename(self): pass

    _binary_code = """
        function(self, value)
            return self {} value
        end
    """

    @compile_lua_method(_binary_code.format('+'), except_hook=not_impl)
    def __add__(self, obj): pass
    @compile_lua_method(_binary_code.format('-'), except_hook=not_impl)
    def __sub__(self, obj): pass
    @compile_lua_method(_binary_code.format('*'), except_hook=not_impl)
    def __mul__(self, obj): pass
    @compile_lua_method(_binary_code.format('/'), except_hook=not_impl)
    def __truediv__(self, obj): pass
    @compile_lua_method(_binary_code.format('//'), except_hook=not_impl)
    def __floordiv__(self, obj): pass
    @compile_lua_method(_binary_code.format('%'), except_hook=not_impl)
    def __mod__(self, obj): pass
    @compile_lua_method(_binary_code.format('^'), except_hook=not_impl)
    def __pow__(self, obj): pass
    @compile_lua_method(_binary_code.format('&'), except_hook=not_impl)
    def __and__(self, obj): pass
    @compile_lua_method(_binary_code.format('|'), except_hook=not_impl)
    def __or__(self, obj): pass
    @compile_lua_method(_binary_code.format('~'), except_hook=not_impl)
    def __xor__(self, obj): pass
    @compile_lua_method(_binary_code.format('<<'), except_hook=not_impl)
    def __lshift__(self, obj): pass
    @compile_lua_method(_binary_code.format('>>'), except_hook=not_impl)
    def __rshift__(self, obj): pass
    @compile_lua_method(_binary_code.format('=='), except_hook=not_impl)
    def __eq__(self, obj): pass
    @compile_lua_method(_binary_code.format('<'), except_hook=not_impl)
    def __lt__(self, obj): pass
    @compile_lua_method(_binary_code.format('<='), except_hook=not_impl)
    def __le__(self, obj): pass
    @compile_lua_method(_binary_code.format('>'), except_hook=not_impl)
    def __gt__(self, obj): pass
    @compile_lua_method(_binary_code.format('>='), except_hook=not_impl)
    def __ge__(self, obj): pass
    @compile_lua_method(_binary_code.format('~='), except_hook=not_impl)
    def __ne__(self, obj): pass

    _rbinary_code = """
        function(self, value)
            return value {} self
        end
    """

    @compile_lua_method(_rbinary_code.format('+'), except_hook=not_impl)
    def __radd__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('-'), except_hook=not_impl)
    def __rsub__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('*'), except_hook=not_impl)
    def __rmul__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('/'), except_hook=not_impl)
    def __rtruediv__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('//'), except_hook=not_impl)
    def __rfloordiv__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('%'), except_hook=not_impl)
    def __rmod__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('^'), except_hook=not_impl)
    def __rpow__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('&'), except_hook=not_impl)
    def __rand__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('|'), except_hook=not_impl)
    def __ror__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('~'), except_hook=not_impl)
    def __rxor__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('<<'), except_hook=not_impl)
    def __rlshift__(self, obj): pass
    @compile_lua_method(_rbinary_code.format('>>'), except_hook=not_impl)
    def __rrshift__(self, obj): pass

    _unary_code = """
        function(self)
            return {}self
        end
    """

    @compile_lua_method(_unary_code.format('~'), except_hook=not_impl)
    def __invert__(self): pass
    @compile_lua_method(_unary_code.format('-'), except_hook=not_impl)
    def __neg__(self): pass
    @compile_lua_method(_unary_code.format('#'), except_hook=not_impl_error)
    def __len__(self): pass

    @compile_lua_method("""
        function(self, key)
            return self[key]
        end
    """, except_hook=not_impl_error)
    def __getitem__(self, key, keep=False): pass

    @compile_lua_method("""
        function(self, key, value)
            self[key] = value
        end
    """, except_hook=not_impl_error)
    def __setitem__(self, key, value): pass

    @compile_lua_method("""
        function(self, key)
            if type(key) == 'number' then
                table.remove(self, key)
            else
                self[key] = nil
            end
        end
    """, except_hook=not_impl_error)
    def __delitem__(self, key): pass

    def attr_filter(self, name):
        return not (name.startswith('__') and name.endswith('__'))

    def __getattr__(self, name):
        if self.attr_filter(name):
            try:
                edit_mode = object.__getattribute__(self, 'edit_mode')
            except AttributeError:
                edit_mode = True
            if not edit_mode:
                return self[name]
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        if self.attr_filter(name):
            try:
                edit_mode = object.__getattribute__(self, 'edit_mode')
            except AttributeError:
                edit_mode = True
            if not edit_mode:
                try:
                    object.__getattribute__(self, name)
                    has = True
                except AttributeError:
                    has = False
                if not has:
                    self[name] = value
                    return
        object.__setattr__(self, name, value)

    def __delattr__(self, name):
        if self.attr_filter(name):
            try:
                edit_mode = object.__getattribute__(self, 'edit_mode')
            except AttributeError:
                edit_mode = True
            if not edit_mode:
                del self[name]
                return
        object.__delattr__(self, name)

    def keys(self):
        return LuaKIter(self)

    def values(self):
        return LuaVIter(self)

    def items(self):
        return LuaKVIter(self)

    def __init__(self, runtime, index):
        super().__init__(runtime, index)
        self.edit_mode = False

    def __iter__(self):
        warnings.warn('ambiguous iter on {!r}. use keys()/values()/items() instead'.format(self), PendingDeprecationWarning)
        return self.items()


class LuaNil(LuaObject):
    def __init__(self, runtime, index=None):
        if index is None:
            with lock_get_state(runtime) as L:
                with ensure_stack_balance(L):
                    lua_pushnil(L)
                    super().__init__(runtime, -1)
        else:
            super().__init__(runtime, index)
class LuaNumber(LuaObject):
    pass
class LuaString(LuaObject):
    pass
class LuaBoolean(LuaObject):
    pass
class LuaTable(LuaObject):
    pass
class LuaFunction(LuaObject):
    pass
class LuaThread(LuaObject):
    pass
class LuaUserdata(LuaObject):
    pass


class LuaIter(six.Iterator):
    def __init__(self, obj):
        super().__init__()
        self._info = list(obj._runtime._G.pairs(obj, keep=True))

    def __iter__(self):
        return self

    def __next__(self):
        func, obj, index = self._info
        rv = func(obj, index, keep=True)
        if isinstance(rv, LuaLimitedObject):
            raise StopIteration
        key, value = rv
        self._info[2] = key
        return self._filterkv(key.pull(), value.pull())

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
    obj = LuaObject.new(runtime, index)
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
                    luaL_getmetatable(L, PYOBJ_SIG)
                    if lua_rawequal(L, -2, -1):
                        handle = ffi.cast('_py_handle*', lua_touserdata(L, -3))[0]
                        return ffi.from_handle(handle._obj)
        return obj
