from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('as_attrgetter', 'as_itemgetter', 'as_function', 'as_is', 'Py2LuaProtocol')))

import six


class Py2LuaProtocol(object):
    ITEM = 1
    ATTR = 2
    FUNC = 3
    def __init__(self, obj, index_protocol=None):
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
