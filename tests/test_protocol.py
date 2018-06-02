import pytest
from ffilupa import *


lua = LuaRuntime()


def test_as_attrgetter():
    assert lua.eval('function(o) return o.eval end')(as_attrgetter(lua)) == lua.eval
    assert lua.eval('python.as_attrgetter(python.runtime).eval') == lua.eval


def test_as_itemgetter():
    assert lua.eval('function(o) return python.as_itemgetter(o)[0] end')(as_attrgetter([2])) == 2


def test_as_is():
    assert lua._G.type(None) == 'nil'
    assert lua._G.type(as_is(None)) == 'userdata'
    assert lua.eval('python.as_is(10):bit_length()') == 4


def test_as_function():
    assert lua._G.type(as_function(lambda: None)) == 'function'
    assert lua.eval('function(f) return f(python.to_list({3, 2, 1})) end')(as_function(lambda l: l[0])) == 3


def test_as_method():
    f = lua.eval('function(o) return o(1, 2) end')
    class Awd:
        def awd(self, *args):
            assert self is awd
            return args[0]
    awd = Awd()
    assert f(awd.awd) == 1
    with pytest.raises(ValueError, match='^wrong instance$'):
        f(as_method(awd.awd))
    assert f(as_method(awd.awd, 1)) == 2


def test_autopackindex():
    assert autopackindex(object()).index_protocol == IndexProtocol.ATTR
    assert autopackindex({}).index_protocol == IndexProtocol.ITEM
    assert autopackindex([]).index_protocol == IndexProtocol.ITEM
