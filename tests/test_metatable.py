from collections import OrderedDict
import pytest
from ffilupa import *


lua = LuaRuntime()


class op:
    def __init__(self, lua_op, py_op=None, m=None):
        if py_op is None:
            py_op = lua_op
        self.lua_op = lua_op
        self.py_op = py_op
        self.method = m

class binary_op(op):
    pass

class unary_op(op):
    pass

ops = {
    'add': binary_op('+', m='__add__'),
    'sub': binary_op('-', m='__sub__'),
    'mul': binary_op('*', m='__mul__'),
    'div': binary_op('/', m='__truediv__'),
    'mod': binary_op('%', m='__mod__'),
    'pow': binary_op('^', '**', m='__pow__'),
    'unm': unary_op('-', m='__neg__'),
    'idiv': binary_op('//', m='__floordiv__'),
    'band': binary_op('&', m='__and__'),
    'bor': binary_op('|', m='__or__'),
    'bxor': binary_op('~', '^', m='__xor__'),
    'bnot': unary_op('~', m='__invert__'),
    'shl': binary_op('<<', m='__lshift__'),
    'shr': binary_op('>>', m='__rshift__'),
    'eq': binary_op('==', m='__eq__'),
    'lt': binary_op('<', m='__lt__'),
    'le': binary_op('<=', m='__le__'),
}

class AcceptAll:
    for name, op in ops.items():
        if isinstance(op, binary_op):
            if name not in ('eq', 'lt', 'le'):
                exec('def {}(self, o): return "{}"'.format(op.method, name))
            else:
                exec('def {}(self, o): return True'.format(op.method, name))
        elif isinstance(op, unary_op):
            exec('def {}(self): return "{}"'.format(op.method, name))

class RefuseAll:
    for name, op in ops.items():
        if isinstance(op, binary_op):
            exec('def {}(self, o): raise TypeError("{}")'.format(op.method, name))
        elif isinstance(op, unary_op):
            exec('def {}(self): raise TypeError("{}")'.format(op.method, name))


def test_simple_operators():
    for name, op in ops.items():
        if isinstance(op, binary_op):
            a, b = AcceptAll(), AcceptAll()
            py_value = eval('a{}b'.format(op.py_op))
            lua._G.a, lua._G.b = a, b
            lua_value = lua.eval('a{}b'.format(op.lua_op))
            assert py_value == lua_value

            a, b = RefuseAll(), RefuseAll()
            with pytest.raises(TypeError, message=name):
                eval('a{}b'.format(op.py_op))
            lua._G.a, lua._G.b = a, b
            with pytest.raises(TypeError, message=name):
                lua.eval('a{}b'.format(op.lua_op))
            status, exception = lua.eval('pcall(function() return a{}b end)'.format(op.lua_op))
            assert status == False
            assert isinstance(exception, TypeError)

        elif isinstance(op, unary_op):
            a = AcceptAll()
            py_value = eval('{}a'.format(op.py_op))
            lua._G.a = a
            lua_value = lua.eval('{}a'.format(op.lua_op))
            assert py_value == lua_value

            a = RefuseAll()
            with pytest.raises(TypeError, message=name):
                eval('{}a'.format(op.py_op))
            lua._G.a = a
            with pytest.raises(TypeError, message=name):
                lua.eval('{}a'.format(op.lua_op))
            status, exception = lua.eval('pcall(function() return {}a end)'.format(op.lua_op))
            assert status == False
            assert isinstance(exception, TypeError)


iter_into_str = lua.eval('''
    function(l)
        local s = ''
        for k, v in pairs(l) do
            s = s .. tostring(k) .. ',' .. tostring(v) .. ';'
        end
        return s
    end
''')


def test_iter_list():
    assert iter_into_str([22, 33, 44, 55]) == '0,22;1,33;2,44;3,55;'
    assert iter_into_str([22, 33, None, 55]) == '0,22;1,33;2,nil;3,55;'


def test_iter_dict():
    d = OrderedDict()
    d['a'] = 22
    d['b'] = 33
    d['c'] = 44
    d['d'] = 55
    assert iter_into_str(d) == 'a,22;b,33;c,44;d,55;'
    d['c'] = None
    assert iter_into_str(d) == 'a,22;b,33;c,nil;d,55;'


def test_iter_dict_view():
    d = OrderedDict()
    d['a'] = 22
    d['b'] = 33
    d['c'] = 44
    d['d'] = 55
    assert iter_into_str(d.items()) == 'a,22;b,33;c,44;d,55;'
    d['c'] = None
    assert iter_into_str(d.items()) == 'a,22;b,33;c,nil;d,55;'


def test_iter_dict_with_binkeys():
    d = OrderedDict()
    d['a'] = 22
    d[b'b'] = 33
    d['c'] = 44
    d[b'd'] = 55
    assert iter_into_str(d) == 'a,22;b,33;c,44;d,55;'
    d['c'] = None
    assert iter_into_str(d) == 'a,22;b,33;c,nil;d,55;'


def test_iter_dict_with_multikeys():
    from collections.abc import ItemsView
    class View:
        def __iter__(self):
            return Iter()

    class Iter:
        def __init__(self):
            self.i = 0
            self.l = (('a', 22), ('b', 33), ('b', 44), ('c', 55))

        def __next__(self):
            i = self.i
            self.i += 1
            try:
                return self.l[i]
            except IndexError:
                raise StopIteration

        def __iter__(self):
            return self

    ItemsView.register(View)
    assert iter_into_str(View()) == 'a,22;b,33;b,44;c,55;'


def test_random_iter_list():
    l = [22, 33, 44, 55]
    f, t, i = lua._G.pairs(l)
    assert f(t, i) == (0, 22)
    assert f(t, 1) == (2, 44)
    assert f(t, 0) == (1, 33)
    assert f(t, 3) == None
    assert f(t, 4) == None
    assert f(t, None) == (0, 22)
    assert f(t, 3) == None
    assert f(t, 1) == (2, 44)


def test_iter_empty_list():
    assert iter_into_str([]) == ''
    l = []
    f, t, i = lua._G.pairs(l)
    assert l is t
    assert f(t, 1) == None
    assert f(t, i) == None
    assert f(t, None) == None
    assert f(t, 1) == None
    assert f(t, None) == None


def test_random_iter_dict():
    d = OrderedDict()
    d['a'] = 22
    d['b'] = 33
    d['c'] = 44
    d['d'] = 55
    f, t, i = lua._G.pairs(d)
    assert f(t, i) == ('a', 22)
    assert f(t, 'b') == ('c', 44)
    assert f(t, 'a') == ('b', 33)
    assert f(t, 'd') == None


def test_random_iter_iterator():
    l = [22, 33, 44, 55]
    f, t, i = lua._G.pairs(iter(l))
    assert f(t, i) == (0, 22)
    assert f(t, 1) == (2, 44)
    assert f(t, 0) == (1, 33)
    assert f(t, 3) == None


def test_bytes_iter():
    d = OrderedDict()
    d['a'] = 22
    d[b'b'] = 33
    d['c'] = 44
    d[b'd'] = 55
    f, t, i = lua._G.pairs(d)
    assert f(t, as_is(b'b')) == ('c', 44)


def test_endecode_fail():
    lua = LuaRuntime(encoding='ascii')
    d = {'苟': 1, '苟'.encode(): 2}
    f, t, i = lua._G.pairs(d)
    with pytest.raises(UnicodeEncodeError):
        f(t, as_is('苟'))
    with pytest.raises(UnicodeDecodeError):
        f(t, as_is('苟'.encode()))


def test_iter_index_nil():
    l = []
    assert lua._G.pairs(l)[0](l) == None
    l = [1]
    assert lua._G.pairs(l)[0](l) == (0, 1)
