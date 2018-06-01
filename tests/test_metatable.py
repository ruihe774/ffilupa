from collections import OrderedDict
import semantic_version as sv
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
        if sv.Spec('<5.3').match(lua.lualib.version) and name in 'band bor bxor bnot shl shr idiv'.split():
            continue
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


def test_concat():
    o1, o2 = object(), object()
    assert str(o1) + str(o2) == lua.compile('return ({...})[1] .. ({...})[2]')(o1, o2)


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


def test_iter_index_nil():
    l = []
    assert lua._G.pairs(l)[0](l) == None
    l = [1]
    assert lua._G.pairs(l)[0](l) == (0, 1)


def test_tostring():
    class 长者:
        def __str__(self):
            return '苟利国家生死以，岂因祸福避趋之。'

    assert lua.eval('function(o) return tostring(o) end')(长者()) == '苟利国家生死以，岂因祸福避趋之。'


def test_list_index():
    l = [3, 2, 1]
    lua._G.l = l
    assert lua.eval('l[0] == 3')
    assert lua.eval('l[1] == 2')
    assert lua.eval('l[2] == 1')
    assert lua.eval('type(l[2]) == "number"')
    assert lua.eval('type(l[3]) == "nil"')


def test_dict_index():
    d = {
        'YaeSakura': '八重樱',
        b'YaeSakura': '大姐',
        'RaidenMei': '芽衣',
        '布洛妮娅': 'BronyaZaychik',
        '布洛妮娅'.encode(): '板鸭',
        '德丽莎': 'TheresaApocalypse',
    }

    lua._G.d = d
    assert lua.eval('d.YaeSakura == "八重樱"')
    assert lua.eval('d[python.to_bytes("YaeSakura")] == "大姐"')
    assert lua.eval('d.RaidenMei == "芽衣"')
    assert lua.eval('d.aichan == nil')
    assert lua.eval('d["布洛妮娅"] == "BronyaZaychik"')
    assert lua.eval('d[python.to_bytes("布洛妮娅")] == "板鸭"')
    assert lua.eval('d["德丽莎"] == "TheresaApocalypse"')
    assert lua.eval('d["吼姆"] == nil')
    assert lua.eval('python.as_attrgetter(d):pop("布洛妮娅") == "BronyaZaychik"')

    d['布洛妮娅'] = 'BronyaZaychik'
    luaNa = LuaRuntime(autodecode=False)
    luaNa._G.d = d
    assert luaNa.eval('d.YaeSakura == "大姐"')
    assert luaNa.eval('d[python.to_str("YaeSakura")] == "八重樱"')
    assert luaNa.eval('d.RaidenMei == nil')
    assert luaNa.eval('d[python.to_str("RaidenMei")] == "芽衣"')
    assert luaNa.eval('d.aichan == nil')
    assert luaNa.eval('d["布洛妮娅"] == "板鸭"')
    assert luaNa.eval('d[python.to_str("布洛妮娅")] == "BronyaZaychik"')
    assert luaNa.eval('d[python.to_str("德丽莎")] == "TheresaApocalypse"')
    assert luaNa.eval('d["吼姆"] == nil')
    assert luaNa.eval('python.as_attrgetter(d):pop("布洛妮娅") == "板鸭"')


def test_unexpected_protocol():
    lua._G.d = IndexProtocol({'a': 1}, 3)
    with pytest.raises(ValueError):
        lua.eval('d.a')
    with pytest.raises(ValueError):
        lua.execute('d.b = 1')


def test_method_call():
    class Awd:
        def a(self):
            return self
        def b(self, a1):
            return self, a1
        def c(self, a1, *, a2):
            return self, a1, a2
        @staticmethod
        def d():
            return 'awd'
        @staticmethod
        def e(a1):
            return a1
        @staticmethod
        def f(a1, *, a2):
            return a1, a2
        @classmethod
        def g(cls):
            return cls
        @classmethod
        def h(cls, a1):
            return cls, a1
        @classmethod
        def i(cls, a1, *, a2):
            return cls, a1, a2

    awd = Awd()
    lua._G.awd = awd
    lua._G.Awd = Awd
    assert lua.eval('awd:a() == awd')
    assert lua.eval('Awd.a(awd) == awd')
    assert lua.eval('awd.a') == awd.a
    assert lua.eval('Awd.a') == Awd.a
    with pytest.raises(ValueError):
        lua.eval('awd.a(Awd())')
    with pytest.raises(TypeError):
        lua.eval('awd.a()')
    assert lua.execute('local a, b = awd:b(awd); return a == awd and b == awd')
    assert lua.execute('local a, b, c = python.table_arg(awd.c)({1, a2=2}); return a == awd and b == 1 and c == 2')
    assert lua.execute('local a, b, c = python.table_arg(Awd.c)({awd, 1, a2=2}); return a == awd and b == 1 and c == 2')
    assert lua.eval('awd.d() == "awd"')
    assert lua.eval('Awd.d() == "awd"')
    assert lua.eval('awd.e(awd) == awd')
    assert lua.execute('local b, c = python.table_arg(awd.f)({1, a2=2}); return b == 1 and c == 2')
    assert lua.execute('local b, c = python.table_arg(Awd.f)({1, a2=2}); return b == 1 and c == 2')
    assert lua.eval('Awd:g() == Awd')
    assert lua.eval('awd.g() == Awd')
    assert lua.execute('local a, b = Awd:h(Awd); return a == Awd and b == Awd')
    assert lua.execute('local a, b, c = python.table_arg(awd.i)({1, a2=2}); return a == Awd and b == 1 and c == 2')
    assert lua.execute('local a, b, c = python.table_arg(Awd.i)({1, a2=2}); return a == Awd and b == 1 and c == 2')
    assert lua.eval('python.as_is(1):__add__(1) == 2')


def test_dict_newindex():
    d = {
        'YaeSakura': '八重樱',
        b'YaeSakura': '大姐',
        'RaidenMei': '芽衣',
        '布洛妮娅': 'BronyaZaychik',
        '布洛妮娅'.encode(): '板鸭',
        '德丽莎': 'TheresaApocalypse',
    }

    lua._G.d = {}
    lua.execute('d.YaeSakura = "八重樱"')
    lua.execute('d[python.to_bytes("YaeSakura")] = "大姐"')
    lua.execute('d.RaidenMei = "芽衣"')
    lua.execute('d["布洛妮娅"] = "BronyaZaychik"')
    lua.execute('d[python.to_bytes("布洛妮娅")] = "板鸭"')
    lua.execute('d["德丽莎"] = "TheresaApocalypse"')
    assert lua._G.d == d

    luaNa = LuaRuntime(autodecode=False)
    luaNa._G.d = {}
    luaNa.execute('d.YaeSakura = "大姐"')
    luaNa.execute('d[python.to_str("YaeSakura")] = "八重樱"')
    luaNa.execute('d[python.to_str("RaidenMei")] = "芽衣"')
    luaNa.execute('d["布洛妮娅"] = "板鸭"')
    luaNa.execute('d[python.to_str("布洛妮娅")] = "BronyaZaychik"')
    luaNa.execute('d[python.to_str("德丽莎")] = "TheresaApocalypse"')
    assert lua._G.d == d


def test_namedtuple_newindex():
    class tp:
        __slots__ = (
            'YaeSakura',
            'RaidenMei',
            '布洛妮娅',
            '德丽莎',
        )

        def __init__(self, d={}):
            for k, v in d.items():
                setattr(self, k, v)

        def __eq__(self, other):
            for k in self.__class__.__slots__:
                if getattr(self, k) != getattr(other, k):
                    return False
            return True

    d = tp({
        'YaeSakura': '八重樱',
        'RaidenMei': '芽衣',
        '布洛妮娅': 'BronyaZaychik',
        '德丽莎': 'TheresaApocalypse',
    })

    lua._G.d = tp()
    lua.execute('d.YaeSakura = "八重樱"')
    lua.execute('d.RaidenMei = "芽衣"')
    lua.execute('d["布洛妮娅"] = "BronyaZaychik"')
    lua.execute('d["德丽莎"] = "TheresaApocalypse"')
    assert lua._G.d == d

    luaNa = LuaRuntime(autodecode=False)
    luaNa._G.d = tp()
    luaNa.execute('d[python.to_str("YaeSakura")] = "八重樱"')
    luaNa.execute('d[python.to_str("RaidenMei")] = "芽衣"')
    luaNa.execute('d[python.to_str("布洛妮娅")] = "BronyaZaychik"')
    luaNa.execute('d[python.to_str("德丽莎")] = "TheresaApocalypse"')
    assert lua._G.d == d


def test_list_newindex():
    l = [1, 2]
    lua._G.l = l
    lua.execute('l[0] = 3')
    lua.execute('l[1] = 2')
    lua.execute('python.as_attrgetter(l):append(1)')
    with pytest.raises(IndexError):
        lua.execute('l[3] = "awd"')
    assert lua.eval('l[0] == 3')
    assert lua.eval('l[1] == 2')
    assert lua.eval('l[2] == 1')
    assert lua.eval('type(l[2]) == "number"')
    assert lua.eval('type(l[3]) == "nil"')


def test_bad_callback():
    class BadCallback(Py2LuaProtocol):
        def push_protocol(self, pi):
            lib = pi.runtime.lib
            client = lib._get_caller_client()
            pi.runtime.push(as_is(pi.runtime))
            lib.lua_pushcclosure(pi.L, client, 1)
    lua._G.cb = BadCallback(None)
    with pytest.raises(RuntimeError):
        lua.eval('cb()')
