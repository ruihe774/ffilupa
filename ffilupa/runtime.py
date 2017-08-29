from __future__ import absolute_import, unicode_literals
__all__ = ('LuaRuntime',)

from threading import RLock
from contextlib import contextmanager
from .lua.lib import *
from .lua import ffi
from .exception import *


class LuaRuntime(object):
    def __init__(self, encoding='utf-8', source_encoding=None):
        self._newlock()
        with self.lock():
            self._setencoding(encoding, source_encoding or encoding or 'utf-8')
            self._newstate()
            self._initstate()

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
            raise LuaError('"luaL_newstate" returns NULL')

    def _initstate(self):
        luaL_openlibs(self.lua_state)

    @property
    def lua_state(self):
        return self._state

    def _setencoding(self, encoding, source_encoding):
        self.encoding = encoding
        self.source_encoding = source_encoding

    def __del__(self):
        with self.lock():
            lua_close(self.lua_state)
