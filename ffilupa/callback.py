from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('alloc_callback', 'release_callback')))

from collections import deque
import six
from .lua import lib, ffi


callbacks = deque(range(lib._PY_C_CALLBACKS))


def alloc_callback():
    name = six.text_type(callbacks.popleft())
    return '_py_callback_server_' + name, getattr(lib, '_py_callback_client_get_' + name)()


def released_callback(L):
    raise RuntimeError('this callback is released')


def release_callback(name):
    ffi.def_extern(name)(released_callback)
    callbacks.append(name)
