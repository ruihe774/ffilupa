import pytest
from ffilupa import *
from ffilupa.util import *


lua = LuaRuntime()


def test_assert_stack_balance():
    with lock_get_state(lua) as L:
        with assert_stack_balance(lua):
            pass
        with pytest.raises(AssertionError):
            with assert_stack_balance(lua):
                lua.lib.lua_pushinteger(L, 1)
        lua.lib.lua_settop(L, 0)
        with pytest.raises(AssertionError):
            with assert_stack_balance(lua):
                lua.lib.lua_pushinteger(L, 1)
                raise Exception()
        lua.lib.lua_settop(L, 0)
        with pytest.raises(TypeError):
            with assert_stack_balance(lua):
                raise TypeError()


def test_ensure_stack_balance():
    with lock_get_state(lua) as L:
        with ensure_stack_balance(lua):
            pass
        assert lua.lib.lua_gettop(L) == 0
        with ensure_stack_balance(lua):
            lua.lib.lua_pushinteger(L, 1)
        assert lua.lib.lua_gettop(L) == 0
        with pytest.raises(TypeError):
            with ensure_stack_balance(lua):
                lua.lib.lua_pushinteger(L, 1)
                raise TypeError()
        assert lua.lib.lua_gettop(L) == 0
        with ensure_stack_balance(lua):
            lua.lib.lua_pushinteger(L, 1)
            with pytest.raises(AssertionError):
                with ensure_stack_balance(lua):
                    lua.lib.lua_settop(L, 0)
        assert lua.lib.lua_gettop(L) == 0


def test_lock_get_state():
    with lock_get_state(lua) as L:
        assert L is lua.lua_state


def test_partial():
    assert partial(lambda *args: args, 'awd')('dwa') == ('awd', 'dwa')


def test_NotCopyable():
    import copy
    import pickle
    tb = lua.table()
    with pytest.raises(TypeError, match='^\'ffilupa.runtime.LuaRuntime\' is not copyable$'):
        copy.copy(lua)
    with pytest.raises(TypeError, match='^\'ffilupa.runtime.LuaRuntime\' is not copyable$'):
        copy.deepcopy(lua)
    with pytest.raises(TypeError, match='^\'ffilupa.py_from_lua.LuaTable\' is not copyable$'):
        copy.deepcopy(tb)
    with pytest.raises(Exception):
        pickle.dumps(lua)
    with pytest.raises(Exception):
        pickle.dumps(tb)


def test_reraise():
    # Copyright (c) 2010-2018 Benjamin Peterson
    import sys
    def get_next(tb):
        return tb.tb_next.tb_next
    e = Exception("blah")
    try:
        raise e
    except Exception:
        tp, val, tb = sys.exc_info()
    try:
        reraise(tp, val, tb)
    except Exception:
        tp2, value2, tb2 = sys.exc_info()
        assert tp2 is Exception
        assert value2 is e
        assert tb is get_next(tb2)
    try:
        reraise(tp, val)
    except Exception:
        tp2, value2, tb2 = sys.exc_info()
        assert tp2 is Exception
        assert value2 is e
        assert tb2 is not tb
    try:
        reraise(tp, val, tb2)
    except Exception:
        tp2, value2, tb3 = sys.exc_info()
        assert tp2 is Exception
        assert value2 is e
        assert get_next(tb3) is tb2
    try:
        reraise(tp, None, tb)
    except Exception:
        tp2, value2, tb2 = sys.exc_info()
        assert tp2 is Exception
        assert value2 is not val
        assert isinstance(value2, Exception)
        assert tb is get_next(tb2)
