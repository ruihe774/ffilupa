from __future__ import absolute_import, unicode_literals, division
import six
import pytest
from ffilupa import *
from ffilupa.py_from_lua import LuaObject
from ffilupa.py_to_lua import push, push_pyobj
from ffilupa.util import ensure_stack_balance, lock_get_state


rt = LuaRuntime()
fixture_tl = """\
@pytest.fixture
def lo{type}_{name}():
    with lock_get_state(rt) as L:
        with ensure_stack_balance(L):
            push(rt, {type}_{name})
            return LuaObject(rt, -1)
"""
binary_tl = """\
def test_{type}_{opname}(lo{type}_a, lo{type}_b):
    assert type(lo{type}_a) is LuaObject
    assert type(lo{type}_b) is LuaObject
    assert lo{type}_a == {type}_a
    assert lo{type}_b == {type}_b
    assert ({type}_a {op} {type}_b) == (lo{type}_a {op} lo{type}_b)
    assert ({type}_a {op} lo{type}_b) == (lo{type}_a {op} {type}_b)
"""
unary_tl = """\
def test_{type}_{opname}(lo{type}_a):
    assert type(lo{type}_a) is LuaObject
    assert lo{type}_a == {type}_a
    assert {op}(lo{type}_a) == {op}({type}_a)
"""

int_a = 666
int_b = 3
exec(fixture_tl.format(type='int', name='a'))
exec(fixture_tl.format(type='int', name='b'))
for opinfo in (\
    ('+', 'add'),
    ('-', 'sub'),
    ('*', 'mul'),
    ('/', 'truediv'),
    ('//', 'floordiv'),
    ('%', 'mod'),
    ('**', 'pow'),
    ('&', 'and'),
    ('|', 'or'),
    ('^', 'xor'),
    ('<<', 'lshift'),
    ('>>', 'rshift'),
    ('==', 'eq'),
    ('<', 'lt'),
    ('<=', 'le'),
    ('>', 'gt'),
    ('>=', 'ge'),
    ('!=', 'ne')):
    exec(binary_tl.format(type='int', op=opinfo[0], opname=opinfo[1]))
for opinfo in (\
    ('~', 'invert'),
    ('-', 'neg')):
    exec(unary_tl.format(type='int', op=opinfo[0], opname=opinfo[1]))

def test_compile_cache(loint_a, loint_b):
    assert loint_a.__add__ is not loint_b.__add__
    assert six.get_method_function(loint_a.__add__) is six.get_method_function(loint_b.__add__)

def test_int_len(loint_a):
    with pytest.raises(LuaErr):
        len(loint_a)

def test_table_len():
    assert len(rt.eval('{1,2,3}')) == 3

def test_table_hash():
    with pytest.raises(TypeError):
        hash(rt.eval('{1,2,3}'))

def test_table_get():
    assert rt.eval('{0,1,2}')[1] == 0
    assert rt.eval('{awd="dwa"}')['awd'] == b'dwa'
    assert rt.eval('{awd="dwa"}')[b'awd'] == b'dwa'
    assert rt.eval('{awd="dwa"}').awd == b'dwa'
    assert rt.eval('{__hash__="dwa"}').__hash__ != b'dwa'
    tb = rt.eval('{edit_mode="dwa"}')
    assert tb.edit_mode == False
    tb.edit_mode = True
    with pytest.raises(AttributeError):
        tb.awd

def test_table_set():
    tb = rt.eval('{}')
    tb['awd'] = 'dwa'
    tb['dwa'] = 'awd'
    tb[1] = 0
    tb[2] = 1
    tb[1.7] = 6.2
    tb[1.4] = 5.3
    assert tb['awd'] == b'dwa'
    assert tb['dwa'] == b'awd'
    assert tb[1] == 0
    assert tb[2] == 1
    assert tb[1.7] == 6.2
    assert tb[1.4] == 5.3
    assert len(tb) == 2
    tb[2] = rt.nil
    assert len(tb) == 1
    assert tb[2] == rt.nil

    tb = rt.eval('{}')
    tb.awd = 'dwa'
    tb.__hash__ = 5
    assert tb.awd == b'dwa'
    assert tb.__hash__ == 5
    assert tb['__hash__'] == None

    tb.edit_mode = True
    tb.awd = b'awd'
    assert tb['awd'] == b'dwa'
    assert tb.awd == b'awd'

def test_table_add():
    with pytest.raises(LuaErr):
        rt.eval('{1,2,3}') + rt.eval('{4,5,6}')

def test_table_convert():
    tb = rt.eval('{}')
    with pytest.raises(ValueError):
        int(tb)
    with pytest.raises(ValueError):
        float(tb)
    with pytest.raises(ValueError):
        str(tb)
    with pytest.raises(ValueError):
        bytes(tb)

def test_str_noencoding():
    lua = LuaRuntime(None)
    push(lua, b'awd')
    with pytest.raises(ValueError):
        str(LuaObject(lua, -1))

def test_nil_debug():
    lua = LuaRuntime()
    del lua._G['debug']['traceback']
    assert lua.eval('1') is 1
    with pytest.raises(LuaErr):
        lua.eval('#awd')
    del lua._G['debug']
    assert lua.eval('1') is 1
    with pytest.raises(LuaErr):
        lua.eval('#awd')

def test_multiple_returnval():
    assert rt.eval('1, 2') == (1, 2)

def test_table_pull():
    tb = rt.eval('{1,2,3}')
    assert tb.pull() == tb

def test_int_pull(loint_a):
    assert loint_a.pull() == int_a
    assert type(loint_a.pull()) is type(int_a)

def test_getmetafield():
    push_pyobj(rt, 1, 1)
    assert callable(LuaObject(rt, -1).getmetafield('__call'))

def test_typename(loint_a):
    assert loint_a.typename() == 'number'
    assert LuaObject.typename(loint_a) == 'number'

def test_repr_cache(loint_a):
    repr(loint_a)

def test_del_attr_item():
    tb = rt.eval('{2,3,4,awd="dwa",__add__="ccc"}')
    del tb[1]
    assert sorted(tb.items(), key=hash) == sorted(((1, 3), (2, 4), (b'awd', b'dwa'), (b'__add__', b'ccc')), key=hash)
    del tb.awd
    assert sorted(tb.items(), key=hash) == sorted(((1, 3), (2, 4), (b'__add__', b'ccc')), key=hash)
    del tb.__add__
    assert sorted(tb.items(), key=hash) == sorted(((1, 3), (2, 4), (b'__add__', b'ccc')), key=hash)
    del tb['__add__']
    assert sorted(tb.items(), key=hash) == sorted(((1, 3), (2, 4)), key=hash)
