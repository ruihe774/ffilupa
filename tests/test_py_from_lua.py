from collections.abc import *
import pytest
from ffilupa import *
from ffilupa.py_from_lua import *


lua = LuaRuntime()


def test_LuaObject_operators():
    a = lua._G.python.to_luaobject(22)
    b = lua._G.python.to_luaobject(3)
    c = 22
    d = 3
    assert a.typename() == 'number'
    assert b.typename() == 'number'
    assert int(a) is c
    assert int(b) is d
    for op in '+ - * / // % ** & | ^ << >> == < <= > >= !='.split():
        exec('assert (a{0}b) == (c{0}d)'.format(op))
        exec('assert (a{0}d) == (c{0}d)'.format(op))
        exec('assert (c{0}b) == (c{0}d)'.format(op))
    for op in '- ~'.split():
        exec('assert {0}a == {0}c'.format(op))


def test_not_impl():
    with pytest.raises(TypeError, message='unsupported operand type(s) for +: \'LuaObject\' and \'LuaObject\''):
        lua.table() + lua.table()
    class R:
        def __radd__(self, other):
            return 'Awd!'
    tb = lua.table()
    r = R()
    assert tb + r == 'Awd!'

    lua_ne = LuaRuntime(encoding=None)
    with pytest.raises(TypeError, message=b'unsupported operand type(s) for +: \'LuaObject\' and \'LuaObject\''):
        lua_ne.table() + lua_ne.table()


def test_bytes():
    assert bytes(lua.table()).startswith(b'table: ')


def test_str():
    assert str(lua.table()).startswith('table: ')
    lua_ne = LuaRuntime(encoding=None)
    assert bytes(lua.table()).startswith(b'table: ')
    with pytest.raises(ValueError):
        str(lua_ne.table())


def test_table_operators():
    tb = lua.table()

    assert tb.第六夜想曲 == None
    assert tb['第六夜想曲'] == None
    tb.第六夜想曲 = '幽色咏叹调'
    assert tb.第六夜想曲 == '幽色咏叹调'
    assert tb['第六夜想曲'] == '幽色咏叹调'
    del tb.第六夜想曲
    assert tb.第六夜想曲 == None
    assert tb['第六夜想曲'] == None

    assert tb.第六夜想曲 == None
    assert tb['第六夜想曲'] == None
    tb['第六夜想曲'] = '幽色咏叹调'
    assert tb.第六夜想曲 == '幽色咏叹调'
    assert tb['第六夜想曲'] == '幽色咏叹调'
    del tb['第六夜想曲']
    assert tb.第六夜想曲 == None
    assert tb['第六夜想曲'] == None

    tb.__dict__['edit_mode'] = True
    tb.卡莲 = '卡斯兰娜'
    tb.__dict__['edit_mode'] = False
    assert tb.卡莲 == '卡斯兰娜'
    assert tb['卡莲'] == None
    del tb.卡莲
    assert tb.卡莲 == None
    assert tb['卡莲'] == None

    tb.__dict__['edit_mode'] = True
    tb.卡莲 = '卡斯兰娜'
    assert tb.卡莲 == '卡斯兰娜'
    assert tb['卡莲'] == None
    del tb.卡莲
    with pytest.raises(AttributeError): tb.卡莲
    assert tb['卡莲'] == None
    tb.__dict__['edit_mode'] = False

    import itertools
    tb.clear()
    tb.update(dict(zip(itertools.count(1), 'the quick brown fox jumps over the lazy doges'.split())))
    del tb[3]
    assert list(tb.items()) == list(zip(itertools.count(1), 'the quick fox jumps over the lazy doges'.split()))


def test_table_iter_and_abc():
    tb = lua.table(
        the='quick',
        brown='fox',
        jumps='over',
        lazy='doges',
    )

    assert isinstance(tb, MutableMapping)
    it = iter(tb)
    assert isinstance(it, Iterator)
    assert sorted(it) == sorted('the brown jumps lazy'.split())
    it = tb.keys()
    assert isinstance(it, KeysView)
    assert sorted(it) == sorted('the brown jumps lazy'.split())
    it = tb.values()
    assert isinstance(it, ValuesView)
    assert sorted(it) == sorted('quick fox over doges'.split())
    it = tb.items()
    assert isinstance(it, ItemsView)
    assert sorted(it) == sorted(zip('the brown jumps lazy'.split(), 'quick fox over doges'.split()))
    assert 'lazy' in tb
    assert 'dog' not in tb


def test_traceback_nil():
    f = lua.eval('function() return "awd" end')
    g = lua.eval('function() error("awd") end')
    tb = lua._G.debug.traceback
    lua._G.debug.traceback = None
    assert f() == 'awd'
    with pytest.raises(LuaErrRun, message='awd'):
        g()
    db = lua._G.debug
    lua._G.debug = None
    assert f() == 'awd'
    with pytest.raises(LuaErrRun, message='awd'):
        g()
    lua._G.debug = db
    lua._G.debug.traceback = tb


def test_lua_number():
    i = lua._G.python.to_luaobject(1)
    f = lua._G.python.to_luaobject(1.1)
    assert int(i) == 1
    assert float(i) == 1.0
    with pytest.raises(TypeError, message='not a integer'):
        int(f)
    assert float(f) == 1.1


def test_lua_string():
    s = lua._G.python.to_luaobject(b'the quick brown fox jumps over the lazy doges'.replace(b' ', b'\0'))
    assert bytes(s) == b'the quick brown fox jumps over the lazy doges'.replace(b' ', b'\0')


def test_lua_thread():
    f = lua.execute('''
        function h(a, b)
            while true do
                a, b = coroutine.yield(a + b, a - b)
            end
        end
        local co = coroutine.create(h)
        function g(a, b)
            local r0, r1, r2 = coroutine.resume(co, a, b)
            return coroutine.yield(r1, r2)
        end
        function f(a, b)
            for i = 1, 5 do
                a, b = g(a, b)
            end
        end
        return f
    ''')
    def pyf(a, b):
        while True:
            a, b = yield a + b, a - b
    pyf = pyf(5, 4)
    co = f.coroutine(5, 4)
    assert next(co) == (9, 1)
    co = co(5, 4)
    assert co.send() == (9, 1)
    co = co(5, 4)
    assert co.send(None) == (9, 1)
    co = co(5, 4)
    with pytest.raises(TypeError, message="can't send non-None value to a just-started generator"):
        co.send('awd')
    co = co(5, 4)
    with pytest.raises(TypeError, message="can't send non-None value to a just-started generator"):
        co.send(**{'awd': 'dwa'})
    co = co(5, 4)
    assert next(co) == next(pyf)
    assert isinstance(co, Generator)
    assert co.status() == 'suspended'
    assert bool(co) is True
    assert co.send(50, 60) == pyf.send((50, 60))
    assert co.status() == 'suspended'
    assert bool(co) is True
    with pytest.raises(Exception, message='awd'):
        co.throw(None, Exception('awd'))
    assert co.status() == 'dead'
    assert bool(co) is False
    co = co(1, 2)
    assert next(co) == (3, -1)
    assert co.send(2, 3) == (5, -1)
    assert co.send(3, 4) == (7, -1)
    assert co.send(4, 5) == (9, -1)
    assert co.send(5, 6) == (11, -1)
    with pytest.raises(StopIteration):
        co.send(6, 7)
    assert co.status() == 'dead'
    assert bool(co) is False


def test_ListProxy():
    tb = lua.table(22, 33, 44, 55, aa='bb', cc='dd')
    assert len(tb) == 6
    assert tb.array_len() == 4
    l = ListProxy(tb)
    assert unproxy(l) is tb
    assert len(l) == 4
    assert l[0] == 22
    assert l[1] == 33
    assert l[2] == 44
    assert l[3] == 55
    with pytest.raises(IndexError, message='list index out of range'):
        l[4]
    assert l[-1] == 55
    assert l[-2] == 44
    assert l[-3] == 33
    assert l[-4] == 22
    with pytest.raises(IndexError, message='list index out of range'):
        l[-5]
    with pytest.raises(TypeError, message='list indices must be integers or slices, not str'):
        l['awd']
    with pytest.raises(TypeError, message='list indices must be integers or slices, not str'):
        l['awd'] = 5
    with pytest.raises(TypeError, message='list indices must be integers or slices, not str'):
        del l['awd']
    sl = l[3:-4:-2]
    assert isinstance(sl, ListProxy)
    assert unproxy(sl) is not unproxy(l)
    assert len(sl) == 2
    assert tuple(sl) == (55, 33)
    del l[3:-4:-2]
    assert tuple(l) == (22, 44)
    l.append(77)
    l.append(88)
    assert tuple(l) == (22, 44, 77, 88)
    l[2] = 66
    assert tuple(l) == (22, 44, 66, 88)
    l.insert(3, 77)
    l.insert(-3, 55)
    assert tuple(l) == (22, 44, 55, 66, 77, 88)
    l.insert(100, 99)
    l.insert(-100, 11)
    assert tuple(l) == (11, 22, 44, 55, 66, 77, 88, 99)


def test_ObjectProxy():
    tb = lua.table(
        the='quick',
        brown='fox',
        jumps='over',
        lazy='doges',
    )
    obj = ObjectProxy(tb)
    assert unproxy(obj) is tb
    assert obj.the == 'quick'
    assert obj.brown == 'fox'
    assert obj.jumps == 'over'
    assert obj.lazy == 'doges'
    obj.brown = 'rabbit'
    assert obj.brown == 'rabbit'
    assert tb.brown == 'rabbit'
    del obj.the
    assert obj.the == None
