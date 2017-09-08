from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('LuaRuntime',
           'LUA_GCSTOP',
           'LUA_GCRESTART',
           'LUA_GCCOLLECT',
           'LUA_GCCOUNT',
           'LUA_GCCOUNTB',
           'LUA_GCSTEP',
           'LUA_GCSETPAUSE',
           'LUA_GCSETSTEPMUL',
           'LUA_GCISRUNNING',)))

from threading import RLock
from contextlib import contextmanager
from collections import Mapping
import sys
import six
if six.PY2:
    import autosuper
from .lua.lib import *
from .lua import ffi
from .exception import *
from .util import *
from .py_from_lua import pull, LuaObject, LuaLimitedObject, getnil
from .py_to_lua import push, init_pyobj
from .protocol import *


class LuaRuntime(object):
    def __init__(self, encoding='utf-8', source_encoding=None):
        super().__init__()
        self._newlock()
        with self.lock():
            self._setencoding(encoding, source_encoding or encoding or 'utf-8')
            self._newstate()
            self._initstate()
        self._exception = None
        self.nil = getnil(self)
        self._G = self.globals()

    @contextmanager
    def lock(self):
        self._lock.acquire()
        yield
        self.unlock()

    def unlock(self):
        self._lock.release()

    def _newlock(self):
        self._lock = RLock()

    def _newstate(self):
        self._state = L = luaL_newstate()
        if L == ffi.NULL:
            raise RuntimeError('"luaL_newstate" returns NULL')

    def _initstate(self):
        luaL_openlibs(self.lua_state)
        init_pyobj(self)
        self.init_pylib()

    @property
    def lua_state(self):
        return self._state

    def _setencoding(self, encoding, source_encoding):
        self.encoding = encoding
        self.source_encoding = source_encoding

    def __del__(self):
        with self.lock():
            if self.lua_state:
                lua_close(self.lua_state)
                self._state = ffi.NULL

    def _store_exception(self):
        self._exception = sys.exc_info()

    def _reraise_exception(self):
        with self.lock():
            try:
                if self._exception:
                    six.reraise(*self._exception)
            finally:
                self._exception = None

    def _pushvar(self, *names):
        with lock_get_state(self) as L:
            lua_pushglobaltable(L)
            for name in names:
                with assert_stack_balance(L):
                    obj = LuaLimitedObject(self, -1)
                    if not lua_istable(L, -1) and obj.getmetafield(b'__index') is None:
                        lua_pop(L, 1)
                        raise TypeError('{} is not indexable'.format(repr(obj)))
                    push(self, name)
                    lua_gettable(L, -2)
                    lua_remove(L, -2)

    def compile(self, code, name=b'=python'):
        if isinstance(code, six.text_type):
            code = code.encode(self.source_encoding)
        with lock_get_state(self) as L:
            with ensure_stack_balance(L):
                status = luaL_loadbuffer(L, code, len(code), name)
                obj = pull(self, -1)
                if status != LUA_OK:
                    raise LuaErr.newerr(status, obj, self.encoding)
                else:
                    return obj

    def execute(self, code, *args):
        return self.compile(code)(*args)

    def eval(self, code, *args):
        if isinstance(code, six.binary_type):
            code = code.decode(self.source_encoding)
        code = 'return ' + code
        code = code.encode(self.source_encoding)
        return self.execute(code, *args)

    def globals(self):
        with lock_get_state(self) as L:
            with ensure_stack_balance(L):
                lua_pushglobaltable(L)
                return pull(self, -1)

    def table(self, *args, **kwargs):
        return self.table_from(args, kwargs)

    def table_from(self, *args):
        table = self.eval('{}')
        i = 1
        for obj in args:
            if isinstance(obj, (LuaObject, Mapping)):
                for k, v in obj.items():
                    table[k] = v
            else:
                for item in obj:
                    table[i] = item
                    i += 1
        return table

    def gc(self, what=LUA_GCCOLLECT, data=0):
        with lock_get_state(self) as L:
            return lua_gc(L, what, data)

    def init_pylib(self):
        self.globals().python = self.table(
            as_attrgetter=as_attrgetter,
            as_itemgetter=as_itemgetter,
            none=Py2LuaProtocol(None),
            eval=eval,
            builtins=six.moves.builtins,
        )

    def predel(self):
        self._G = self.nil = self.compile_cache = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if not six.PY34:
            self.predel()
