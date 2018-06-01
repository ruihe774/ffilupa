"""module contains helpers for compatibility with lupa"""


__all__ = ('unpacks_lua_table', 'unpacks_lua_table_method', 'lua_type', 'LuaError', 'LuaSyntaxError')

import functools
from .exception import LuaErr as LuaError
from .exception import LuaErrSyntax as LuaSyntaxError


def unpacks_arg_table(args):
    """unpacks lua table in args"""
    from .py_from_lua import LuaTable, ListProxy
    da, dk = [], {}
    if len(args) != 1:
        da = args
    else:
        arg = args[0]
        if isinstance(arg, LuaTable):
            lp = ListProxy(arg)
            da.extend(lp)
            llp = len(lp)
            for k, v in arg.items():
                if not isinstance(k, int) or k < 1 or k > llp:
                    if isinstance(k, bytes):
                        k = k.decode(arg._runtime.encoding)
                    dk[k] = v
        else:
            da = args
    return tuple(da), dk


def unpacks_lua_table(func):
    """
    A decorator for function. Unpacks lua tables in args.
    """
    @functools.wraps(func)
    def newfunc(*args):
        da, dk = unpacks_arg_table(args)
        return func(*da, **dk)
    return newfunc


def unpacks_lua_table_method(func):
    """
    A decorator for method. Unpacks lua tables in args.
    """
    @functools.wraps(func)
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
