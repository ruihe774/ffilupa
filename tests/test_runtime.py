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
