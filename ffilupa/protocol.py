"""module contains python-to-lua protocols"""


__all__ = ('as_attrgetter', 'as_itemgetter', 'as_function', 'as_is', 'as_method', 'Py2LuaProtocol', 'IndexProtocol', 'PushProtocol', 'CFunctionProtocol', 'MethodProtocol', 'autopackindex')

from enum import Enum

class PushProtocol(Enum):
    """
    Control push behavior. :py:attr:`Py2LuaProtocol.push_protocol` is set to this.

    * ``Keep``: the protocol object will be pushed to Lua.
    * ``Naked``: the protocol object will not be pushed to Lua. Instead, it will be unwrapped.
    """
    Keep = 1
    Naked = 2

class Py2LuaProtocol:
    push_protocol = PushProtocol.Naked

    def __init__(self, obj):
        super().__init__()
        self.obj = obj

class IndexProtocol(Py2LuaProtocol):
    """
    Control the access way for python object in lua.

    * ``ITEM``: indexing will be treat as item getting/setting.
    * ``ATTR``: indexing will be treat as attr getting/setting.
    """
    ITEM = 1
    ATTR = 2

    push_protocol = PushProtocol.Keep
    def __init__(self, obj, index_protocol):
        """
        Init self with ``obj`` and ``index_protocol``.

        ``obj`` is a python object.

        ``index_protocol`` can be ITEM or ATTR.
        """
        super().__init__(obj)
        self.index_protocol = index_protocol


class CFunctionProtocol(Py2LuaProtocol):
    """make a python object behave like a C function in lua"""
    def push_protocol(self, pi):
        from .metatable import normal_args
        lib = pi.runtime.lib
        client = lib._get_caller_client()
        pi.runtime.push(as_is(pi.runtime))
        pi.runtime.push(as_is(normal_args(self.obj)))
        lib.lua_pushcclosure(pi.L, client, 2)

class MethodProtocol(Py2LuaProtocol):
    """wrap method"""
    push_protocol = PushProtocol.Keep
    def __init__(self, *args):
        args = list(args)
        if len(args) == 1:
            args.append(args[0].__self__)
        super().__init__(args[0])
        _, self.selfobj = args

    def __call__(self, obj, *args, **kwargs):
        if self.selfobj is not obj:
            raise ValueError('wrong instance')
        return self.obj(*args, **kwargs)

as_attrgetter = lambda obj: IndexProtocol(obj, IndexProtocol.ATTR)
as_itemgetter = lambda obj: IndexProtocol(obj, IndexProtocol.ITEM)
as_is = Py2LuaProtocol
as_function = CFunctionProtocol
as_method = MethodProtocol

def autopackindex(obj) -> IndexProtocol:
    """If objects have method ``__getitem__``,
    indexing will be treat as item getting/setting; otherwise
    indexing will be treat as attr getting/setting.
    """
    if hasattr(obj.__class__, '__getitem__'):
        return as_itemgetter(obj)
    else:
        return as_attrgetter(obj)
