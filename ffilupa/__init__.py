from collections import UserDict, namedtuple
from collections.abc import *
from contextlib import contextmanager
from enum import Enum
import functools
import importlib
import itertools
import operator
import os
import sys
from threading import RLock
from typing import *
from pathlib import Path

from .__version__ import __version__
from . import lualibs as _lualibs
from .lualibs import *

__all__ = (
    "LuaRuntime",
    "LuaErr",
    "LuaErrSyntax",
    "as_attrgetter",
    "as_itemgetter",
    "as_function",
    "as_is",
    "as_method",
    "autopackindex",
    "unpacks_lua_table",
    "unpacks_lua_table_method",
    "lua_type",
    "LuaError",
    "LuaSyntaxError",
    'unproxy',
    'ListProxy',
    'ObjectProxy',
    'StrictObjectProxy',
    'DictProxy',
) + _lualibs.__all__


class LuaErr(Exception):
    """
    Base exception class for error happened in lua.

    One instance of LuaErr has two attributes.

    * ``status``, the return value of failed lua API call.
    * ``err_msg``, the error message got from lua.
    """

    @staticmethod
    def new(runtime, status, err_msg, encoding=None):
        """
        Make an instance of one of the subclasses of LuaErr
        according to ``status``.

        ``err_msg`` is string type.

        ``encoding`` will be used to decode the ``err_msg``
        if it's binary type. ``err_msg`` will remain undecoded
        if ``encoding`` is None.
        """
        if isinstance(err_msg, bytes) and encoding is not None:
            err_msg = err_msg.decode(encoding)
        return {
            runtime.lib.LUA_OK: LuaOK,
            runtime.lib.LUA_YIELD: LuaYield,
            runtime.lib.LUA_ERRRUN: LuaErrRun,
            runtime.lib.LUA_ERRSYNTAX: LuaErrSyntax,
            runtime.lib.LUA_ERRMEM: LuaErrMem,
            runtime.lib.LUA_ERRGCMM: LuaErrGCMM,
            runtime.lib.LUA_ERRERR: LuaErrErr,
        }.get(status, LuaErr)(status, err_msg)

    def __init__(self, status, err_msg):
        """
        Init self with ``status`` and ``err_msg``.
        """
        super().__init__(status, err_msg)
        self.status, self.err_msg = status, err_msg

    def __repr__(self):
        return "{}: status {}\n{}".format(
            self.__class__.__name__, self.status, self.err_msg
        )

    def __str__(self):
        return self.err_msg


class LuaOK(LuaErr):
    """Exception LuaOK"""

    pass


class LuaYield(LuaErr):
    """Exception LuaYield"""

    pass


class LuaErrRun(LuaErr):
    """Exception LuaErrRun"""

    pass


class LuaErrSyntax(LuaErr):
    """Exception LuaErrSyntax"""

    pass


class LuaErrMem(LuaErr):
    """Exception LuaErrMem"""

    pass


class LuaErrGCMM(LuaErr):
    """Exception LuaErrGCMM"""

    pass


class LuaErrErr(LuaErr):
    """Exception LuaErrErr"""

    pass


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
        assert oldtop == newtop, "stack unbalance"


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
        assert oldtop <= newtop, "stack unbalance"
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
        raise TypeError(
            "'{}.{}' is not copyable".format(
                self.__class__.__module__, self.__class__.__name__
            )
        )

    def __deepcopy__(self, memo):
        raise TypeError(
            "'{}.{}' is not copyable".format(
                self.__class__.__module__, self.__class__.__name__
            )
        )


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


class Registry(UserDict):
    """a dict with ``register``"""

    def register(self, name):
        """a decorator. Set function into ``self``"""

        def _(func):
            self[name] = func
            return func

        return _


def ensure_strpath(path: Union[str, os.PathLike]) -> str:
    return path if isinstance(path, str) else path.__fspath__()


def ensure_pathlib_path(path: Union[str, os.PathLike]) -> Path:
    return Path(ensure_strpath(path))


def getmetafield(runtime, index, key):
    """
    Get the metatable field ``key`` of lua object in ``runtime`` at ``index``.
    Returns None if the object has no metatable or there's no such metafield.
    """
    if isinstance(key, str):
        key = key.encode(runtime.source_encoding)
    lib = runtime.lib
    with lock_get_state(runtime) as L:
        with ensure_stack_balance(runtime):
            if lib.luaL_getmetafield(L, index, key) != lib.LUA_TNIL:
                return runtime.pull(-1)


def hasmetafield(runtime, index, key):
    """
    Returns whether the lua object in ``runtime`` at ``index`` has such metafield ``key``.
    The return value is the same as ``getmetafield(runtime, index, key) is not None``.
    """
    return getmetafield(runtime, index, key) is not None


class LuaLimitedObject(NotCopyable):
    """
    Class LuaLimitedObject.

    This class is the base class of LuaObject.
    """

    def _ref_to_key(self, key):
        self._ref = key

    def _ref_to_index(self, runtime, index):
        lib = runtime.lib
        ffi = runtime.ffi
        with lock_get_state(runtime) as L:
            with assert_stack_balance(runtime):
                index = lib.lua_absindex(L, index)
                key = ffi.new("char*")
                lib.lua_pushlightuserdata(L, key)
                lib.lua_pushvalue(L, index)
                lib.lua_rawset(L, lib.LUA_REGISTRYINDEX)
                self._ref_to_key(key)

    def __init__(self, runtime, index):
        """
        Init a lua object wrapper for the lua object in ``runtime`` at ``index``.

        ``runtime`` is a lua runtime.

        ``index`` is a integer, the position in lua stack.

        This method will not change the lua stack.
        This method will register the lua object into registry,
        so that the lua object will keep alive until this wrapper
        is garbage collected.

        The instance of lua object wrapper will have a ref to the lua runtime
        so that if there's lua object wrapper alive, the runtime will not be
        closed unless you close it manually.
        """
        super().__init__()
        self._runtime = runtime
        self._ref_to_index(runtime, index)

    @staticmethod
    def new(runtime, index):
        """
        Make an instance of one of the subclasses of LuaObject
        according to the type of that lua object.
        """
        lib = runtime.lib
        with lock_get_state(runtime) as L:
            tp = lib.lua_type(L, index)
            return {
                lib.LUA_TNIL: LuaNil,
                lib.LUA_TNUMBER: LuaNumber,
                lib.LUA_TBOOLEAN: LuaBoolean,
                lib.LUA_TSTRING: LuaString,
                lib.LUA_TTABLE: LuaTable,
                lib.LUA_TFUNCTION: LuaFunction,
                lib.LUA_TUSERDATA: LuaUserdata,
                lib.LUA_TTHREAD: LuaThread,
                lib.LUA_TLIGHTUSERDATA: LuaUserdata,
            }[tp](runtime, index)

    def __del__(self):
        """unregister the lua object."""
        key = self._ref
        lib = self._runtime.lib
        with lock_get_state(self._runtime) as L:
            if L:
                with assert_stack_balance(self._runtime):
                    lib.lua_pushlightuserdata(L, key)
                    lib.lua_pushnil(L)
                    lib.lua_rawset(L, lib.LUA_REGISTRYINDEX)

    def _pushobj(self):
        """push the lua object onto the top of stack."""
        key = self._ref
        lib = self._runtime.lib
        with lock_get_state(self._runtime) as L:
            lib.lua_pushlightuserdata(L, key)
            lib.lua_rawget(L, lib.LUA_REGISTRYINDEX)

    def __bool__(self):
        """convert to bool using lua_toboolean."""
        lib = self._runtime.lib
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                self._pushobj()
                return bool(lib.lua_toboolean(L, -1))

    def _type(self):
        """calls ``lua_type`` and returns the type id of the lua object."""
        lib = self._runtime.lib
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                self._pushobj()
                return lib.lua_type(L, -1)

    def pull(self, **kwargs):
        """
        "Pull" down the lua object to python.
        Returns a lua object wrapper or a native python value.
        See ``py_from_lua.pull`` for more details.
        """
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                self._pushobj()
                return self._runtime.pull(-1, **kwargs)

    def __copy__(self):
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                self._pushobj()
                return self.__class__(self._runtime, -1)


def not_impl(exc_type, exc_value, exc_traceback):
    """check whether lua error is happened in first stack frame.
    if it is, returns ``NotImplemented``, otherwise reraise the lua error.

    This function is a helper for operator overloading."""
    if issubclass(exc_type, LuaErrRun):
        err_msg = exc_value.err_msg
        if isinstance(err_msg, bytes):
            lns = err_msg.split(b"\n")
        else:
            lns = err_msg.split("\n")
        if len(lns) == 3:
            return NotImplemented
    reraise(exc_type, exc_value, exc_traceback)


_method_template = """\
def {name}({outer_args}, **kwargs):
    runtime = self._runtime
    lib = runtime.lib
    with lock_get_state(runtime) as L:
        with ensure_stack_balance(runtime):
            lib.lua_pushcfunction(L, lib._get_{client}_client())
            try:
                op = lib.{op}
            except AttributeError:
                return NotImplemented
            try:
                return LuaCallable.__call__(LuaVolatile(runtime, -1), op, {args}, set_metatable=False, **kwargs)
            except LuaErrRun:
                return not_impl(*sys.exc_info())
"""


class LuaObject(LuaLimitedObject):
    """
    Base class for other lua object wrapper classes.

    A lua object wrapper wraps a lua object for python.
    Commonly it's used to wrap lua tables, functions etc
    which cannot be simply translate to a plain python
    object. The wrapped lua object won't be garbage
    collected until the wrapper is garbage collected.

    Operations on lua object wrapper will be passed to lua
    and done in lua with the wrapped lua object.
    """

    def typename(self):
        """
        Returns the typename of the wrapped lua object.
        The return value is the same as the return value
        of lua function ``type``, decoded with ascii.
        """
        runtime = self._runtime
        lib = runtime.lib
        ffi = runtime.ffi
        with lock_get_state(runtime) as L:
            with ensure_stack_balance(runtime):
                self._pushobj()
                return ffi.string(lib.lua_typename(L, lib.lua_type(L, -1))).decode(
                    "ascii"
                )

    for name, op in (
        ("add", "LUA_OPADD"),
        ("sub", "LUA_OPSUB"),
        ("mul", "LUA_OPMUL"),
        ("truediv", "LUA_OPDIV"),
        ("floordiv", "LUA_OPIDIV"),
        ("mod", "LUA_OPMOD"),
        ("pow", "LUA_OPPOW"),
        ("and", "LUA_OPBAND"),
        ("or", "LUA_OPBOR"),
        ("xor", "LUA_OPBXOR"),
        ("lshift", "LUA_OPSHL"),
        ("rshift", "LUA_OPSHR"),
    ):
        exec(
            _method_template.format(
                name="__{}__".format(name),
                client="arith",
                op=op,
                args="self, value",
                outer_args="self, value",
            )
        )
        exec(
            _method_template.format(
                name="__r{}__".format(name),
                client="arith",
                op=op,
                args="value, self",
                outer_args="self, value",
            )
        )

    for name, rname, op in (
        ("eq", None, "LUA_OPEQ"),
        ("lt", "gt", "LUA_OPLT"),
        ("le", "ge", "LUA_OPLE"),
    ):
        exec(
            _method_template.format(
                name="__{}__".format(name),
                client="compare",
                op=op,
                args="self, value",
                outer_args="self, value",
            )
        )
        if rname:
            exec(
                _method_template.format(
                    name="__{}__".format(rname),
                    client="compare",
                    op=op,
                    args="value, self",
                    outer_args="self, value",
                )
            )

    for name, op in (("invert", "LUA_OPBNOT"), ("neg", "LUA_OPUNM")):
        exec(
            _method_template.format(
                name="__{}__".format(name),
                client="arith",
                op=op,
                args="self",
                outer_args="self",
            )
        )

    del name
    del rname
    del op

    def __init__(self, runtime, index):
        super().__init__(runtime, index)
        self.edit_mode = False

    def _tostring(self, *, autodecode=False, **kwargs):
        return self._runtime._G.tostring(self, autodecode=autodecode, **kwargs)

    def __bytes__(self):
        return self._tostring(autodecode=False)

    def __str__(self):
        if self._runtime.encoding is not None:
            return bytes(self).decode(self._runtime.encoding)
        else:
            raise ValueError("encoding not specified")


_index_template = """\
def {name}({args}, **kwargs):
    runtime = self._runtime
    lib = runtime.lib
    with lock_get_state(runtime) as L:
        with ensure_stack_balance(runtime):
            lib.lua_pushcfunction(L, lib._get_index_client())
            return LuaCallable.__call__(LuaVolatile(runtime, -1), {op}, {args}, **kwargs)
"""


class LuaCollection(LuaObject):
    """
    Lua collection type wrapper. ("table" and "userdata")

    LuaCollection is dict-like and support item getting/setting.
    The item getting/setting will be passed to lua and
    modify the wrapped lua object.

    Getting/setting through attributes is also supported.
    The same name python attributes will override that in
    lua.

    The indexing key name will be encoded with ``encoding``
    specified in lua runtime if it's a str.
    """

    exec(_index_template.format(name="__len__", op=0, args="self"))
    exec(_index_template.format(name="__getitem__", op=1, args="self, name"))
    exec(_index_template.format(name="__setitem__", op=2, args="self, name, value"))

    def __delitem__(self, name):
        if isinstance(name, int):
            self._runtime._G.table.remove(self, name)
        else:
            self[name] = self._runtime.nil

    def attr_filter(self, name: str) -> bool:
        """
        Attr filter. Used in attr getting/setting. If returns True,
        the attr getting/setting will be passed to lua, otherwise
        the attr getting/setting will not be passed to lua and
        operation will be done on ``self`` the python object.
        """
        return (
            self.__dict__.get("edit_mode", True) is False and name not in self.__dict__
        )

    def __getattr__(self, name):
        if self.attr_filter(name):
            return self[name]
        else:
            return self.__getattribute__(name)

    def __setattr__(self, name, value):
        if self.attr_filter(name):
            self[name] = value
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name):
        if self.attr_filter(name):
            del self[name]
        else:
            super().__delattr__(name)

    def keys(self):
        """
        Returns KeysView.
        """
        return LuaKView(self)

    def values(self):
        """
        Returns ValuesView.
        """
        return LuaVView(self)

    def items(self):
        """
        Returns ItemsView.
        """
        return LuaKVView(self)

    def __iter__(self):
        return iter(self.keys())


MutableMapping.register(LuaCollection)


class LuaCallable(LuaObject):
    """
    Lua callable type wrapper. ("function" and "userdata")

    LuaCallable object is callable.
    The call will be translated to
    the call to the wrapped lua object.
    """

    def __call__(self, *args, **kwargs):
        """
        Call the wrapped lua object.

        Lua functions do not support keyword arguments.
        ``*args`` will be "pushed" to lua and as the
        arguments to call the lua object.
        Keyword arguments will be processed in python.
        """
        lib = self._runtime.lib
        set_metatable = kwargs.pop("set_metatable", True)
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                oldtop = lib.lua_gettop(L)
                try:
                    self._runtime._pushvar(b"debug", b"traceback")
                    if lib.lua_isfunction(L, -1) or hasmetafield(
                        self._runtime, -1, b"__call"
                    ):
                        errfunc = 1
                    else:
                        lib.lua_pop(L, 1)
                        errfunc = 0
                except TypeError:
                    errfunc = 0
                self._pushobj()
                handles = [
                    self._runtime.push(obj, set_metatable=set_metatable) for obj in args
                ]
                status = lib.lua_pcall(
                    L, len(args), lib.LUA_MULTRET, (-len(args) - 2) * errfunc
                )
                if status != lib.LUA_OK:
                    err_msg = self._runtime.pull(-1)
                    try:
                        stored = self._runtime._exception[1]
                    except (IndexError, TypeError):
                        pass
                    else:
                        if err_msg is stored:
                            self._runtime._reraise_exception()
                    self._runtime._clear_exception()
                    raise LuaErr.new(
                        self._runtime, status, err_msg, self._runtime.encoding
                    )
                else:
                    rv = [
                        self._runtime.pull(i, **kwargs)
                        for i in range(oldtop + 1 + errfunc, lib.lua_gettop(L) + 1)
                    ]
                    if len(rv) > 1:
                        return tuple(rv)
                    elif len(rv) == 1:
                        return rv[0]
                    else:
                        return


class LuaNil(LuaObject):
    """
    Lua nil type wrapper.
    """

    def __init__(self, runtime, index=None):
        lib = runtime.lib
        if index is None:
            with lock_get_state(runtime) as L:
                with ensure_stack_balance(runtime):
                    lib.lua_pushnil(L)
                    super().__init__(runtime, -1)
        else:
            super().__init__(runtime, index)


class LuaNumber(LuaObject):
    """
    Lua number type wrapper.
    """

    def __int__(self):
        lib = self._runtime.lib
        ffi = self._runtime.ffi
        isnum = ffi.new("int*")
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                self._pushobj()
                value = lib.lua_tointegerx(L, -1, isnum)
        isnum = isnum[0]
        if isnum:
            return value
        else:
            raise TypeError("not a integer")

    def __float__(self):
        lib = self._runtime.lib
        ffi = self._runtime.ffi
        isnum = ffi.new("int*")
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                self._pushobj()
                value = lib.lua_tonumberx(L, -1, isnum)
        isnum = isnum[0]
        if isnum:
            return value
        else:
            raise TypeError("not a number")


class LuaString(LuaObject):
    """
    Lua string type wrapper.
    """

    def __bytes__(self):
        lib = self._runtime.lib
        ffi = self._runtime.ffi
        sz = ffi.new("size_t*")
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                self._pushobj()
                value = lib.lua_tolstring(L, -1, sz)
                sz = sz[0]
                if value == ffi.NULL:
                    raise TypeError("not a string")
                else:
                    return ffi.unpack(value, sz)


class LuaBoolean(LuaObject):
    """
    Lua boolean type wrapper.
    """


class LuaTable(LuaCollection):
    """
    Lua table type wrapper.
    """


class LuaFunction(LuaCallable):
    """
    Lua function type wrapper.
    """

    def coroutine(self, *args, **kwargs) -> "LuaThread":
        """
        Create a coroutine from the lua function.
        Arguments will be stored then used in first resume.
        """
        rv = self._runtime._G.coroutine.create(self)
        rv._first = [args, kwargs]
        return rv


class LuaThread(LuaObject, Generator):
    """
    lua thread type wrapper.

    LuaThread is Generator-like.
    ``bool(thread)`` will returns True
    if the lua coroutine is not dead otherwise returns False.
    """

    def send(self, *args, **kwargs):
        """
        Sends arguments into lua coroutine.
        Returns next yielded value or raises StopIteration.

        This is an atomic operation.
        """
        if self._isfirst:
            if args in ((), (None,)) and not kwargs:
                return next(self)
            else:
                raise TypeError("can't send non-None value to a just-started generator")
        with self._runtime.lock():
            return self._send(*args, **kwargs)

    def _send(self, *args, **kwargs):
        if not self:
            raise StopIteration
        rv = self._runtime._G.coroutine.resume(self, *args, **kwargs)
        if rv is True:
            rv = (rv,)
        if rv[0]:
            rv = rv[1:]
            if len(rv) > 1:
                return rv
            elif len(rv) == 1:
                return rv[0]
            else:
                if not self:
                    raise StopIteration
                return
        else:
            try:
                stored = self._runtime._exception[1]
            except (IndexError, TypeError):
                pass
            else:
                if rv[1] is stored:
                    self._runtime._reraise_exception()
            self._runtime._clear_exception()
            raise LuaErr.new(self._runtime, None, rv[1], self._runtime.encoding)

    def __next__(self):
        """
        Returns next yielded value or raises StopIteration.

        This is an atomic operation.
        """
        with self._runtime.lock():
            a, k = self._first
            rv = self._send(*a, **k)
            self._first[0] = ()
            self._isfirst = False
            return rv

    def __init__(self, runtime, index):
        lib = runtime.lib
        self._first = [(), {}]
        self._isfirst = True
        super().__init__(runtime, index)
        with lock_get_state(runtime) as L:
            with ensure_stack_balance(runtime):
                self._pushobj()
                thread = lib.lua_tothread(L, -1)
                if lib.lua_status(thread) == lib.LUA_OK and lib.lua_gettop(thread) == 1:
                    lib.lua_pushvalue(thread, 1)
                    lib.lua_xmove(thread, L, 1)
                    self._func = LuaObject.new(runtime, -1)
                else:
                    self._func = None

    def __call__(self, *args, **kwargs) -> "LuaThread":
        """
        Behave like calling a coroutine factory.
        Returns a new LuaThread of the function of ``self``.
        Arguments will be stored then used in first resume.
        """
        if self._func is None:
            raise RuntimeError("original function not found")
        newthread = self._runtime._G.coroutine.create(self._func)
        newthread._first = [args, kwargs]
        return newthread

    def status(self) -> str:
        """
        Returns the status of lua coroutine.
        The return value is the same as the
        return value of ``coroutine.status``,
        decoded with ascii.
        """
        return self._runtime._G.coroutine.status(self, autodecode=False).decode("ascii")

    def __bool__(self):
        """
        Returns whether the lua coroutine is not dead.
        """
        return self.status() != "dead"

    def throw(self, typ, val=None, tb=None):
        """throw exceptions in LuaThread"""
        if val is None:
            val = typ()
        if tb is not None:
            val = val.with_traceback(tb)

        def raise_exc(*args):
            raise val

        with self._runtime.lock():
            self._runtime._G.debug.sethook(self, as_function(raise_exc), "c")
            try:
                return next(self)
            finally:
                self._runtime._G.debug.sethook(self)


class LuaUserdata(LuaCollection, LuaCallable):
    """
    Lua userdata type wrapper.
    """

    pass


class LuaVolatile(LuaObject):
    """
    Volatile ref to stack position.
    """

    def _ref_to_index(self, runtime, index):
        lib = runtime.lib
        with lock_get_state(self._runtime) as L:
            self._ref_to_key(lib.lua_absindex(L, index))

    def _pushobj(self):
        lib = self._runtime.lib
        with lock_get_state(self._runtime) as L:
            lib.lua_pushvalue(L, self._ref)

    def settle(self):
        return LuaObject.new(self._runtime, self._ref)

    def __del__(self):
        pass


class LuaView:
    """
    Base class of MappingView classes for LuaCollection.
    """

    def __init__(self, obj):
        """
        Init self with ``obj``, a LuaCollection object.
        """
        self._obj = obj

    def __len__(self):
        return len(self._obj)

    def __iter__(self):
        raise NotImplementedError


class LuaKView(LuaView):
    """
    KeysView for LuaCollection.
    """

    def __iter__(self):
        return LuaKIter(self._obj)


KeysView.register(LuaKView)


class LuaVView(LuaView):
    """
    ValuesView for LuaCollection.
    """

    def __iter__(self):
        return LuaVIter(self._obj)


ValuesView.register(LuaVView)


class LuaKVView(LuaView):
    """
    ItemsView for LuaCollection.
    """

    def __iter__(self):
        return LuaKVIter(self._obj)


ItemsView.register(LuaKVView)


class LuaIter(Iterator):
    """
    Base class of Iterator classes for LuaCollection.

    At init, lua function ``pairs`` will be called and
    iteration will be just like a "for in" in lua.
    """

    def __init__(self, obj):
        """
        Init self with ``obj``, a LuaCollection object.
        """
        super().__init__()
        self._info = list(obj._runtime._G.pairs(obj, keep=True))

    def __next__(self):
        _, obj, _ = self._info
        with obj._runtime.lock():
            func, obj, index = self._info
            rv = func(obj, index, keep=True)
            if isinstance(rv, LuaLimitedObject):
                raise StopIteration
            key, value = rv
            self._info[2] = key
            return self._filterkv(key.pull(), value.pull())

    def _filterkv(self, key, value):
        """the key-value filter"""
        raise NotImplementedError


class LuaKIter(LuaIter):
    """
    KeysIterator for LuaCollection.
    """

    def _filterkv(self, key, value):
        return key


class LuaVIter(LuaIter):
    """
    ValuesIterator for LuaCollection.
    """

    def _filterkv(self, key, value):
        return value


class LuaKVIter(LuaIter):
    """
    ItemsIterator for LuaCollection.
    """

    def _filterkv(self, key, value):
        return key, value


class Puller(Registry):
    """class Puller"""

    def __init__(self):
        super().__init__()
        self._default_puller = None

    def __call__(self, runtime, index, *, keep=False, **kwargs):
        """Pull the lua object at ``index`` into python"""
        lib = runtime.lib
        obj = LuaVolatile(runtime, index)
        if keep:
            return obj.settle()
        tp = obj._type()
        return self._find_puller(lib, tp)(runtime, obj, **kwargs)

    def _find_puller(self, lib, tp):
        for k, v in self.items():
            if getattr(lib, k) == tp:
                return v
        if self._default_puller is not None:
            return self._default_puller
        raise TypeError("cannot find puller for lua type '" + str(tp) + "'")

    def register_default(self, func):
        """register default puller"""
        self._default_puller = func


std_puller = Puller()


@std_puller.register("LUA_TNIL")
def _(runtime, obj, **kwargs):
    return None


@std_puller.register("LUA_TNUMBER")
def _(runtime, obj, **kwargs):
    try:
        i = LuaNumber.__int__(obj)
        f = LuaNumber.__float__(obj)
        return i if i == f else f
    except TypeError:
        return LuaNumber.__float__(obj)


@std_puller.register("LUA_TBOOLEAN")
def _(runtime, obj, **kwargs):
    return LuaBoolean.__bool__(obj)


@std_puller.register("LUA_TSTRING")
def _(runtime, obj, *, autodecode=None, **kwargs):
    if runtime.autodecode if autodecode is None else autodecode:
        return LuaString.__str__(obj)
    else:
        return LuaString.__bytes__(obj)


@std_puller.register_default
def _(runtime, obj, *, autounpack=True, keep_handle=False, **kwargs):
    lib = runtime.lib
    ffi = runtime.ffi
    with lock_get_state(runtime) as L:
        with ensure_stack_balance(runtime):
            obj._pushobj()
            if lib.lua_getmetatable(L, -1):
                lib.luaL_getmetatable(L, PYOBJ_SIG)
                if lib.lua_rawequal(L, -2, -1):
                    handle = ffi.cast("void**", lib.lua_topointer(L, -3))[0]
                    if keep_handle:
                        return handle
                    obj = ffi.from_handle(handle)
                    del handle
                    if isinstance(obj, Py2LuaProtocol) and autounpack:
                        obj = obj.obj
                    return obj
    return obj.settle()


class Proxy:
    """base class for proxies"""

    def __init__(self, obj: LuaCollection):
        """make a proxy for ``obj``"""
        object.__setattr__(self, "_obj", obj)


def unproxy(proxy: Proxy):
    """unwrap a proxy object"""
    return object.__getattribute__(proxy, "_obj")


class ListProxy(Proxy, MutableSequence):
    """list-like proxy"""

    @staticmethod
    def _raise_type(obj):
        raise TypeError(
            "list indices must be integers or slices, not " + type(obj).__name__
        )

    def _process_index(self, index, check_index=True):
        if index >= len(self):
            if check_index:
                raise IndexError("list index out of range")
            else:
                index = len(self)
        if index < 0:
            index += len(self)
        if index < 0:
            if check_index:
                raise IndexError("list index out of range")
            else:
                index = 0
        return index + 1

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._obj[self._process_index(item)]
        elif isinstance(item, slice):
            return self.__class__(
                self._obj._runtime.table_from(
                    self[i] for i in range(*item.indices(len(self)))
                )
            )
        else:
            self._raise_type(item)

    def __setitem__(self, key, value):
        if isinstance(key, int):
            self._obj[self._process_index(key)] = value
        else:
            self._raise_type(key)

    def __delitem__(self, key):
        if isinstance(key, int):
            del self._obj[self._process_index(key)]
        elif isinstance(key, slice):
            for i in sorted(range(*key.indices(len(self))), reverse=True):
                del self[i]
        else:
            self._raise_type(key)

    def __len__(self):
        return len(self._obj)

    def insert(self, index, value):
        self._obj._runtime._G.table.insert(
            self._obj, self._process_index(index, False), value
        )


class ObjectProxy(Proxy):
    """object-like proxy"""

    def __getattribute__(self, item):
        return unproxy(self)[item]

    def __setattr__(self, key, value):
        unproxy(self)[key] = value

    def __delattr__(self, item):
        del unproxy(self)[item]


class StrictObjectProxy(ObjectProxy):
    """strict object-like proxy. Treat "nil" attr value as no such attr."""

    def __getattribute__(self, item):
        rv = unproxy(self)[item]
        if rv is None:
            raise AttributeError(
                "'{!r}' has no attribute '{}' or it's nil".format(unproxy(self), item)
            )
        else:
            return rv


class DictProxy(Proxy, MutableMapping):
    """dict-like proxy. Treat "nil" value as no such item."""

    def __getitem__(self, item):
        rv = self._obj[item]
        if rv is None:
            raise KeyError(item)
        else:
            return rv

    def __setitem__(self, key, value):
        self._obj[key] = value

    def __delitem__(self, key):
        self._obj[key] = self._obj._runtime.nil

    def __iter__(self):
        yield from self._obj

    def __len__(self):
        i = 0
        for i, _ in zip(itertools.count(1), self):
            pass
        return i


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
            raise ValueError("wrong instance (use 'foo:bar()' to call method, not 'foo.bar()')")
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
    if hasattr(obj.__class__, "__getitem__"):
        return as_itemgetter(obj)
    else:
        return as_attrgetter(obj)


_PushInfo = namedtuple("_PushInfo", ("runtime", "L", "obj", "kwargs", "pusher"))


class PushInfo(_PushInfo):
    def with_new_obj(self, new_obj):
        d = self._asdict()
        d["obj"] = new_obj
        return self.__class__(**d)


class Pusher(Registry):
    """class Pusher"""

    @staticmethod
    def _convert_func(func):
        @functools.wraps(func)
        def _(obj, pi):
            return func(pi)

        return _

    @staticmethod
    def _convert_call(func):
        @functools.wraps(func)
        def _(pi):
            return func(pi.obj, pi)

        return _

    def __init__(self):
        super().__init__()
        self._default_func = None

        def fallback(pi):
            if self._default_func is not None:
                return self._default_func(pi)
            else:
                raise TypeError(
                    "no pusher registered for type '" + type(pi.obj).__name__ + "'"
                )

        self._fallback = fallback
        self._func = functools.singledispatch(self._convert_func(self._fallback))
        self.internal_push = self._convert_call(self._func)

    def __call__(self, runtime, obj, **kwargs):
        """push ``obj`` to lua"""
        with lock_get_state(runtime) as L:
            return self.internal_push(PushInfo(runtime, L, obj, kwargs, self))

    def register_default(self, func):
        """register default pusher"""
        self._default_func = func

    def __setitem__(self, key, value):
        self._func.register(key)(self._convert_func(value))
        super().__setitem__(key, value)

    def __delitem__(self, key):
        raise NotImplementedError("cannot delete a registered pusher")

    def copy(self):
        o = self.__class__()
        o.update(self)
        o.register_default(self._default_func)
        return o


std_pusher = Pusher()


@std_pusher.register_default
def _(pi):
    return pi.pusher.internal_push(pi.with_new_obj(as_is(pi.obj)))


@std_pusher.register(LuaObject)
def _(pi):
    with lock_get_state(pi.obj._runtime) as fr:
        pi.obj._pushobj()
        if fr != pi.L:
            pi.runtime.lib.lua_xmove(fr, pi.L, 1)


@std_pusher.register(bool)
def _(pi):
    pi.runtime.lib.lua_pushboolean(pi.L, int(pi.obj))


@std_pusher.register(int)
def _(pi):
    if pi.runtime.ffi.cast("lua_Integer", pi.obj) == pi.obj:
        pi.runtime.lib.lua_pushinteger(pi.L, pi.obj)
    else:
        return pi.pusher.internal_push(pi.with_new_obj(as_is(pi.obj)))


@std_pusher.register(float)
def _(pi):
    pi.runtime.lib.lua_pushnumber(pi.L, pi.obj)


@std_pusher.register(str)
def _(pi):
    if pi.runtime.encoding is None:
        raise ValueError("encoding not specified")
    else:
        b = pi.obj.encode(pi.runtime.encoding)
        return pi.pusher.internal_push(pi.with_new_obj(b))


@std_pusher.register(bytes)
def _(pi):
    pi.runtime.lib.lua_pushlstring(pi.L, pi.obj, len(pi.obj))


@std_pusher.register(type(None))
def _(pi):
    pi.runtime.lib.lua_pushnil(pi.L)


@std_pusher.register(Py2LuaProtocol)
def _(pi):
    ffi = pi.runtime.ffi
    lib = pi.runtime.lib
    if pi.obj.push_protocol == PushProtocol.Naked:
        obj = pi.obj.obj
    elif callable(pi.obj.push_protocol):
        return pi.obj.push_protocol(pi)
    else:
        obj = pi.obj
    handle = ffi.new_handle(obj)
    ffi.cast("void**", lib.lua_newuserdata(pi.L, ffi.sizeof(handle)))[0] = handle
    if pi.kwargs.get("set_metatable", True):
        pi.runtime.refs.add(handle)
        lib.luaL_setmetatable(pi.L, PYOBJ_SIG)
    return handle


@std_pusher.register(Proxy)
def _(pi):
    return pi.pusher.internal_push(pi.with_new_obj(unproxy(pi.obj)))


def caller(ffi, lib, L):
    try:
        runtime = ffi.from_handle(
            ffi.cast("void**", lib.lua_topointer(L, lib.lua_upvalueindex(1)))[0]
        )
        pyobj = ffi.from_handle(
            ffi.cast("void**", lib.lua_topointer(L, lib.lua_upvalueindex(2)))[0]
        )
        bk = runtime._state
        runtime._state = L
        rv = pyobj(
            runtime,
            *[
                LuaObject.new(runtime, index)
                for index in range(1, lib.lua_gettop(L) + 1)
            ],
        )
        lib.lua_settop(L, 0)
        if not isinstance(rv, tuple):
            rv = (rv,)
        for v in rv:
            runtime.push(v)
        return len(rv)
    except BaseException as e:
        runtime.push(e)
        runtime._store_exception()
        return -1
    finally:
        try:
            runtime._state = bk
        except UnboundLocalError:
            pass


PYOBJ_SIG = b"PyObject"


class Metatable(Registry):
    """class Metatable"""

    @staticmethod
    def init_lib(ffi, lib):
        """prepare lua lib for setting up metatable"""
        ffi.def_extern("_caller_server")(partial(caller, ffi, lib))

    def init_runtime(self, runtime):
        """set up metatable on ``runtime``"""
        lib = runtime.lib
        ffi = runtime.ffi
        self.init_lib(ffi, lib)
        client = lib._get_caller_client()
        with lock_get_state(runtime) as L:
            with ensure_stack_balance(runtime):
                lib.luaL_newmetatable(L, PYOBJ_SIG)
                for name, func in self.items():
                    lib.lua_pushstring(L, name)
                    runtime.push(as_is(runtime))
                    runtime.push(as_is(func))
                    lib.lua_pushcclosure(L, client, 2)
                    lib.lua_rawset(L, -3)


def normal_args(func):
    @functools.wraps(func)
    def _(runtime, *args):
        return func(*[arg.pull() for arg in args])

    return _


def binary_op(func):
    @normal_args
    @functools.wraps(func)
    def _(o1, o2):
        return func(o1, o2)

    return _


def unary_op(func):
    @normal_args
    @functools.wraps(func)
    def _(o1, o2=None):
        return func(o1)

    return _


std_metatable = Metatable()

std_metatable.update(
    {
        b"__add": binary_op(operator.add),
        b"__sub": binary_op(operator.sub),
        b"__mul": binary_op(operator.mul),
        b"__div": binary_op(operator.truediv),
        b"__mod": binary_op(operator.mod),
        b"__pow": binary_op(operator.pow),
        b"__unm": unary_op(operator.neg),
        b"__idiv": binary_op(operator.floordiv),
        b"__band": binary_op(operator.and_),
        b"__bor": binary_op(operator.or_),
        b"__bxor": binary_op(operator.xor),
        b"__bnot": unary_op(operator.invert),
        b"__shl": binary_op(operator.lshift),
        b"__shr": binary_op(operator.rshift),
        b"__len": unary_op(len),
        b"__eq": binary_op(operator.eq),
        b"__lt": binary_op(operator.lt),
        b"__le": binary_op(operator.le),
        b"__concat": binary_op(lambda a, b: str(a) + str(b)),
    }
)


@std_metatable.register(b"__call")
def _(runtime, obj, *args):
    return obj.pull(autounpack=False)(*[arg.pull() for arg in args])


@std_metatable.register(b"__index")
def _(runtime, obj, key):
    wrap = obj.pull(autounpack=False)
    ukey = key.pull(autodecode=True)
    dkey = key.pull()
    obj = obj.pull()
    wrap = wrap if isinstance(wrap, IndexProtocol) else autopackindex(obj)
    protocol = wrap.index_protocol
    if protocol == IndexProtocol.ATTR:
        result = getattr(obj, ukey, runtime.nil)
    elif protocol == IndexProtocol.ITEM:
        try:
            result = obj[dkey]
        except LookupError:
            return runtime.nil
    else:
        raise ValueError("unexpected index_protocol {}".format(protocol))
    if (
        protocol == IndexProtocol.ATTR
        and callable(result)
        and hasattr(result, "__self__")
        and getattr(result, "__self__") is obj
    ):
        return MethodProtocol(result, obj)
    else:
        return result


@std_metatable.register(b"__newindex")
def _(runtime, obj, key, value):
    wrap = obj.pull(autounpack=False)
    obj = obj.pull()
    wrap = wrap if isinstance(wrap, IndexProtocol) else autopackindex(obj)
    protocol = wrap.index_protocol
    value = value.pull()
    if protocol == IndexProtocol.ATTR:
        setattr(obj, key.pull(autodecode=True), value)
    elif protocol == IndexProtocol.ITEM:
        obj[key.pull()] = value
    else:
        raise ValueError("unexpected index_protocol {}".format(protocol))


@std_metatable.register(b"__tostring")
def _(runtime, obj):
    return str(obj.pull())


@std_metatable.register(b"__gc")
def _(runtime, obj):
    runtime.refs.discard(obj.pull(keep_handle=True))


@std_metatable.register(b"__pairs")
def _(runtime, obj):
    obj = obj.pull()
    if isinstance(obj, Mapping):
        it = obj.items()
    elif isinstance(obj, ItemsView):
        it = obj
    else:
        it = enumerate(obj)

    it, it2, it_bk = itertools.tee(it, 3)
    started = False

    def next_or_none(it):
        try:
            return next(it)
        except StopIteration:
            return None

    def nnext(o, index=None):
        nonlocal it, it2, it_bk, started
        indexs = [index]
        if isinstance(index, str):
            try:
                indexs.append(index.encode(runtime.encoding))
            except UnicodeEncodeError:
                pass
        elif isinstance(index, bytes):
            try:
                indexs.append(index.decode(runtime.encoding))
            except UnicodeDecodeError:
                pass

        if index == None and not started:
            started = True
            return next_or_none(it)
        else:
            try:
                k, v = next(it2)
            except StopIteration:
                it, it2, it_bk = itertools.tee(it_bk, 3)
                try:
                    k, v = next(it2)
                except StopIteration:
                    return None
            if k in indexs:
                return next_or_none(it)
            else:
                it, it2, it_bk = itertools.tee(it_bk, 3)
                if index == None:
                    return next_or_none(it)
                else:
                    k, v = next(it)
                    while k not in indexs:
                        next(it2)
                        try:
                            k, v = next(it)
                        except StopIteration:
                            return None
                    next(it2)
                    return next_or_none(it)

    return as_function(nnext), obj, None


LuaError = LuaErr
LuaSyntaxError = LuaErrSyntax


def unpacks_arg_table(args):
    """unpacks lua table in args"""
    da, dk = [], {}
    if len(args) != 1:
        da = args
    else:
        arg = args[0]
        if isinstance(arg, LuaTable):
            lp = ListProxy(arg)
            da.extend(lp)
            llp = len(lp)
            for k, v in arg.items():
                if not isinstance(k, int) or k < 1 or k > llp:
                    if isinstance(k, bytes):
                        k = k.decode(arg._runtime.encoding)
                    dk[k] = v
        else:
            da = args
    return tuple(da), dk


def unpacks_lua_table(func):
    """
    A decorator for function. Unpacks lua tables in args.
    """

    @functools.wraps(func)
    def newfunc(*args):
        da, dk = unpacks_arg_table(args)
        return func(*da, **dk)

    return newfunc


def unpacks_lua_table_method(func):
    """
    A decorator for method. Unpacks lua tables in args.
    """

    @functools.wraps(func)
    def newfunc(self, *args):
        da, dk = unpacks_arg_table(args)
        return func(self, *da, **dk)

    return newfunc


def lua_type(obj):
    """
    Returns the typename of the lua object, decoded with
    ascii. Returns None for other python objects.
    """
    if isinstance(obj, LuaObject):
        return obj.typename()
    else:
        return None


class LockContext:
    """lock context for runtime used in ``with`` statement"""

    def __init__(self, runtime):
        self._runtime = runtime

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_value, traceback):
        self._runtime.unlock()


class LuaRuntime(NotCopyable):
    """
    LuaRuntime is the wrapper of main thread "lua_State".
    One process can open multiple LuaRuntime instances.
    LuaRuntime is thread-safe.
    """

    def __init__(
        self,
        encoding: str = sys.getdefaultencoding(),
        source_encoding: Optional[str] = None,
        autodecode: Optional[bool] = None,
        lualib=None,
        metatable=std_metatable,
        pusher=std_pusher,
        puller=std_puller,
        lua_state=None,
        lock=None,
    ):
        """
        Init a LuaRuntime instance.
        This will call ``luaL_newstate`` to open a "lua_State"
        and do some init work.

        :param encoding: the encoding to encode and decode lua string
        :param source_encoding: the encoding to encoding lua code
        :param autodecode: whether automatically decode strings returned from lua functions
        :param lualib: the lua lib. Default is the return value of :py:func:`ffilupa.lualibs.get_default_lualib`
        :param metatable: the metatable for python objects. Default is :py:data:`ffilupa.metatable.std_metatable`
        :param pusher: the pusher to push objects to lua. Default is :py:data:`ffilupa.metatable.std_pusher`
        :param puller: the pulled to pull objects from lua. Default is :py:data:`ffilupa.metatable.std_puller`
        """
        super().__init__()
        self.push = lambda obj, **kwargs: pusher(self, obj, **kwargs)
        self.pull = lambda index, **kwargs: puller(self, index, **kwargs)
        self._newlock(lock)
        with self.lock():
            self._exception = None
            self.compile_cache = {}
            self.refs = set()
            self._setencoding(
                encoding, source_encoding or encoding or sys.getdefaultencoding()
            )
            if autodecode is None:
                autodecode = encoding is not None
            self.autodecode = autodecode
            self._initlua(lualib)
            if lua_state is None:
                self._newstate()
                self._openlibs()
            else:
                self._state = self.ffi.cast("lua_State*", lua_state)
            self._init_metatable(metatable)
            self._init_pylib()
            self._exception = None
            self._nil = LuaNil(self)
            self._G_ = self.globals()
            self._inited = True

    def lock(self):
        """
        Lock the runtime and returns a context manager which
        unlocks the runtime when exiting.
        All operations to the runtime will automatically lock
        the runtime. It's not necessary for common users.
        """
        self._lock.acquire()
        return LockContext(self)

    def unlock(self):
        """
        Unlock the runtime.
        """
        self._lock.release()

    def _newlock(self, lock):
        """make a lock"""
        if lock is None:
            self._lock = RLock()
        else:
            self._lock = lock

    def _newstate(self):
        """open a lua state"""
        self._state = L = self.lib.luaL_newstate()
        if L == self.ffi.NULL:
            raise RuntimeError('"luaL_newstate" returns NULL')

    def _openlibs(self):
        """open lua stdlibs"""
        self.lib.luaL_openlibs(self.lua_state)

    def _init_metatable(self, metatable):
        metatable.init_runtime(self)

    @property
    def lua_state(self):
        """
        The original "lua_State" object. It can be used directly
        in low-level lua APIs. Common users should not get and use it.

        To make it thread-safe, one must lock the runtime before
        doing any operation on the lua state and unlock after.
        Use the helper :py:func:`ffilupa.util.lock_get_state` instead.

        It's recommended to ensure the lua stack unchanged after
        operations. Use the helpers :py:func:`ffilupa.util.assert_stack_balance`
        and :py:func:`ffilupa.util.ensure_stack_balance`.
        """
        return self._state

    def _setencoding(self, encoding, source_encoding):
        """set the encoding"""
        self.encoding = encoding
        self.source_encoding = source_encoding

    def __del__(self):
        """close lua state"""
        if getattr(self, "_inited", False):
            with self.lock():
                if self.lua_state:
                    self.lib.lua_close(self.lua_state)
                    self._state = None

    def _store_exception(self):
        """store the exception raised"""
        self._exception = sys.exc_info()

    def _reraise_exception(self):
        """reraise the exception stored if there is"""
        with self.lock():
            try:
                if self._exception:
                    reraise(*self._exception)
            finally:
                self._clear_exception()

    def _clear_exception(self):
        """clear the stored exception"""
        with self.lock():
            self._exception = None

    def _pushvar(self, *names):
        """push variable with name ``'.'.join(names)`` in lua
        to the top of stack. raise TypeError if some object is
        not indexable in the chain"""
        with lock_get_state(self) as L:
            self.lib.lua_pushglobaltable(L)
            namebuf = []
            for name in names:
                if isinstance(name, str):
                    name = name.encode(self.encoding)
                if not self.lib.lua_istable(L, -1) and not hasmetafield(
                    self, -1, b"__index"
                ):
                    self.lib.lua_pop(L, 1)
                    raise TypeError(
                        "'{}' is not indexable".format(
                            ".".join(
                                [
                                    x.decode(self.encoding)
                                    if isinstance(x, bytes)
                                    else x
                                    for x in namebuf
                                ]
                            )
                        )
                    )
                self.push(name)
                self.lib.lua_gettable(L, -2)
                self.lib.lua_remove(L, -2)
                namebuf.append(name)

    def compile_path(self, pathname):
        """compile lua source file"""
        if not isinstance(pathname, (str, bytes)):
            pathname = str(pathname)
        if isinstance(pathname, str):
            pathname = os.fsencode(pathname)
        with lock_get_state(self) as L:
            with ensure_stack_balance(self):
                status = self.lib.luaL_loadfile(L, pathname)
                obj = self.pull(-1)
                if status != self.lib.LUA_OK:
                    raise LuaErr.new(self, status, obj, self.encoding)
                else:
                    return obj

    def compile(self, code, name=b"=python"):
        """compile lua code"""
        if isinstance(code, str):
            code = code.encode(self.source_encoding)
        with lock_get_state(self) as L:
            with ensure_stack_balance(self):
                status = self.lib.luaL_loadbuffer(L, code, len(code), name)
                obj = self.pull(-1)
                if status != self.lib.LUA_OK:
                    raise LuaErr.new(self, status, obj, self.encoding)
                else:
                    return obj

    def execute(self, code, *args):
        """
        Execute lua source code. This is the same as
        ``compile(code)(*args)``.
        """
        return self.compile(code)(*args)

    def eval(self, code, *args):
        """
        Eval lua expression. This is the same as
        ``execute('return ' + code, *args)``.
        """
        if isinstance(code, bytes):
            code = b"return " + code
        else:
            code = "return " + code
            code = code.encode(self.source_encoding)
        return self.execute(code, *args)

    def globals(self):
        """
        Returns the global table in lua.
        """
        with lock_get_state(self) as L:
            with ensure_stack_balance(self):
                self.lib.lua_pushglobaltable(L)
                return self.pull(-1)

    def table(self, *args, **kwargs):
        """
        Make a lua table. This is the same as
        ``table_from(args, kwargs)``.
        """

        return self.table_from(args, kwargs)

    def table_from(self, *args):
        """
        Make a lua table from ``args``. items in ``args`` are
        Iterable or Mapping or ItemsView.
        Mapping and ItemsView objects are joined and
        entries will be set in the resulting lua table.
        Other Iterable objects are chained and set to the lua
        table with index *starting from 1*.
        """
        lib = self.lib
        narr = nres = 0
        for obj in args:
            if isinstance(obj, (Mapping, ItemsView)):
                nres += operator.length_hint(obj)
            else:
                narr += operator.length_hint(obj)
        with lock_get_state(self) as L:
            with ensure_stack_balance(self):
                lib.lua_createtable(L, narr, nres)
                i = 1
                for obj in args:
                    if isinstance(obj, Mapping):
                        obj = obj.items()
                    if isinstance(obj, ItemsView):
                        for k, v in obj:
                            self.push(k)
                            self.push(v)
                            lib.lua_rawset(L, -3)
                    else:
                        for item in obj:
                            self.push(item)
                            lib.lua_rawseti(L, -2, i)
                            i += 1
                return LuaTable(self, -1)

    def _init_pylib(self):
        """
        This method will be called at init time to setup
        the ``python`` module in lua.
        """

        def keep_return(func):
            @functools.wraps(func)
            def _(*args, **kwargs):
                return as_is(func(*args, **kwargs))

            return _

        pack_table = self.eval(
            """
            function(tb)
                return function(s, ...)
                    return tb({s}, ...)
                end
            end"""
        )

        def setitem(d, k, v):
            d[k] = v

        def delitem(d, k):
            del d[k]

        def getitem(d, k, *args):
            try:
                return d[k]
            except LookupError:
                if args:
                    return args[0]
                else:
                    reraise(*sys.exc_info())

        self.globals()[b"python"] = self.globals()[b"package"][b"loaded"][
            b"python"
        ] = self.table_from(
            {
                b"as_attrgetter": as_attrgetter,
                b"as_itemgetter": as_itemgetter,
                b"as_is": as_is,
                b"as_function": as_function,
                b"as_method": as_method,
                b"none": as_is(None),
                b"eval": eval,
                b"builtins": importlib.import_module("builtins"),
                b"next": next,
                b"import_module": importlib.import_module,
                b"table_arg": unpacks_lua_table,
                b"keep_return": keep_return,
                b"to_luaobject": pack_table(
                    lambda o: as_is(o.__getitem__(1, keep=True))
                ),
                b"to_bytes": pack_table(
                    lambda o: as_is(o.__getitem__(1, autodecode=False))
                ),
                b"to_str": pack_table(
                    lambda o, encoding=None: as_is(
                        o.__getitem__(1, autodecode=False).decode(
                            self.encoding
                            if encoding is None
                            else encoding
                            if isinstance(encoding, str)
                            else encoding.decode(self.encoding)
                        )
                    )
                ),
                b"table_keys": lambda o: o.keys(),
                b"table_values": lambda o: o.values(),
                b"table_items": lambda o: o.items(),
                b"to_list": lambda o: list(o.values()),
                b"to_tuple": lambda o: tuple(o.values()),
                b"to_dict": lambda o: dict(o.items()),
                b"to_set": lambda o: set(o.values()),
                b"setattr": setattr,
                b"getattr": getattr,
                b"delattr": delattr,
                b"setitem": setitem,
                b"getitem": getitem,
                b"delitem": delitem,
                b"ffilupa": importlib.import_module(__package__),
                b"runtime": self,
            }
        )

    def require(self, *args, **kwargs):
        """
        The same as ``._G.require()``. Load a lua module.
        """
        return self._G.require(*args, **kwargs)

    @property
    def _G(self):
        """
        The global table in lua.
        """
        return self._G_

    @property
    def nil(self):
        """
        nil value in lua.
        """
        return self._nil

    def _initlua(self, lualib):
        if lualib is None:
            lualib = get_default_lualib()
        self.lualib = lualib
        self.luamod = lualib.import_mod()

    @property
    def lib(self):
        """lib object of CFFI"""
        return self.luamod.lib

    @property
    def ffi(self):
        """ffi object of CFFI"""
        return self.luamod.ffi

    def close(self):
        """close this LuaRuntime"""
        with lock_get_state(self) as L:
            self._state = None
            self.lib.lua_close(L)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class VoidLock:
    def acquire(self, blocking=True, timeout=-1):
        pass

    def release(self):
        pass
