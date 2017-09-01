from __future__ import absolute_import, unicode_literals, division
import six
import pytest
from ffilupa import LuaRuntime
from ffilupa.py_from_lua import LuaObject
from ffilupa.py_to_lua import push
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
