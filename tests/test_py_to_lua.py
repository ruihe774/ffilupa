from ffilupa import *


lua = LuaRuntime()


def test_push_luaobject():
    lua._G.n = lua.nil
    assert lua.eval('type(n)') == 'nil'


def test_push_bool():
    lua._G.b = True
    assert lua.eval('type(b)') == 'boolean'
    assert lua.eval('b == true')
    lua._G.b = False
    assert lua.eval('type(b)') == 'boolean'
    assert lua.eval('b == false')


def test_push_int():
    lua._G.n = 233
    assert lua.eval('type(n)') == 'number'
    assert lua.eval('n == 233')
    lua._G.n = 1 << 70
    assert lua.eval('type(n)') == 'userdata'
    lua.execute('n = n % 100')
    assert lua.eval('type(n)') == 'number'
    assert lua.eval('n == 24')


def test_push_float():
    lua._G.n = 23.3
    assert lua.eval('type(n)') == 'number'
    assert lua.eval('n == 23.3')


def test_push_str():
    lua._G.s = 'awd'
    assert lua.eval('type(s)') == 'string'
    assert lua.eval('s == "awd"')


def test_push_bytes():
    lua._G.b = b'awd\0dwa'
    assert lua.eval('type(b)') == 'string'
    assert lua.eval('b == "awd\\0dwa"')


def test_push_None():
    lua._G.n = None
    assert lua.eval('type(n)') == 'nil'
