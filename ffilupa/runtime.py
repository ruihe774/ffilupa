"""core module contains LuaRuntime"""


__all__ = ('LuaRuntime',)

from threading import RLock
from collections import Mapping
import importlib
import warnings
import sys
import tempfile
import pathlib
import os
import semantic_version as sv
from .exception import *
from .util import *
from .py_from_lua import *
from .py_to_lua import *
from .metatable import *
from .protocol import *
from .lualibs import get_lualibs


if not hasattr(pathlib.PurePath, '__fspath__'):
    def __fspath__(self):
        return str(self)
    pathlib.PurePath.__fspath__ = __fspath__
    del __fspath__


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
    A instance of LuaRuntime is a lua environment.
    Operations with lua are through LuaRuntime.

    One process can open multiple LuaRuntime instances.
    They are separate, objects can transfer between.

    LuaRuntime is thread-safe because every operation
    on it will acquire a reentrant lock.
    """

    def __init__(self, encoding=sys.getdefaultencoding(), source_encoding=None, autodecode=None, lualib=None):
        """
        Init a LuaRuntime instance.
        This will call ``luaL_newstate`` to open a "lua_State"
        and do some init work.

        ``encoding`` specify which encoding will be used when
        conversation with lua. default is the same as
        ``sys.getdefaultencoding()``. *It cannot be None.*

        ``source_encoding`` specify which encoding will be used
        when pass source code to lua to compile. default is the
        same as ``encoding``.

        I quite recommend to use ascii-compatible encoding for
        both. "utf16", "ucs2" etc are not recommended.

        ``autodecode`` specify whether decode binary to unicode
        when a lua function returns a string value. If it's set
        to True, decoding will be done automatically, otherwise
        the original binary data will be returned. Default is
        True.
        """
        super().__init__()
        self._newlock()
        with self.lock():
            self._exception = None
            self.compile_cache = {}
            self.refs = set()
            self._setencoding(encoding, source_encoding or encoding or sys.getdefaultencoding())
            if autodecode is None:
                autodecode = encoding is not None
            self.autodecode = autodecode
            self._initlua(lualib)
            self._newstate()
            self._initstate()
            self._exception = None
            self.compile_cache = {}
            self._nil = LuaNil(self)
            self._G_ = self.globals()
            self._inited = True

    def lock(self):
        """
        Lock the runtime and returns a context manager which
        unlocks the runtime when ``__exit__`` is called. That
        means it can be used in a "with" statement like this:

        ..
            ## doctest helper
            >>> from ffilupa.runtime import LuaRuntime
            >>> runtime = LuaRuntime()

        ::

            >>> with runtime.lock():
            ...     # now it's locked
            ...     # do some work
            ...     pass
            ...
            >>> # now it's unlocked

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

    def _newlock(self):
        """make a lock"""
        self._lock = RLock()

    def _newstate(self):
        """open a lua state"""
        self._state = L = self.lib.luaL_newstate()
        if L == self.ffi.NULL:
            raise RuntimeError('"luaL_newstate" returns NULL')

    def _initstate(self):
        """open lua stdlibs and register pyobj metatable"""
        self.lib.luaL_openlibs(self.lua_state)
        std_metatable.init_runtime(self)
        self.init_pylib()

    @property
    def lua_state(self):
        """
        The original "lua_State" object. It can be used directly
        in low-level lua APIs. Common users should not get and use it.

        To make it thread-safe, one must lock the runtime before
        doing any operation on the lua state and unlock after.
        To use the helper ``util.lock_get_state`` instead.

        It's recommended to ensure the lua stack unchanged after
        operations. Use the helpers ``util.assert_stack_balance``
        and ``util.ensure_stack_balance``.
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
                push(self, name)
                self.lib.lua_gettable(L, -2)
                self.lib.lua_remove(L, -2)
                namebuf.append(name)

    def _compile_path(self, pathname):
        if isinstance(pathname, PathLike):
            pathname = os.path.abspath(pathname.__fspath__())
        if isinstance(pathname, str):
            pathname = os.fsencode(pathname)
        with lock_get_state(self) as L:
            with ensure_stack_balance(self):
                status = self.lib.luaL_loadfile(L, pathname)
                obj = pull(self, -1)
                if status != self.lib.LUA_OK:
                    raise LuaErr.new(self, status, obj, self.encoding)
                else:
                    return obj

    def _compile_file(self, f):
        original_pos = f.tell()
        fd, name = tempfile.mkstemp()
        encoding = getattr(f, 'encoding', None)
        with os.fdopen(fd, mode=('wb' if encoding is None else 'w'), encoding=encoding) as outf:
            BUF_LEN = 1000 * 4
            while True:
                buf = f.read(BUF_LEN)
                if not buf:
                    break
                outf.write(buf)
            f.seek(original_pos)
            outf.flush()
            return self._compile_path(name)

    def compile(self, code, name=b'=python'):
        """
        Compile lua source code using ``luaL_loadbuffer``,
        returns a lua function if succeed, otherwise raises
        a lua error, commonly it's ``LuaErrSyntax`` if there's
        a syntax error.

        ``code`` is string type, path type or file type,
        the lua source code to compile.
        If it's unicode, it will be encoded with
        ``self.source_encoding``.

        ``name`` is binary type, the name of this code, will
        be used in lua stack traceback and other places.

        The code is treat as function body. Example:

        ..
            ## doctest helper
            >>> from ffilupa.runtime import LuaRuntime
            >>> runtime = LuaRuntime()

        ::

            >>> runtime.compile('return 1 + 2') # doctest: +ELLIPSIS
            <ffilupa.py_from_lua.LuaFunction object at ...>
            >>> runtime.compile('return 1 + 2')()
            3
            >>> runtime.compile('return ...')(1, 2, 3)
            (1, 2, 3)

        """
        if isinstance(code, str):
            code = code.encode(self.source_encoding)
        if not isinstance(code, bytes):
            if isinstance(code, PathLike):
                return self._compile_path(code)
            else:
                return self._compile_file(code)
        with lock_get_state(self) as L:
            with ensure_stack_balance(self):
                status = self.lib.luaL_loadbuffer(L, code, len(code), name)
                obj = pull(self, -1)
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
            code = code.decode(self.source_encoding)
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
                return pull(self, -1)

    def table(self, *args, **kwargs):
        """
        Make a lua table. This is the same as
        ``table_from(args, kwargs)``.
        Example:

        ..
            ## doctest helper
            >>> from ffilupa.runtime import LuaRuntime
            >>> runtime = LuaRuntime()

        ::

            >>> runtime.table(5, 6, 7, awd='dwa')   # doctest: +ELLIPSIS
            <ffilupa.py_from_lua.LuaTable object at ...>
            >>> list(runtime.table(5, 6, 7, awd='dwa').items())
            [(1, 5), (2, 6), (3, 7), ('awd', 'dwa')]

        """

        return self.table_from(args, kwargs)

    def table_from(self, *args):
        """
        Make a lua table from ``args``. items in ``args`` is
        Iterable or Mapping. Mapping objects are joined and
        entries will be set in the resulting lua table.
        Other Iterable objects are chained and set to the lua
        table with index *starting from 1*.
        """
        table = self.eval('{}')
        i = 1
        for obj in args:
            if isinstance(obj, Mapping):
                for k, v in obj.items():
                    table[k] = v
            else:
                for item in obj:
                    table[i] = item
                    i += 1
        return table

    def init_pylib(self):
        """
        This method will be called at init time to setup
        the ``python`` module in lua. You can inherit
        class LuaRuntime and do some special work like
        additional register or reduce registers in this
        method.
        """
        self.globals().python = self.table(
            as_attrgetter=as_attrgetter,
            as_itemgetter=as_itemgetter,
            as_function=as_function,
            none=as_is(None),
            eval=eval,
            builtins=__builtins__,
            next=next,
            import_module=importlib.import_module,
        )

    @deprecate('duplicate. use ``._G.require()`` instead')
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
            lualib = get_lualibs().select_version(sv.Spec('>=5.1,<5.4'))
        self.lualib = lualib
        self.luamod = lualib.import_mod()

    @property
    def lib(self):
        return self.luamod.lib

    @property
    def ffi(self):
        return self.luamod.ffi
