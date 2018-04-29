from ffilupa import *


lua = LuaRuntime()


def test_exception():
    e = LuaErr(lua.lib.LUA_OK, 'awd')
    assert e.status == lua.lib.LUA_OK
    assert e.err_msg == 'awd'
    assert e.args == (lua.lib.LUA_OK, 'awd')
    assert isinstance(LuaErr.new(lua, lua.lib.LUA_OK, 'awd'), LuaOK)
    assert isinstance(LuaErr.new(lua, lua.lib.LUA_YIELD, 'awd'), LuaYield)
    assert isinstance(LuaErr.new(lua, lua.lib.LUA_ERRRUN, 'awd'), LuaErrRun)
    assert isinstance(LuaErr.new(lua, lua.lib.LUA_ERRSYNTAX, 'awd'), LuaErrSyntax)
    assert isinstance(LuaErr.new(lua, lua.lib.LUA_ERRMEM, 'awd'), LuaErrMem)
    assert isinstance(LuaErr.new(lua, lua.lib.LUA_ERRGCMM, 'awd'), LuaErrGCMM)
    assert isinstance(LuaErr.new(lua, lua.lib.LUA_ERRERR, 'awd'), LuaErrErr)
    assert LuaErr.new(lua, lua.lib.LUA_OK, b'awd').err_msg == b'awd'
    assert LuaErr.new(lua, lua.lib.LUA_OK, b'awd', 'ascii').err_msg == 'awd'
    assert repr(LuaErr.new(lua, lua.lib.LUA_OK, 'awd')) == 'LuaOK: status 0\nawd'
    assert str(LuaErr.new(lua, lua.lib.LUA_OK, 'awd')) == 'awd'
