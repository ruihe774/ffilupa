from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, (
    'getmetafield',
    'hasmetafield',
    'LuaLimitedObject',
    'LuaObject',
    'LuaCollection',
    'LuaCallable',
    'LuaNil',
    'LuaNumber',
    'LuaString',
    'LuaBoolean',
    'LuaTable',
    'LuaFunction',
    'LuaThread',
    'LuaUserdata',
    'LuaView',
    'LuaKView',
    'LuaVView',
    'LuaKVView',
    'LuaIter',
    'LuaKIter',
    'LuaVIter',
    'LuaKVIter',
    'pull',
)))


from threading import Lock
from functools import partial
from collections import *
import six
if six.PY2:
    import autosuper
from kwonly_args import first_kwonly_arg
from .lua.lib import *
from .lua import ffi
from .util import *
from .exception import *
from .compile import *


def getmetafield(runtime, index, key):
    if isinstance(key, six.text_type):
        key = key.encode(runtime.source_encoding)
    with lock_get_state(runtime) as L:
        with ensure_stack_balance(L):
            if luaL_getmetafield(L, index, key) != LUA_TNIL:
                return pull(runtime, -1)

def hasmetafield(runtime, index, key):
    return getmetafield(runtime, index, key) is not None


@python_2_bool_compatible
class LuaLimitedObject(CompileHub, NotCopyable):
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

    def __bool__(self):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                return bool(lua_toboolean(L, -1))

    def _type(self):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                return lua_type(L, -1)

    def pull(self):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                return pull(self._runtime, -1)


def not_impl(func, exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, LuaErrRun):
        err_msg = exc_value.err_msg
        if isinstance(err_msg, six.binary_type):
            lns = err_msg.split(b'\n')
        else:
            lns = err_msg.split('\n')
        if len(lns) == 3:
            return NotImplemented
    six.reraise(exc_type, exc_value, exc_traceback)


_binary_code = """
    function(self, value)
        return self {} value
    end
"""
_rbinary_code = """
    function(self, value)
        return value {} self
    end
"""
_unary_code = """
    function(self)
        return {}self
    end
"""


@python_2_unicode_compatible
class LuaObject(LuaLimitedObject):
    @compile_lua_method("""
        function(self)
            return type(self)
        end
    """, return_hook=lambda name: name.decode('ascii') if isinstance(name, six.binary_type) else name)
    def typename(self): pass

    @compile_lua_method(_binary_code.format('+'), except_hook=not_impl)
    def __add__(self, value): pass
    @compile_lua_method(_binary_code.format('-'), except_hook=not_impl)
    def __sub__(self, value): pass
    @compile_lua_method(_binary_code.format('*'), except_hook=not_impl)
    def __mul__(self, value): pass
    @compile_lua_method(_binary_code.format('/'), except_hook=not_impl)
    def __truediv__(self, value): pass
    @compile_lua_method(_binary_code.format('//'), except_hook=not_impl)
    def __floordiv__(self, value): pass
    @compile_lua_method(_binary_code.format('%'), except_hook=not_impl)
    def __mod__(self, value): pass
    @compile_lua_method(_binary_code.format('^'), except_hook=not_impl)
    def __pow__(self, value): pass
    @compile_lua_method(_binary_code.format('&'), except_hook=not_impl)
    def __and__(self, value): pass
    @compile_lua_method(_binary_code.format('|'), except_hook=not_impl)
    def __or__(self, value): pass
    @compile_lua_method(_binary_code.format('~'), except_hook=not_impl)
    def __xor__(self, value): pass
    @compile_lua_method(_binary_code.format('<<'), except_hook=not_impl)
    def __lshift__(self, value): pass
    @compile_lua_method(_binary_code.format('>>'), except_hook=not_impl)
    def __rshift__(self, value): pass
    @compile_lua_method(_binary_code.format('=='), except_hook=not_impl)
    def __eq__(self, value): pass
    @compile_lua_method(_binary_code.format('<'), except_hook=not_impl)
    def __lt__(self, value): pass
    @compile_lua_method(_binary_code.format('<='), except_hook=not_impl)
    def __le__(self, value): pass
    @compile_lua_method(_binary_code.format('>'), except_hook=not_impl)
    def __gt__(self, value): pass
    @compile_lua_method(_binary_code.format('>='), except_hook=not_impl)
    def __ge__(self, value): pass
    @compile_lua_method(_binary_code.format('~='), except_hook=not_impl)
    def __ne__(self, value): pass

    @compile_lua_method(_rbinary_code.format('+'), except_hook=not_impl)
    def __radd__(self, value): pass
    @compile_lua_method(_rbinary_code.format('-'), except_hook=not_impl)
    def __rsub__(self, value): pass
    @compile_lua_method(_rbinary_code.format('*'), except_hook=not_impl)
    def __rmul__(self, value): pass
    @compile_lua_method(_rbinary_code.format('/'), except_hook=not_impl)
    def __rtruediv__(self, value): pass
    @compile_lua_method(_rbinary_code.format('//'), except_hook=not_impl)
    def __rfloordiv__(self, value): pass
    @compile_lua_method(_rbinary_code.format('%'), except_hook=not_impl)
    def __rmod__(self, value): pass
    @compile_lua_method(_rbinary_code.format('^'), except_hook=not_impl)
    def __rpow__(self, value): pass
    @compile_lua_method(_rbinary_code.format('&'), except_hook=not_impl)
    def __rand__(self, value): pass
    @compile_lua_method(_rbinary_code.format('|'), except_hook=not_impl)
    def __ror__(self, value): pass
    @compile_lua_method(_rbinary_code.format('~'), except_hook=not_impl)
    def __rxor__(self, value): pass
    @compile_lua_method(_rbinary_code.format('<<'), except_hook=not_impl)
    def __rlshift__(self, value): pass
    @compile_lua_method(_rbinary_code.format('>>'), except_hook=not_impl)
    def __rrshift__(self, value): pass

    @compile_lua_method(_unary_code.format('~'), except_hook=not_impl)
    def __invert__(self): pass
    @compile_lua_method(_unary_code.format('-'), except_hook=not_impl)
    def __neg__(self): pass

    def __init__(self, runtime, index):
        super().__init__(runtime, index)
        self.edit_mode = False

    @compile_lua_method('tostring')
    def _tostring(self, autodecode=False): pass

    def __bytes__(self):
        return self._tostring(autodecode=False)

    def __str__(self):
        if self._runtime.encoding is not None:
            return six.binary_type(self).decode(self._runtime.encoding)
        else:
            raise ValueError('encoding not specified')


class LuaCollection(LuaObject):
    @compile_lua_method(_unary_code.format('#'))
    def __len__(self): pass

    @compile_lua_method("""
        function(self, name)
            return self[name]
        end
    """)
    def __getitem__(self, name, keep=False): pass

    @compile_lua_method("""
        function(self, name, value)
            self[name] = value
        end
    """)
    def __setitem__(self, name, value): pass

    @compile_lua_method("""
        function(self, name)
            if type(name) == 'number' then
                table.remove(self, name)
            else
                self[name] = nil
            end
        end
    """)
    def __delitem__(self, name): pass

    def attr_filter(self, name):
        return not (name.startswith('__') and name.endswith('__')) and \
               self.__dict__.get('edit_mode', True) is False and \
               name not in self.__dict__

    def __getattr__(self, name):
        if self.attr_filter(name):
            return self[name]
        else:
            return self.__getattribute__(name)

    def __setattr__(self, name, value):
        if self.attr_filter(name):
            self[name] = value
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name):
        if self.attr_filter(name):
            del self[name]
        else:
            super().__delattr__(name)

    def keys(self):
        return LuaKView(self)

    def values(self):
        return LuaVView(self)

    def items(self):
        return LuaKVView(self)

    @pending_deprecate('ambiguous iter. use keys()/values()/items() instead')
    def __iter__(self):
        return iter(self.keys())

MutableMapping.register(LuaCollection)


class LuaCallable(LuaObject):
    @first_kwonly_arg('keep')
    def __call__(self, keep=False, autodecode=None, *args):
        from .py_to_lua import push
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                oldtop = lua_gettop(L)
                try:
                    self._runtime._pushvar(b'debug', b'traceback')
                    if lua_isfunction(L, -1) or hasmetafield(self._runtime, -1, b'__call'):
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
                    rv = [pull(self._runtime, i, keep=keep, autodecode=autodecode) for i in range(oldtop + 1 + errfunc, lua_gettop(L) + 1)]
                    if len(rv) > 1:
                        return tuple(rv)
                    elif len(rv) == 1:
                        return rv[0]
                    else:
                        return


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
            raise TypeError('not a integer')

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
            raise TypeError('not a number')


class LuaString(LuaObject):
    def __bytes__(self):
        sz = ffi.new('size_t*')
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                value = lua_tolstring(L, -1, sz)
                sz = sz[0]
                if value == ffi.NULL:
                    raise TypeError('not a string')
                else:
                    return ffi.unpack(value, sz)

    if six.PY2:
        __str__ = __bytes__
        del __bytes__


class LuaBoolean(LuaObject):
    pass


class LuaTable(LuaCollection):
    pass


class LuaFunction(LuaCallable):
    def coroutine(self, *args, **kwargs):
        rv = self._runtime._G.coroutine.create(self)
        rv._first = [args, kwargs]
        return rv


@python_2_bool_compatible
class LuaThread(LuaObject, six.Iterator):
    def send(self, *args, **kwargs):
        with self._runtime.lock():
            if not self:
                raise StopIteration
            rv = self._runtime._G.coroutine.resume(self, *args, **kwargs)
            if rv is True:
                rv = (rv,)
            if rv[0]:
                rv = rv[1:]
                if len(rv) > 1:
                    return rv
                elif len(rv) == 1:
                    return rv[0]
                else:
                    if not self:
                        raise StopIteration
                    return
            else:
                try:
                    stored = self._runtime._exception[1]
                except (IndexError, TypeError):
                    pass
                else:
                    if rv[1] is stored:
                        self._runtime._reraise_exception()
                self._runtime._clear_exception()
                raise LuaErr.newerr(None, rv[1], self._runtime.encoding)

    def __next__(self):
        a, k = self._first
        rv = self.send(*a, **k)
        self._first[0] = ()
        return rv

    def __init__(self, runtime, index):
        self._first = [(), {}]
        super().__init__(runtime, index)
        with lock_get_state(runtime) as L:
            with ensure_stack_balance(L):
                self._pushobj()
                thread = lua_tothread(L, -1)
                if lua_status(thread) == LUA_OK and lua_gettop(thread) == 1:
                    lua_pushvalue(thread, 1)
                    lua_xmove(thread, L, 1)
                    self._func = LuaObject.new(runtime, -1)
                else:
                    self._func = None

    def __iter__(self):
        return self

    def __call__(self, *args, **kwargs):
        if self._func is None:
            raise RuntimeError('original function not found')
        newthread = self._runtime._G.coroutine.create(self._func)
        newthread._first = [args, kwargs]
        return newthread

    def status(self):
        return self._runtime._G.coroutine.status(self, autodecode=False).decode('ascii')

    def __bool__(self):
        return self.status() != 'dead'


class LuaUserdata(LuaCollection, LuaCallable):
    pass


class LuaView(object):
    def __init__(self, obj):
        self._obj = obj

    def __len__(self):
        return len(self._obj)

    def __iter__(self):
        raise NotImplementedError


class LuaKView(LuaView):
    def __iter__(self):
        return LuaKIter(self._obj)

KeysView.register(LuaKView)


class LuaVView(LuaView):
    def __iter__(self):
        return LuaVIter(self._obj)

ValuesView.register(LuaVView)


class LuaKVView(LuaView):
    def __iter__(self):
        return LuaKVIter(self._obj)

ItemsView.register(LuaKVView)


class LuaIter(six.Iterator):
    def __init__(self, obj):
        super().__init__()
        self._info = list(obj._runtime._G.pairs(obj, keep=True))

    def __iter__(self):
        return self

    def __next__(self):
        _, obj, _ = self._info
        with obj._runtime.lock():
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


@first_kwonly_arg('keep')
def pull(runtime, index, keep=False, autodecode=None):
    from .py_to_lua import PYOBJ_SIG
    obj = LuaObject.new(runtime, index)
    if keep:
        return obj
    tp = obj._type()
    if tp == LUA_TNIL:
        return None
    elif tp == LUA_TNUMBER:
        try:
            return int(obj)
        except TypeError:
            return float(obj)
    elif tp == LUA_TBOOLEAN:
        return bool(obj)
    elif tp == LUA_TSTRING:
        return (six.text_type if (autodecode if autodecode is not None else runtime.autodecode) else six.binary_type)(obj)
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
