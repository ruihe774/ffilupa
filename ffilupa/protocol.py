"""module contains python-to-lua protocols"""


__all__ = ('as_attrgetter', 'as_itemgetter', 'as_function', 'as_is', 'as_method', 'Py2LuaProtocol', 'IndexProtocol', 'PushProtocol', 'CFunctionProtocol', 'MethodProtocol', 'autopack')

from enum import Enum

class PushProtocol(Enum):
    Keep = 1
    Naked = 2

class Py2LuaProtocol:
    push_protocol = PushProtocol.Naked

    def __init__(self, obj):
        super().__init__()
        self.obj = obj

    def __call__(self, *args, **kwargs):
        return self.obj(*args, **kwargs)

class IndexProtocol(Py2LuaProtocol):
    """
    Control the access way for python object in lua.

    * ``ITEM``: indexing will be treat as item getting/setting.
    * ``ATTR``: indexing will be treat as attr getting/setting.

    Example:

    ..
        ## doctest helper
        >>> from ffilupa import *
        >>> runtime = LuaRuntime()

    ::

        >>> awd = {'get': 'awd'}
        >>> runtime._G.awd = awd
        >>> runtime.eval('awd.get')
        'awd'
        >>> runtime._G.awd = IndexProtocol(awd, IndexProtocol.ATTR)
        >>> runtime.eval('awd:get("get")')
        'awd'

    Default behavior is for objects have method ``__getitem__``,
    indexing will be treat as item getting/setting; otherwise
    indexing will be treat as attr getting/setting.
    """
    ITEM = 1
    ATTR = 2

    push_protocol = PushProtocol.Keep
    def __init__(self, obj, index_protocol=None):
        """
        Init self with ``obj`` and ``index_protocol``.

        ``obj`` is a python object.

        ``index_protocol`` can be ITEM or ATTR.
        If it's set to None, default behavior said above will
        take effect.
        """
        super().__init__(obj)
        if index_protocol is None:
            if hasattr(obj.__class__, '__getitem__'):
                index_protocol = self.__class__.ITEM
            else:
                index_protocol = self.__class__.ATTR
        self.index_protocol = index_protocol


class CFunctionProtocol(Py2LuaProtocol):
    def push_protocol(self, runtime, L):
        from .py_to_lua import push
        from .metatable import normal_args
        lib = runtime.lib
        client = lib._get_caller_client()
        push(runtime, as_is(runtime))
        push(runtime, as_is(normal_args(self.obj)))
        lib.lua_pushcclosure(L, client, 2)

class MethodProtocol(Py2LuaProtocol):
    push_protocol = PushProtocol.Keep
    def __init__(self, *args):
        args = list(args)
        if len(args) == 1:
            args.append(args[0].__self__)
        self.obj, self.selfobj = args

    def __call__(self, obj, *args, **kwargs):
        assert self.selfobj is obj, 'wrong instance'
        return self.obj(*args, **kwargs)

as_attrgetter = lambda obj: IndexProtocol(obj, IndexProtocol.ATTR)
as_itemgetter = lambda obj: IndexProtocol(obj, IndexProtocol.ITEM)
as_is = Py2LuaProtocol
as_function = CFunctionProtocol
as_method = MethodProtocol

def autopack(obj):
    if hasattr(obj.__class__, '__getitem__'):
        return as_itemgetter(obj)
    else:
        return as_is(obj)
