import os
import tempfile
from pathlib import Path
import pytest
from ffilupa import *
from ffilupa.metatable import *
from ffilupa.py_from_lua import *
from ffilupa.py_to_lua import *


lua = LuaRuntime()


def test_init():
    with LuaRuntime(encoding=None) as lua:
        tb = lua.table()
        tb[b'awd'] = b'dwa'
        with pytest.raises(ValueError):
            tb['awd'] = 'dwa'
        with pytest.raises(ValueError):
            tb[b'awd'] = 'dwa'
    with LuaRuntime(encoding='gb18030', autodecode=False) as lua:
        tb = lua.table()
        tb['怪盗'] = '卡莲'
        assert tb['怪盗'] == '卡莲'.encode('gb18030')

    my_metatable = std_metatable.copy()
    @my_metatable.register(b'__add')
    def _(runtime, a, b):
        assert isinstance(runtime, LuaRuntime)
        return 'AwD!'
    with LuaRuntime(metatable=my_metatable) as lua:
        assert lua.eval('python.builtins + python.builtins') == 'AwD!'
    with LuaRuntime() as lua:
        with pytest.raises(TypeError):
            lua.eval('python.builtins + python.builtins')

    my_pusher = std_pusher.copy()
    class Awd:
        pass
    @my_pusher.register(Awd)
    def _(pi):
        return pi.pusher.internal_push(pi.with_new_obj('AwD!'))
    awd = Awd()
    with LuaRuntime(pusher=my_pusher) as lua:
        lua._G.awd = awd
        assert lua._G.awd == 'AwD!'
    with LuaRuntime() as lua:
        lua._G.awd = awd
        assert lua._G.awd is awd

    my_puller = std_puller.copy()
    @my_puller.register('LUA_TSTRING')
    def _(runtime, obj, **kwargs):
        return 'AwD!'
    with LuaRuntime(puller=my_puller) as lua:
        lua._G.awd = 'awd'
        assert lua._G.awd == 'AwD!'
    with LuaRuntime() as lua:
        lua._G.awd = 'awd'
        assert lua._G.awd == 'awd'


def test_compilepath():
    with tempfile.NamedTemporaryFile('w') as f:
        f.write('return "awd"')
        f.flush()
        assert lua.compile_path(f.name)() == 'awd'
        assert lua.compile_path(Path(f.name))() == 'awd'
        assert lua.compile_path(os.fsencode(f.name))() == 'awd'
    with tempfile.NamedTemporaryFile('w') as f:
        f.write('return "awd')
        f.flush()
        with pytest.raises(LuaErrSyntax, match='^' + f.name + ":1: unfinished string near <eof>$"):
            lua.compile_path(f.name)()


def test_compile():
    assert lua.compile('return "awd"')() == 'awd'
    with pytest.raises(LuaErrSyntax, match="^awd:1: unfinished string near <eof>$"):
        lua.compile('return "awd', b'=awd')()


def test_eval():
    assert lua.eval("'awd'") == 'awd'
    assert lua.eval(b"'awd'") == 'awd'


def test_require():
    assert lua.require('python').runtime is lua


def test_as_attrgetter():
    assert lua.eval('python.as_attrgetter(python.to_dict({awd="dwa"})):pop("awd")') == 'dwa'


def test_as_itemgetter():
    assert lua.eval('python.as_itemgetter(python.as_attrgetter(python.to_dict({awd="dwa"}))).awd') == 'dwa'


def test_as_function():
    assert lua.eval('type(python.as_function(python.as_attrgetter))') == 'function'


def test_none():
    assert lua.eval('python.none') is None
    assert lua.eval('type(python.none)') == 'userdata'


def test_eval():
    assert lua.eval('python.eval("b\'awd\'")') == 'awd'


def test_builtins():
    import builtins
    assert lua.eval('python.builtins') is builtins


def test_next():
    lua._G.it = iter([1])
    assert lua.eval('python.next(it)') == 1
    with pytest.raises(StopIteration):
        lua.eval('python.next(it)')


def test_import():
    import sys
    assert lua.eval('python.import_module("sys")') is sys


def test_table_arg():
    def awd(a, b, *, c, d):
        return a * 4 + b * 3 + c * 2 + d
    lua._G.awd = awd
    assert lua.eval('python.table_arg(awd)({3, 4, c=5, d=6})') == 40


def test_keep_return():
    def awd(a, b, *, c=5, d=6):
        return a * 4 + b * 3 + c * 2 + d
    lua._G.awd = awd
    lua.execute('dwa = python.keep_return(awd)(3, 4)')
    assert lua.eval('type(dwa)') == 'userdata'
    assert lua.eval('dwa + 5') == 45
    lua._G.dwa = None
    lua.execute('dwa = python.keep_return(python.table_arg(awd))({3, 4, c=5, d=6})')
    assert lua.eval('type(dwa)') == 'userdata'
    assert lua.eval('dwa + 5') == 45


def test_to_luaobject():
    assert isinstance(lua.eval('python.to_luaobject(1)'), LuaNumber)


def test_to_bytes():
    assert lua.eval('python.to_bytes("awd")') == b"awd"


def test_to_str():
    assert lua.eval('python.to_bytes("稳态")'.encode('gb18030')) == "稳态".encode('gb18030')
    assert lua.eval('python.to_str("稳态", "gb18030")'.encode('gb18030')) == "稳态"
    assert lua.eval('python.to_str("稳态")') == "稳态"
    with LuaRuntime(autodecode=False) as lua_na:
        assert lua_na.eval('python.to_bytes("稳态")'.encode('gb18030')) == "稳态".encode('gb18030')
        assert lua_na.eval('python.to_str("稳态", "gb18030")'.encode('gb18030')) == "稳态"
        assert lua.eval('python.to_str("稳态")') == "稳态"


def test_table_iters():
    from collections import OrderedDict
    lua._G.iter_into_str = lua.eval('''
        function(l)
            local s = ''
            for k, v in pairs(l) do
                s = s .. tostring(k) .. ',' .. tostring(v) .. ';'
            end
            return s
        end
    ''')
    d = OrderedDict()
    d[1] = 2
    d['awd'] = 'dwa'
    d['def'] = 'ccc'
    lua._G.d = d
    assert lua.eval('iter_into_str(python.table_keys(d))') == '0,1;1,awd;2,def;'
    assert lua.eval('iter_into_str(python.table_values(d))') == '0,2;1,dwa;2,ccc;'
    assert lua.eval('iter_into_str(python.table_items(d))') == '1,2;awd,dwa;def,ccc;'


def test_to_list():
    o = lua.eval('python.to_list({2, 2, 3, awd="dwa", def="ccc"})')
    assert o[:3] == [2, 2, 3]
    assert sorted(o[3:]) == sorted('dwa ccc'.split())


def test_to_tuple():
    o = lua.eval('python.to_tuple({2, 2, 3, awd="dwa", def="ccc"})')
    assert o[:3] == (2, 2, 3)
    assert sorted(o[3:]) == sorted('dwa ccc'.split())


def test_to_set():
    assert lua.eval('python.to_set({2, 2, 3, awd="dwa", def="ccc"})') == {2, 3, 'dwa', 'ccc'}


def test_to_dict():
    assert lua.eval('python.to_dict({2, 2, 3, awd="dwa", def="ccc"})') == {1: 2, 2: 2, 3: 3, 'awd': 'dwa', 'def': 'ccc'}


def test_attr_gsd():
    from collections import UserDict
    lua._G.o = UserDict()
    lua.execute('python.setattr(o, "awd", "dwa")')
    assert lua.eval('python.getattr(o, "awd")') == "dwa"
    lua.execute('python.delattr(o, "awd")')
    assert lua.eval('python.getattr(o, "awd", "ccc")') == "ccc"
    with pytest.raises(AttributeError):
        lua.eval('python.getattr(o, "awd")')


def test_item_gsd():
    from collections import UserDict
    lua._G.o = UserDict()
    lua.execute('python.setitem(o, "awd", "dwa")')
    assert lua.eval('python.getitem(o, "awd")') == "dwa"
    lua.execute('python.delitem(o, "awd")')
    assert lua.eval('python.getitem(o, "awd", "ccc")') == "ccc"
    with pytest.raises(KeyError):
        lua.eval('python.getitem(o, "awd")')


def test_ffilupa():
    import ffilupa
    assert lua.eval('python.ffilupa') is ffilupa


def test_runtime():
    assert lua.eval('python.runtime') is lua
