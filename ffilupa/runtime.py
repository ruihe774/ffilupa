"""core module contains LuaRuntime"""


__all__ = ('LuaRuntime',)

from threading import RLock
from collections.abc import *
from typing import *
import importlib
import functools
import operator
import sys
import os
from .exception import *
from .util import *
from .py_from_lua import *
from .py_to_lua import std_pusher
from .metatable import std_metatable
from .protocol import *
from .lualibs import get_default_lualib
from .compat import unpacks_lua_table


class LockContext:
    """lock context for runtime used in ``with`` statement"""
    def __init__(self, runtime):
        self._runtime = runtime

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        self._runtime.unlock()


class LuaRuntime(NotCopyable):
    """
    LuaRuntime is the wrapper of main thread "lua_State".
    One process can open multiple LuaRuntime instances.
    LuaRuntime is thread-safe.
    """

    def __init__(self, encoding: str = sys.getdefaultencoding(), source_encoding: Optional[str] = None, autodecode: Optional[bool] = None,
                 lualib=None, metatable=std_metatable, pusher=std_pusher, puller=std_puller, lua_state=None, lock=None):
        """
        Init a LuaRuntime instance.
        This will call ``luaL_newstate`` to open a "lua_State"
        and do some init work.

        :param encoding: the encoding to encode and decode lua string
        :param source_encoding: the encoding to encoding lua code
        :param autodecode: whether automatically decode strings returned from lua functions
        :param lualib: the lua lib. Default is the return value of :py:func:`ffilupa.lualibs.get_default_lualib`
        :param metatable: the metatable for python objects. Default is :py:data:`ffilupa.metatable.std_metatable`
        :param pusher: the pusher to push objects to lua. Default is :py:data:`ffilupa.metatable.std_pusher`
        :param puller: the pulled to pull objects from lua. Default is :py:data:`ffilupa.metatable.std_puller`
        """
        super().__init__()
        self.push = lambda obj, **kwargs: pusher(self, obj, **kwargs)
        self.pull = lambda index, **kwargs: puller(self, index, **kwargs)
        self._newlock(lock)
        with self.lock():
            self._exception = None
            self.compile_cache = {}
            self.refs = set()
            self._setencoding(encoding, source_encoding or encoding or sys.getdefaultencoding())
            if autodecode is None:
                autodecode = encoding is not None
            self.autodecode = autodecode
            self._initlua(lualib)
            if lua_state is None:
                self._newstate()
                self._openlibs()
            else:
                self._state = self.ffi.cast('lua_State*', lua_state)
            self._init_metatable(metatable)
            self._init_pylib()
            self._exception = None
            self._nil = LuaNil(self)
            self._G_ = self.globals()
            self._inited = True

    def lock(self):
        """
        Lock the runtime and returns a context manager which
        unlocks the runtime when exiting.
        All operations to the runtime will automatically lock
        the runtime. It's not necessary for common users.
        """
        self._lock.acquire()
        return LockContext(self)

    def unlock(self):
        """
        Unlock the runtime.
        """
        self._lock.release()

    def _newlock(self, lock):
        """make a lock"""
        if lock is None:
            self._lock = RLock()
        else:
            self._lock = lock

    def _newstate(self):
        """open a lua state"""
        self._state = L = self.lib.luaL_newstate()
        if L == self.ffi.NULL:
            raise RuntimeError('"luaL_newstate" returns NULL')

    def _openlibs(self):
        """open lua stdlibs"""
        self.lib.luaL_openlibs(self.lua_state)

    def _init_metatable(self, metatable):
        metatable.init_runtime(self)

    @property
    def lua_state(self):
        """
        The original "lua_State" object. It can be used directly
        in low-level lua APIs. Common users should not get and use it.

        To make it thread-safe, one must lock the runtime before
        doing any operation on the lua state and unlock after.
        Use the helper :py:func:`ffilupa.util.lock_get_state` instead.

        It's recommended to ensure the lua stack unchanged after
        operations. Use the helpers :py:func:`ffilupa.util.assert_stack_balance`
        and :py:func:`ffilupa.util.ensure_stack_balance`.
        """
        return self._state

    def _setencoding(self, encoding, source_encoding):
        """set the encoding"""
        self.encoding = encoding
        self.source_encoding = source_encoding

    def __del__(self):
        """close lua state"""
        if getattr(self, '_inited', False):
            with self.lock():
                if self.lua_state:
                    self.lib.lua_close(self.lua_state)
                    self._state = None

    def _store_exception(self):
        """store the exception raised"""
        self._exception = sys.exc_info()

    def _reraise_exception(self):
        """reraise the exception stored if there is"""
        with self.lock():
            try:
                if self._exception:
                    reraise(*self._exception)
            finally:
                self._clear_exception()

    def _clear_exception(self):
        """clear the stored exception"""
        with self.lock():
            self._exception = None

    def _pushvar(self, *names):
        """push variable with name ``'.'.join(names)`` in lua
        to the top of stack. raise TypeError if some object is
        not indexable in the chain"""
        with lock_get_state(self) as L:
            self.lib.lua_pushglobaltable(L)
            namebuf = []
            for name in names:
                if isinstance(name, str):
                    name = name.encode(self.encoding)
                if not self.lib.lua_istable(L, -1) and not hasmetafield(self, -1, b'__index'):
                    self.lib.lua_pop(L, 1)
                    raise TypeError('\'{}\' is not indexable'.format('.'.join([x.decode(self.encoding) if isinstance(x, bytes) else x for x in namebuf])))
                self.push(name)
                self.lib.lua_gettable(L, -2)
                self.lib.lua_remove(L, -2)
                namebuf.append(name)

    def compile_path(self, pathname):
        """compile lua source file"""
        if not isinstance(pathname, (str, bytes)):
            pathname = str(pathname)
        if isinstance(pathname, str):
            pathname = os.fsencode(pathname)
        with lock_get_state(self) as L:
            with ensure_stack_balance(self):
                status = self.lib.luaL_loadfile(L, pathname)
                obj = self.pull(-1)
                if status != self.lib.LUA_OK:
                    raise LuaErr.new(self, status, obj, self.encoding)
                else:
                    return obj

    def compile(self, code, name=b'=python'):
        """compile lua code"""
        if isinstance(code, str):
            code = code.encode(self.source_encoding)
        with lock_get_state(self) as L:
            with ensure_stack_balance(self):
                status = self.lib.luaL_loadbuffer(L, code, len(code), name)
                obj = self.pull(-1)
                if status != self.lib.LUA_OK:
                    raise LuaErr.new(self, status, obj, self.encoding)
                else:
                    return obj

    def execute(self, code, *args):
        """
        Execute lua source code. This is the same as
        ``compile(code)(*args)``.
        """
        return self.compile(code)(*args)

    def eval(self, code, *args):
        """
        Eval lua expression. This is the same as
        ``execute('return ' + code, *args)``.
        """
        if isinstance(code, bytes):
            code = b'return ' + code
        else:
            code = 'return ' + code
            code = code.encode(self.source_encoding)
        return self.execute(code, *args)

    def globals(self):
        """
        Returns the global table in lua.
        """
        with lock_get_state(self) as L:
            with ensure_stack_balance(self):
                self.lib.lua_pushglobaltable(L)
                return self.pull(-1)

    def table(self, *args, **kwargs):
        """
        Make a lua table. This is the same as
        ``table_from(args, kwargs)``.
        """

        return self.table_from(args, kwargs)

    def table_from(self, *args):
        """
        Make a lua table from ``args``. items in ``args`` are
        Iterable or Mapping or ItemsView.
        Mapping and ItemsView objects are joined and
        entries will be set in the resulting lua table.
        Other Iterable objects are chained and set to the lua
        table with index *starting from 1*.
        """
        lib = self.lib
        narr = nres = 0
        for obj in args:
            if isinstance(obj, (Mapping, ItemsView)):
                nres += operator.length_hint(obj)
            else:
                narr += operator.length_hint(obj)
        with lock_get_state(self) as L:
            with ensure_stack_balance(self):
                lib.lua_createtable(L, narr, nres)
                i = 1
                for obj in args:
                    if isinstance(obj, Mapping):
                        obj = obj.items()
                    if isinstance(obj, ItemsView):
                        for k, v in obj:
                            self.push(k)
                            self.push(v)
                            lib.lua_rawset(L, -3)
                    else:
                        for item in obj:
                            self.push(item)
                            lib.lua_rawseti(L, -2, i)
                            i += 1
                return LuaTable(self, -1)

    def _init_pylib(self):
        """
        This method will be called at init time to setup
        the ``python`` module in lua.
        """
        def keep_return(func):
            @functools.wraps(func)
            def _(*args, **kwargs):
                return as_is(func(*args, **kwargs))
            return _
        pack_table = self.eval('''
            function(tb)
                return function(s, ...)
                    return tb({s}, ...)
                end
            end''')
        def setitem(d, k, v):
            d[k] = v
        def delitem(d, k):
            del d[k]
        def getitem(d, k, *args):
            try:
                return d[k]
            except LookupError:
                if args:
                    return args[0]
                else:
                    reraise(*sys.exc_info())
        self.globals()[b'python'] = self.globals()[b'package'][b'loaded'][b'python'] = self.table_from({
            b'as_attrgetter': as_attrgetter,
            b'as_itemgetter': as_itemgetter,
            b'as_is': as_is,
            b'as_function': as_function,
            b'as_method': as_method,
            b'none': as_is(None),
            b'eval': eval,
            b'builtins': importlib.import_module('builtins'),
            b'next': next,
            b'import_module': importlib.import_module,
            b'table_arg': unpacks_lua_table,
            b'keep_return': keep_return,
            b'to_luaobject': pack_table(lambda o: as_is(o.__getitem__(1, keep=True))),
            b'to_bytes': pack_table(lambda o: as_is(o.__getitem__(1, autodecode=False))),
            b'to_str': pack_table(lambda o, encoding=None: as_is(o.__getitem__(1, autodecode=False) \
                                                             .decode(self.encoding if encoding is None
                                                                        else encoding if isinstance(encoding, str)
                                                                        else encoding.decode(self.encoding)))),
            b'table_keys': lambda o: o.keys(),
            b'table_values': lambda o: o.values(),
            b'table_items': lambda o: o.items(),
            b'to_list': lambda o: list(o.values()),
            b'to_tuple': lambda o: tuple(o.values()),
            b'to_dict': lambda o: dict(o.items()),
            b'to_set': lambda o: set(o.values()),

            b'setattr': setattr,
            b'getattr': getattr,
            b'delattr': delattr,
            b'setitem': setitem,
            b'getitem': getitem,
            b'delitem': delitem,

            b'ffilupa': importlib.import_module(__package__),
            b'runtime': self,
        })

    def require(self, *args, **kwargs):
        """
        The same as ``._G.require()``. Load a lua module.
        """
        return self._G.require(*args, **kwargs)

    @property
    def _G(self):
        """
        The global table in lua.
        """
        return self._G_

    @property
    def nil(self):
        """
        nil value in lua.
        """
        return self._nil

    def _initlua(self, lualib):
        if lualib is None:
            lualib = get_default_lualib()
        self.lualib = lualib
        self.luamod = lualib.import_mod()

    @property
    def lib(self):
        """lib object of CFFI"""
        return self.luamod.lib

    @property
    def ffi(self):
        """ffi object of CFFI"""
        return self.luamod.ffi

    def close(self):
        """close this LuaRuntime"""
        with lock_get_state(self) as L:
            self._state = None
            self.lib.lua_close(L)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class VoidLock:
    def acquire(self, blocking=True, timeout=-1):
        pass

    def release(self):
        pass
