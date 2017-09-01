from __future__ import absolute_import, unicode_literals
__all__ = ('alloc_callback', 'release_callback')

import six
from six.moves.queue import Queue
from .lua import lib, ffi


callbacks = Queue()
for i in range(100, 1000):
    callbacks.put(i)


def alloc_callback():
    name = six.text_type(callbacks.get())
    return '_py_callback_server_' + name, getattr(lib, '_py_callback_client_get_' + name)()


def released_callback(L):
    raise RuntimeError('this callback is released')


def release_callback(name):
    ffi.def_extern(name)(released_callback)
    callbacks.put(name)
