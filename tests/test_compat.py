from ffilupa import *


lua = LuaRuntime()


def test_errors_renaming():
    assert LuaErr is LuaError
    assert LuaErrSyntax is LuaSyntaxError


def test_unpacks_lua_table():
    @unpacks_lua_table
    def f(*args, **kwargs):
        return args, kwargs

    assert f('awd', 'dwa') == (('awd', 'dwa'), {})
    assert f('awd') == (('awd',), {})
    assert f(lua.table_from({1: 'arg1', 2: 'arg2', 'awd': 'dwa'})) == (('arg1', 'arg2'), {'awd': 'dwa'})
    lua_nad = LuaRuntime(autodecode=False)
    assert f(lua_nad.table_from({1: 'arg1', 2: 'arg2', 'awd': 'dwa'})) == ((b'arg1', b'arg2'), {'awd': b'dwa'})


def test_unpacks_lua_table_method():
    class Awd:
        @unpacks_lua_table_method
        def f(self, *args, **kwargs):
            return self, args, kwargs

        @classmethod
        @unpacks_lua_table_method
        def c(cls, *args, **kwargs):
            return cls, args, kwargs

        @staticmethod
        @unpacks_lua_table
        def s(*args, **kwargs):
            return args, kwargs

    awd = Awd()
    assert awd.f(lua.table_from({1: 'arg1', 2: 'arg2', 'awd': 'dwa'})) == (awd, ('arg1', 'arg2'), {'awd': 'dwa'})
    assert Awd.f(awd, lua.table_from({1: 'arg1', 2: 'arg2', 'awd': 'dwa'})) == (awd, ('arg1', 'arg2'), {'awd': 'dwa'})
    assert awd.c(lua.table_from({1: 'arg1', 2: 'arg2', 'awd': 'dwa'})) == (Awd, ('arg1', 'arg2'), {'awd': 'dwa'})
    assert Awd.c(lua.table_from({1: 'arg1', 2: 'arg2', 'awd': 'dwa'})) == (Awd, ('arg1', 'arg2'), {'awd': 'dwa'})
    assert awd.s(lua.table_from({1: 'arg1', 2: 'arg2', 'awd': 'dwa'})) == (('arg1', 'arg2'), {'awd': 'dwa'})
    assert Awd.s(lua.table_from({1: 'arg1', 2: 'arg2', 'awd': 'dwa'})) == (('arg1', 'arg2'), {'awd': 'dwa'})


def test_luatype():
    assert lua_type(1) is None
    assert lua_type(lua.table()) == 'table'
