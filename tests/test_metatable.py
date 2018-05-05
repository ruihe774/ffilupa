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
