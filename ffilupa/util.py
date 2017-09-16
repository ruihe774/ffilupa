"""
module contains util functions

.. note::
    For context manager,

    * ``enter time`` means the time ``__enter__`` called.
      That happens at the begin of ``with`` block.

    * ``exit time`` means the time ``__exit__`` called.
      That happens at the end of ``with`` block. Note
      this does not mean the exit time of the interpreter.
"""


from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, (
    'assert_stack_balance', 'ensure_stack_balance', 'lock_get_state',
    'python_2_bool_compatible', 'python_2_unicode_compatible', 'partial',
    'NotCopyable', 'deprecate', 'pending_deprecate')))

from contextlib import contextmanager
import six
from zope.deprecation.deprecation import deprecate
from .lua.lib import *
from .exception import *


@contextmanager
def assert_stack_balance(L):
    """
    A context manager. Accepts a lua state and raise
    AssertionError if the lua stack top got from
    ``lua_gettop()`` is different between the enter
    time and exit time. This helper helps to assert
    the stack balance.
    """
    oldtop = lua_gettop(L)
    try:
        yield
    finally:
        newtop = lua_gettop(L)
        if oldtop != newtop:
            raise AssertionError('stack unbalance: {} elements before, {} elements after'.format(oldtop, newtop))


@contextmanager
def ensure_stack_balance(L):
    """
    A context manager. Accepts a lua state and pops
    the lua stack at exit time to make the top of
    stack is unchanged compared to the enter time.
    Note that it just pops values but not pushes
    anything so that if the stack top at exit time
    is less than enter time, AssertionError will be
    raised. This helper helps to ensure the stack
    balance.
    """
    with assert_stack_balance(L):
        oldtop = lua_gettop(L)
        try:
            yield
        finally:
            newtop = lua_gettop(L)
            if newtop > oldtop:
                lua_pop(L, newtop - oldtop)


@contextmanager
def lock_get_state(runtime):
    """
    A context manager. Locks ``runtime`` and returns
    the lua state of it. The runtime will be unlocked
    at exit time.
    """
    with runtime.lock():
        yield runtime.lua_state


def python_2_bool_compatible(klass):
    """
    A decorator that defines __nonzero__ method under Python 2.
    Under Python 3 it does nothing.

    To support Python 2 and 3 with a single code base, define a __bool__ method
    returning bool value and apply this decorator to the class.
    """
    if six.PY2:
        if '__bool__' not in klass.__dict__:
            raise ValueError("@python_2_bool_compatible cannot be applied "
                             "to %s because it doesn't define __bool__()." %
                             klass.__name__)
        klass.__nonzero__ = klass.__bool__
        del klass.__bool__
    return klass


def python_2_unicode_compatible(klass):
    """
    A decorator that defines __str__ and __unicode__ methods under Python 2.
    Under Python 3 it does nothing.

    To support Python 2 and 3 with a single code base, define __str__ and
    __bytes__ methods returning unicode value and binary value and apply
    this decorator to the class.
    """
    if six.PY2:
        if '__str__' not in klass.__dict__ or \
           '__bytes__' not in klass.__dict__:
            raise ValueError("@python_2_unicode_compatible cannot be applied "
                             "to %s because it doesn't define __str__() and __bytes__()." % klass.__name__)
        klass.__unicode__ = klass.__str__
        klass.__str__ = klass.__bytes__
        del klass.__bytes__
    return klass


def partial(func, *frozenargs):
    """
    Same as ``functools.partial``.
    Repaired for lambda.
    """
    @six.wraps(func)
    def newfunc(*args):
        return func(*(frozenargs + args))
    return newfunc


class NotCopyable(object):
    """
    A base class that its instance is not copyable.
    Do copying on the instance will raise a TypeError.
    """
    def __copy__(self):
        raise TypeError("'{}.{}' is not copyable".format(self.__class__.__module__, self.__class__.__name__))

    def __deepcopy__(self, memo):
        raise TypeError("'{}.{}' is not copyable".format(self.__class__.__module__, self.__class__.__name__))


pending_deprecate = lambda msg: deprecate(msg, PendingDeprecationWarning)
