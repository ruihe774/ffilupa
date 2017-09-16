"""module contains helpers for compatibility with lupa"""


from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('unpacks_lua_table', 'unpacks_lua_table_method', 'lua_type', 'LuaError', 'LuaSyntaxError')))

import six
from zope.deprecation import deprecated, deprecate
from .exception import LuaErr as LuaError
from .exception import LuaErrSyntax as LuaSyntaxError

deprecated('LuaError', 'renamed. use ``LuaErr`` instead')
deprecated('LuaSyntaxError', 'renamed. use ``LuaErrSyntax`` instead')


def unpacks_arg_table(args):
    """unpacks lua table in args"""
    from .py_from_lua import LuaTable
    da, dk = [], {}
    if len(args) != 1:
        da = args
    else:
        arg = args[0]
        if isinstance(arg, LuaTable):
            for i in range(1, len(arg) + 1):
                da.append(arg[i])
            for k, v in arg.items():
                if k not in range(1, len(arg) + 1):
                    if isinstance(k, six.binary_type):
                        k = k.decode(arg._runtime.encoding)
                    dk[k] = v
        else:
            da = args
    return tuple(da), dk


def unpacks_lua_table(func):
    """
    A decorator for function. Unpacks lua tables in args.
    """
    @six.wraps(func)
    def newfunc(*args):
        da, dk = unpacks_arg_table(args)
        return func(*da, **dk)
    return newfunc


def unpacks_lua_table_method(func):
    """
    A decorator for method. Unpacks lua tables in args.
    """
    @six.wraps(func)
    def newfunc(self, *args):
        da, dk = unpacks_arg_table(args)
        return func(self, *da, **dk)
    return newfunc


def lua_type(obj):
    """
    Returns the typename of the lua object, decoded with
    ascii. Returns None for other python objects.
    """
    from .py_from_lua import LuaObject
    if isinstance(obj, LuaObject):
        return obj.typename()
    else:
        return None

deprecated('lua_type', 'deprecated. use ``.typename()`` instead')
