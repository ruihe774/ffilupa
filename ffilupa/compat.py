from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('unpacks_lua_table', 'unpacks_lua_table_method', 'lua_type', 'LuaError')))

import six
from zope.deprecation.deprecation import deprecated, deprecate
from .exception import LuaErr as LuaError

deprecated('LuaError', 'renamed. use ``LuaErr`` instead')


def unpacks_arg_table(args):
    from .py_from_lua import LuaObject
    da, dk = [], {}
    if len(args) != 1:
        da = args
    else:
        arg = args[0]
        if isinstance(arg, LuaObject) and arg._type() == LUA_TTABLE:
            for i in range(1, len(arg) + 1):
                da.append(arg[i])
            for k, v in arg.items():
                if k not in range(1, len(arg) + 1):
                    dk[k] = v
        else:
            da = args
    return tuple(da), dk


def unpacks_lua_table(func):
    @six.wraps(func)
    def newfunc(*args):
        da, dk = unpacks_arg_table(args)
        return func(*da, **dk)
    return newfunc


def unpacks_lua_table_method(func):
    @six.wraps(func)
    def newfunc(self, *args):
        da, dk = unpacks_arg_table(args)
        return func(self, *da, **dk)
    return newfunc


@deprecate('deprecated. use ``.typename()`` instead')
def lua_type(obj):
    from .py_from_lua import LuaObject
    if isinstance(obj, LuaObject):
        return obj.typename()
    else:
        return None
