"""module contains python-to-lua protocols"""


from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('as_attrgetter', 'as_itemgetter', 'as_function', 'as_is', 'Py2LuaProtocol')))

import six


class Py2LuaProtocol(object):
    """
    Control the access way for python object in lua.

    * ``ITEM``: indexing will be treat as item getting/setting.
    * ``ATTR``: indexing will be treat as attr getting/setting.
    * ``FUNC``: object will be treat as a (C) function.

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
        >>> runtime._G.awd = Py2LuaProtocol(awd, Py2LuaProtocol.ATTR)
        >>> runtime.eval('awd.get("get")')
        'awd'

    Default behavior is for objects have method ``__getitem__``,
    indexing will be treat as item getting/setting; otherwise
    indexing will be treat as attr getting/setting.
    """
    ITEM = 1
    ATTR = 2
    FUNC = 3
    def __init__(self, obj, index_protocol=None):
        """
        Init self with ``obj`` and ``index_protocol``.

        ``obj`` is a python object.

        ``index_protocol`` can be ITEM, ATTR or FUNC.
        If it's set to None, default behavior said above will
        take effect.
        """
        super(Py2LuaProtocol, self).__init__()
        if index_protocol is None:
            if hasattr(obj, '__getitem__'):
                index_protocol = self.__class__.ITEM
            else:
                index_protocol = self.__class__.ATTR
        self.obj = obj
        self.index_protocol = index_protocol


as_attrgetter = lambda obj: Py2LuaProtocol(obj, Py2LuaProtocol.ATTR)
as_itemgetter = lambda obj: Py2LuaProtocol(obj, Py2LuaProtocol.ITEM)
as_function = lambda obj: Py2LuaProtocol(obj, Py2LuaProtocol.FUNC)
as_is = Py2LuaProtocol
