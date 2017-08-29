from __future__ import absolute_import, unicode_literals
__all__ = ('assert_stack_balance', 'ensure_stack_balance', 'lock_get_state')

from contextlib import contextmanager
from .lua.lib import *
from .exception import *


@contextmanager
def assert_stack_balance(L):
    oldtop = lua_gettop(L)
    yield
    newtop = lua_gettop(L)
    if oldtop != newtop:
        raise LuaError('stack unbalance: {} elements before, {} elements after'.format(oldtop, newtop))


@contextmanager
def ensure_stack_balance(L):
    with assert_stack_balance(L):
        oldtop = lua_gettop(L)
        yield
        newtop = lua_gettop(L)
        if newtop > oldtop:
            lua_pop(L, newtop - oldtop)


@contextmanager
def lock_get_state(runtime):
    with runtime.lock():
        yield runtime.lua_state
