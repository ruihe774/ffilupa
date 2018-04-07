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


__all__ = (
    'assert_stack_balance', 'ensure_stack_balance', 'lock_get_state',
    'partial', 'NotCopyable', 'deprecate', 'pending_deprecate', 'PathLike')

from contextlib import contextmanager
from warnings import warn
import functools
import abc
from .exception import *


@contextmanager
def assert_stack_balance(runtime):
    """
    A context manager. Accepts a lua state and raise
    AssertionError if the lua stack top got from
    ``lua_gettop()`` is different between the enter
    time and exit time. This helper helps to assert
    the stack balance.
    """
    L = runtime.lua_state
    lib = runtime.lib
    oldtop = lib.lua_gettop(L)
    try:
        yield
    finally:
        newtop = lib.lua_gettop(L)
        assert oldtop == newtop, 'stack unbalance'


@contextmanager
def ensure_stack_balance(runtime):
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
    L = runtime.lua_state
    lib = runtime.lib
    oldtop = lib.lua_gettop(L)
    try:
        yield
    finally:
        newtop = lib.lua_gettop(L)
        assert oldtop <= newtop, 'stack unbalance'
        lib.lua_settop(L, oldtop)


@contextmanager
def lock_get_state(runtime):
    """
    A context manager. Locks ``runtime`` and returns
    the lua state of it. The runtime will be unlocked
    at exit time.
    """
    with runtime.lock():
        yield runtime.lua_state


def partial(func, *frozenargs):
    """
    Same as ``functools.partial``.
    Repaired for lambda.
    """
    @functools.wraps(func)
    def newfunc(*args):
        return func(*(frozenargs + args))
    return newfunc


class NotCopyable:
    """
    A base class that its instance is not copyable.
    Do copying on the instance will raise a TypeError.
    """
    def __copy__(self):
        raise TypeError("'{}.{}' is not copyable".format(self.__class__.__module__, self.__class__.__name__))

    def __deepcopy__(self, memo):
        raise TypeError("'{}.{}' is not copyable".format(self.__class__.__module__, self.__class__.__name__))


def deprecate(message, category=DeprecationWarning):
    def helper(func):
        @functools.wraps(func)
        def newfunc(*args):
            warn(message, category)
            return func(*args)
        return newfunc
    return helper
    
pending_deprecate = lambda message: deprecate(message, PendingDeprecationWarning)


def reraise(tp, value, tb=None):
    # Copyright (c) 2010-2018 Benjamin Peterson
    try:
        if value is None:
            value = tp()
        if value.__traceback__ is not tb:
            raise value.with_traceback(tb)
        raise value
    finally:
        value = None
        tb = None


class PathLike(abc.ABC):

    """Abstract base class for implementing the file system path protocol."""

    @abc.abstractmethod
    def __fspath__(self):
        """Return the file system path representation of the object."""
        raise NotImplementedError

    @classmethod
    def __subclasshook__(cls, subclass):
        return hasattr(subclass, '__fspath__')
