"""
module contains lua C callback helpers

A lua C callback is a C function that accepts
a argument typed "lua_State*" and returns a
integer. This module helps to make lua C callback
from a python function that accepts lua state and
returns a int. To better deal with error raising,
if the python function returns -1, the ``lua_error()``
is called. The number of lua C callback is limited
and this module is the manager of them.
"""


from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('alloc_callback', 'release_callback')))

from collections import deque
import six
from .lua import lib, ffi


callbacks = deque(range(lib._PY_C_CALLBACKS))


def alloc_callback():
    """
    Allocate a lua C callback.

    Returns a tuple, the callback name to be passed to
    ``ffi.def_extern()`` and the C callback.

    The ``ffi.def_extern()`` must be called before the
    C callback is used. After finishing using, call
    ``release_callback()`` with the callback name to
    release the C callback for next time allocation.

    Example:

    ::

        >>> from ffilupa.runtime import *
        >>> from ffilupa.callback import *
        >>> from ffilupa.lua import ffi, lib
        >>> runtime = LuaRuntime()
        >>> runtime.lock()  # doctest: +ELLIPSIS
        <...>
        >>> L = runtime.lua_state
        >>> name, callback = alloc_callback()
        >>> @ffi.def_extern(name)
        ... def mypow(L):
        ...     a = lib.lua_tointeger(L, -2)
        ...     b = lib.lua_tointeger(L, -1)
        ...     if a == b == 0:
        ...         lib.lua_pushstring(L, b'the result of 0 ** 0 is undefined')
        ...         return -1   # raise a error into lua
        ...     lib.lua_pushinteger(L, a ** b)
        ...     return 1        # one return value
        ...
        >>> lib.lua_pushcfunction(L, callback)
        >>> lib.lua_pushinteger(L, 5)
        >>> lib.lua_pushinteger(L, 3)
        >>> lib.lua_pcall(L, 2, lib.LUA_MULTRET, 0) == lib.LUA_OK
        True
        >>> lib.lua_tointeger(L, 1)
        125
        >>> lib.lua_settop(L, 0)
        >>> runtime.unlock()

    .. warning::
        This is a low-level API. Users should not use this.
        Use ``protocol.as_function`` instead.

    """
    name = six.text_type(callbacks.popleft())
    return '_py_callback_server_' + name, getattr(lib, '_py_callback_client_get_' + name)()


def released_callback(L):
    """just raise a error"""
    raise RuntimeError('this callback is released')


def release_callback(name):
    """
    Release the C callback specified by ``name``.
    """
    ffi.def_extern(name)(released_callback)
    callbacks.append(name)
