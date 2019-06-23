import abc
import functools
import importlib
import itertools
import operator
import os
import sys
import types
from collections import UserDict
from contextlib import contextmanager
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import *
from typing import NoReturn

import dataclasses
from dataclasses import dataclass

from . import lualibs as _lualibs
from .__version__ import __version__
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
    "unproxy",
    "ListProxy",
    "ObjectProxy",
    "StrictObjectProxy",
    "DictProxy",
) + _lualibs.__all__


class LuaErr(Exception):
    """
    Base exception class for errors raised in Lua.

    Instance variables:
        * ``status``: The return value of failed Lua API call.
        * ``err_msg``: The error message got from Lua.
    """

    @staticmethod
    def new(
        runtime: "LuaRuntime",
        status: Optional[int],
        err_msg: Union[str, bytes],
        encoding: Optional[str] = None,
    ) -> "LuaErr":
        """
        Create an instance of one of the subclasses of LuaErr according to ``status``.
        Attempt to decode ``err_msg`` if it's bytes, even if ``encoding`` is None.
        """

        if isinstance(err_msg, bytes):
            if encoding is not None:
                err_msg = err_msg.decode(encoding)
            else:
                err_msg = err_msg.decode("utf8", "replace")
        return {
            runtime.lib.LUA_OK: LuaOK,
            runtime.lib.LUA_YIELD: LuaYield,
            runtime.lib.LUA_ERRRUN: LuaErrRun,
            runtime.lib.LUA_ERRSYNTAX: LuaErrSyntax,
            runtime.lib.LUA_ERRMEM: LuaErrMem,
            runtime.lib.LUA_ERRGCMM: LuaErrGCMM,
            runtime.lib.LUA_ERRERR: LuaErrErr,
        }.get(status, LuaErr)(status, err_msg)

    def __init__(self, status: int, err_msg: str) -> None:
        super().__init__(status, err_msg)
        self.status, self.err_msg = status, err_msg

    def __repr__(self):
        return f"{self.__class__.__name__}: status {self.status}\n{self.err_msg}"

    def __str__(self):
        return self.err_msg


class LuaOK(LuaErr):
    pass


class LuaYield(LuaErr):
    pass


class LuaErrRun(LuaErr):
    pass


class LuaErrSyntax(LuaErr):
    pass


class LuaErrMem(LuaErr):
    pass


class LuaErrGCMM(LuaErr):
    pass


class LuaErrErr(LuaErr):
    pass


def partial(func, *frozenargs):
    """Equivalent to :py:func:`functools.partial`. Repaired for lambda."""

    @functools.wraps(func)
    def newfunc(*args):
        return func(*(frozenargs + args))

    return newfunc


class NotCopyable:
    """
    A base class for not copyable instances.
    Copying the instance will raise a TypeError.
    """

    def __copy__(self) -> NoReturn:
        raise TypeError(
            f"'{self.__class__.__module__}.{self.__class__.__name__}' is not copyable."
        )

    def __deepcopy__(self, memo) -> NoReturn:
        raise TypeError(
            f"'{self.__class__.__module__}.{self.__class__.__name__}' is not copyable."
        )


def reraise(tp, value, tb=None):
    # Copyright (c) 2010-2018 Benjamin Peterson
    if value is None:
        value = tp()
    if value.__traceback__ is not tb:
        raise value.with_traceback(tb)
    raise value


class Registry(UserDict):
    def register(self, name):
        """A decorator to register function to the dict."""

        def _(func):
            self[name] = func
            return func

        return _


def ensure_strpath(path: Union[str, os.PathLike]) -> str:
    """Cast path to str."""
    return path if isinstance(path, str) else path.__fspath__()


def ensure_pathlib_path(path: Union[str, os.PathLike]) -> Path:
    """Cast path to ``pathlib.Path``."""
    return Path(ensure_strpath(path))


def ensure_bytespath(path: Union[str, bytes, os.PathLike]) -> bytes:
    """Cast path to bytes."""
    return path if isinstance(path, bytes) else os.fsencode(ensure_strpath(path))


exec(
    '''\
# Copyright (c) 2001-2019 Python Software Foundation. All rights reserved.
# Copyright (c) 2000 BeOpen.com. All rights reserved.
# Copyright (c) 1995-2001 Corporation for National Research Initiatives. All rights reserved.
# Copyright (c) 1991-1995 Stichting Mathematisch Centrum. All rights reserved.

def replace(*args, **changes):
    """Return a new object replacing specified fields with new values.
    This is especially useful for frozen classes.  Example usage:
      @dataclass(frozen=True)
      class C:
          x: int
          y: int
      c = C(1, 2)
      c1 = replace(c, x=3)
      assert c1.x == 3 and c1.y == 2
      """
    if len(args) > 1:
        raise TypeError(f'replace() takes 1 positional argument but {len(args)} were given')
    if args:
        obj, = args
    elif 'obj' in changes:
        obj = changes.pop('obj')
        import warnings
        warnings.warn("Passing 'obj' as keyword argument is deprecated",
                      DeprecationWarning, stacklevel=2)
    else:
        raise TypeError("replace() missing 1 required positional argument: 'obj'")

    # We're going to mutate 'changes', but that's okay because it's a
    # new dict, even if called with 'replace(obj, **my_changes)'.

    if not _is_dataclass_instance(obj):
        raise TypeError("replace() should be called on dataclass instances")

    # It's an error to have init=False fields in 'changes'.
    # If a field is not in 'changes', read its value from the provided obj.

    for f in getattr(obj, _FIELDS).values():
        # Only consider normal fields or InitVars.
        if f._field_type is _FIELD_CLASSVAR:
            continue

        if not f.init:
            # Error if this field is specified in changes.
            if f.name in changes:
                raise ValueError(f'field {f.name} is declared with '
                                 'init=False, it cannot be specified with '
                                 'replace()')
            continue

        if f.name not in changes:
            if f._field_type is _FIELD_INITVAR:
                raise ValueError(f"InitVar {f.name!r} "
                                 'must be specified with replace()')
            changes[f.name] = getattr(obj, f.name)

    # Create the new object, which calls __init__() and
    # __post_init__() (if defined), using all of the init fields we've
    # added and/or left in 'changes'.  If there are values supplied in
    # changes that aren't fields, this will correctly raise a
    # TypeError.
    return obj.__class__(**changes)
replace.__text_signature__ = '(obj, /, **kwargs)'
''',
    dataclasses.__dict__,
)


class LuaLimitedObject(NotCopyable):
    """
    Class LuaLimitedObject, the base class of LuaObject.
    """

    def _ref_to_key(self, key) -> None:
        self._ref = key

    def _ref_to_index(self, runtime: "LuaRuntime", index: int) -> None:
        lib = runtime.lib
        ffi = runtime.ffi
        with runtime.get_state(1) as L:
            index: int = lib.lua_absindex(L, index)
            key = ffi.new("char*")
            lib.lua_pushlightuserdata(L, key)
            lib.lua_pushvalue(L, index)
            lib.lua_rawset(L, lib.LUA_REGISTRYINDEX)
            self._ref_to_key(key)

    def __init__(self, runtime: "LuaRuntime", index: int) -> None:
        """
        Init a Lua object wrapper for the Lua object in ``runtime`` at ``index``.

        :param runtime: The Lua runtime.
        :param index: The index of the Lua object in the Lua stack.

        Will not change the Lua stack.
        The lifetime of the wrapped Lua object will depend on the wrapper.
        """
        super().__init__()
        self._runtime = runtime
        self._ref_to_index(runtime, index)

    @staticmethod
    def new(runtime: "LuaRuntime", index: int) -> "LuaObject":
        """Create an instance of one of the subclasses of LuaObject according to the type of that Lua object."""
        lib = runtime.lib
        with runtime.get_state(0) as L:
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

    def __del__(self) -> None:
        key = self._ref
        lib = self._runtime.lib
        with self._runtime.get_state(1) as L:
            if L:
                lib.lua_pushlightuserdata(L, key)
                lib.lua_pushnil(L)
                lib.lua_rawset(L, lib.LUA_REGISTRYINDEX)

    def _pushobj_nts(self) -> None:
        """Push the lua object onto the top of stack."""
        key = self._ref
        lib = self._runtime.lib
        with self._runtime.get_state(0, lock=False) as L:
            lib.lua_pushlightuserdata(L, key)
            lib.lua_rawget(L, lib.LUA_REGISTRYINDEX)

    def __bool__(self) -> bool:
        """Convert to bool using lua_toboolean."""
        lib = self._runtime.lib
        with self._runtime.get_state(2) as L:
            self._pushobj_nts()
            return bool(lib.lua_toboolean(L, -1))

    def _type(self) -> int:
        """Get the type id of the lua object."""
        lib = self._runtime.lib
        with self._runtime.get_state(2) as L:
            self._pushobj_nts()
            return lib.lua_type(L, -1)

    def pull(self, **kwargs) -> Any:
        """Pull the Lua object to Python."""
        with self._runtime.lock():
            self._pushobj_nts()
            return self._runtime.pull(-1, **kwargs)


def not_impl(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, LuaErrRun):
        err_msg = exc_value.err_msg
        lns = err_msg.split("\n")
        if len(lns) == 3:
            return NotImplemented
    reraise(exc_type, exc_value, exc_traceback)


_method_template = """\
def {name}({outer_args}, **kwargs):
    runtime = self._runtime
    lib = runtime.lib
    with runtime.get_state(2) as L:
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
    """Base class for Lua object wrappers."""

    def typename(self) -> str:
        """Get the type name of the wrapped Lua object."""
        runtime = self._runtime
        lib = runtime.lib
        ffi = runtime.ffi
        with runtime.get_state(2) as L:
            self._pushobj_nts()
            return ffi.string(lib.lua_typename(L, lib.lua_type(L, -1))).decode()

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

    def __init__(self, runtime: "LuaRuntime", index: int) -> None:
        super().__init__(runtime, index)
        self._edit_mode = False

    def _tostring(self, *, autodecode: bool = False, **kwargs) -> Union[str, bytes]:
        return self._runtime._G.tostring(self, autodecode=autodecode, **kwargs)

    def __bytes__(self) -> bytes:
        return self._tostring(autodecode=False)

    def __str__(self) -> str:
        if self._runtime.encoding is not None:
            return bytes(self).decode(self._runtime.encoding)
        else:
            raise ValueError("Encoding not specified.")


_index_template = """\
def {name}({args}, **kwargs):
    runtime = self._runtime
    lib = runtime.lib
    with runtime.get_state(2) as L:
        lib.lua_pushcfunction(L, lib._get_index_client())
        return LuaCallable.__call__(LuaVolatile(runtime, -1), {op}, {args}, **kwargs)
"""


class LuaCollection(LuaObject):
    """
    Lua collection type wrapper. ("table" and "userdata")

    LuaCollection is dict-like and support item getting/setting.
    Item getting/setting will operate on the wrapped Lua object.
    Getting/setting through attributes is also supported.
    The same name Python attributes will override that in Lua.

    The indexing key will be encoded with ``encoding``
    specified in Lua runtime if it's a str.
    """

    exec(_index_template.format(name="__len__", op=0, args="self"))
    exec(_index_template.format(name="__getitem__", op=1, args="self, name"))
    exec(_index_template.format(name="__setitem__", op=2, args="self, name, value"))

    def __delitem__(self, name):
        if isinstance(name, int):
            self._runtime._G.table.remove(self, name)
        else:
            self[name] = self._runtime.nil

    def _attr_filter(self, name: str) -> bool:
        return (
            self.__dict__.get("_edit_mode", True) is False and name not in self.__dict__
        )

    def __getattr__(self, name):
        if self._attr_filter(name):
            return self[name]
        else:
            return self.__getattribute__(name)

    def __setattr__(self, name, value):
        if self._attr_filter(name):
            self[name] = value
        else:
            super().__setattr__(name, value)

    def __delattr__(self, name):
        if self._attr_filter(name):
            del self[name]
        else:
            super().__delattr__(name)

    def keys(self) -> "LuaTableKeys":
        return LuaTableKeys(self)

    def values(self) -> "LuaTableValues":
        return LuaTableValues(self)

    def items(self) -> "LuaTableItems":
        return LuaTableItems(self)

    def __iter__(self):
        return iter(self.keys())


class LuaCallable(LuaObject):
    """
    Lua callable type wrapper. ("function" and "userdata")

    LuaCallable object is callable.
    """

    def __call__(self, *args, **kwargs):
        """
        Call the wrapped lua object.

        Lua functions do not support keyword arguments.
        Keyword arguments have special usage.
        """

        lib = self._runtime.lib
        set_metatable = kwargs.pop("set_metatable", True)
        with self._runtime.get_state(2) as L:
            oldtop = lib.lua_gettop(L)
            lib.lua_pushcfunction(L, self._runtime._db_traceback)
            errfunc = 1
            self._pushobj_nts()
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
                        self._runtime._reraise_exception_nts()
                self._runtime._clear_exception_nts()
                raise LuaErr.new(self._runtime, status, err_msg, self._runtime.encoding)
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
    """Lua nil type wrapper."""

    def __init__(self, runtime: 'LuaRuntime', *args) -> None:
        super().__init__(runtime, 0)

    def _ref_to_index(self, runtime: "LuaRuntime", index: int) -> None:
        pass

    def _ref_to_key(self, key) -> None:
        pass

    def __del__(self) -> None:
        pass

    def _pushobj_nts(self) -> None:
        runtime = self._runtime
        lib = runtime.lib
        with runtime.get_state(0, lock=False) as L:
            lib.lua_pushnil(L)

    def __eq__(self, other) -> bool:
        return isinstance(other, LuaNil)


class LuaNumber(LuaObject):
    """Lua number type wrapper."""

    def __int__(self):
        lib = self._runtime.lib
        ffi = self._runtime.ffi
        isnum = ffi.new("int*")
        with self._runtime.get_state(2) as L:
            self._pushobj_nts()
            value = lib.lua_tointegerx(L, -1, isnum)
        isnum = isnum[0]
        if isnum:
            return value
        else:
            raise TypeError("Not a integer.")

    def __float__(self):
        lib = self._runtime.lib
        ffi = self._runtime.ffi
        isnum = ffi.new("int*")
        with self._runtime.get_state(2) as L:
            self._pushobj_nts()
            value = lib.lua_tonumberx(L, -1, isnum)
        isnum = isnum[0]
        if isnum:
            return value
        else:
            raise TypeError("Not a number.")


class LuaString(LuaObject):
    """Lua string type wrapper."""

    def __bytes__(self):
        lib = self._runtime.lib
        ffi = self._runtime.ffi
        sz = ffi.new("size_t*")
        with self._runtime.get_state(2) as L:
            self._pushobj_nts()
            value = lib.lua_tolstring(L, -1, sz)
            sz = sz[0]
            if value == ffi.NULL:
                raise TypeError("Not a string.")
            else:
                return ffi.unpack(value, sz)


class LuaBoolean(LuaObject):
    """Lua boolean type wrapper."""


class LuaTable(LuaCollection):
    """Lua table type wrapper."""


class LuaFunction(LuaCallable):
    """Lua function type wrapper."""

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
    Lua thread type wrapper.

    LuaThread is Generator-like.
    ``bool(thread)`` returns True if the Lua coroutine is not dead otherwise returns False.
    """

    def send(self, *args, **kwargs):
        """
        Send arguments into Lua coroutine.
        Return next yielded value or raise StopIteration.
        """

        if self._isfirst:
            if args in ((), (None,)) and not kwargs:
                return next(self)
            else:
                raise TypeError(
                    "Can't send non-None value to a just-started generator."
                )
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
                    self._runtime._reraise_exception_nts()
            self._runtime._clear_exception_nts()
            raise LuaErr.new(self._runtime, None, rv[1], self._runtime.encoding)

    def __next__(self):
        """Return next yielded value or raise StopIteration."""
        with self._runtime.lock():
            a, k = self._first
            rv = self._send(*a, **k)
            self._first[0] = ()
            self._isfirst = False
            return rv

    def __init__(self, runtime: "LuaRuntime", index: int) -> None:
        lib = runtime.lib
        self._first = [(), {}]
        self._isfirst = True
        super().__init__(runtime, index)
        with runtime.get_state(2) as L:
            self._pushobj_nts()
            thread = lib.lua_tothread(L, -1)
            if lib.lua_status(thread) == lib.LUA_OK and lib.lua_gettop(thread) == 1:
                lib.lua_pushvalue(thread, 1)
                lib.lua_xmove(thread, L, 1)
                self._func = LuaObject.new(runtime, -1)
            else:
                self._func = None

    def __call__(self, *args, **kwargs) -> "LuaThread":
        """
        Behave like calling the coroutine factory.
        Return a new LuaThread from the factory function of this LuaThread.
        Arguments will be stored then used in first resume.
        """
        if self._func is None:
            raise RuntimeError("Factory function not found.")
        newthread = self._runtime._G.coroutine.create(self._func)
        newthread._first = [args, kwargs]
        return newthread

    def status(self) -> str:
        """Get the status of the Lua coroutine. Equivalent to call ``coroutine.status``."""
        return self._runtime._G.coroutine.status(self, autodecode=False).decode("ascii")

    def __bool__(self) -> bool:
        """Return whether the lua coroutine is not dead."""
        return self.status() != "dead"

    def throw(self, typ, val=None, tb=None):
        """Throw exceptions in LuaThread."""
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
    """Lua userdata type wrapper."""


class LuaVolatile(LuaObject):
    """Volatile ref to stack index."""

    def _ref_to_index(self, runtime: "LuaRuntime", index: int):
        lib = runtime.lib
        with runtime.get_state(0) as L:
            self._ref_to_key(lib.lua_absindex(L, index))

    def _pushobj_nts(self):
        lib = self._runtime.lib
        with self._runtime.get_state(0, lock=False) as L:
            lib.lua_pushvalue(L, self._ref)

    def settle(self) -> LuaObject:
        return LuaObject.new(self._runtime, self._ref)

    def __del__(self) -> None:
        pass


class LuaTableView:
    """Base class of MappingView classes for LuaCollection."""

    def __init__(self, obj: LuaCollection) -> None:
        self._obj = obj

    def __len__(self):
        return self._obj.__len__()

    def __iter__(self):
        raise NotImplementedError


class LuaTableKeys(LuaTableView, KeysView):
    """KeysView for LuaCollection."""

    def __iter__(self):
        return LuaKeyIter(self._obj)


class LuaTableValues(LuaTableView, ValuesView):
    """ValuesView for LuaCollection."""

    def __iter__(self):
        return LuaValueIter(self._obj)


class LuaTableItems(LuaTableView, ItemsView):
    """ItemsView for LuaCollection."""

    def __iter__(self):
        return LuaItemIter(self._obj)


class LuaIter(Iterator, metaclass=abc.ABCMeta):
    """
    Base class of Iterator classes for LuaCollection.
    Iteration use ``pairs`` function.
    """

    def __init__(self, obj: LuaCollection):
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

    @abc.abstractmethod
    def _filterkv(self, key, value):
        pass


class LuaKeyIter(LuaIter):
    """KeyIterator for LuaCollection."""

    def _filterkv(self, key, value):
        return key


class LuaValueIter(LuaIter):
    """ValuesIterator for LuaCollection."""

    def _filterkv(self, key, value):
        return value


class LuaItemIter(LuaIter):
    """ItemsIterator for LuaCollection."""

    def _filterkv(self, key, value):
        return key, value


class Puller(Registry):
    """
    Puller. A puller is callable to pull Lua object on the Lua stack to Python.
    Pull functions can be registered for specific Lua types.
    """

    def __init__(self):
        super().__init__()
        self._default_puller = None

    def __call__(
        self, runtime: "LuaRuntime", index: int, *, keep: bool = False, **kwargs
    ):
        """Pull the Lua object at ``index`` to Python."""
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
        raise TypeError(f"Cannot find puller for lua type '{tp}'.")

    def register_default(self, func):
        """Register the default pull function."""
        self._default_puller = func
        return func


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
    with runtime.get_state(2) as L:
        obj._pushobj_nts()
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
    """Base class for proxies."""

    def __init__(self, obj: LuaCollection) -> None:
        """Init a proxy for ``obj``."""
        object.__setattr__(self, "_obj", obj)


def unproxy(proxy: Proxy) -> LuaCollection:
    """Unwrap a proxy."""
    return object.__getattribute__(proxy, "_obj")


class ListProxy(Proxy, MutableSequence):
    """List-like proxy."""

    @staticmethod
    def _raise_type(obj) -> NoReturn:
        raise TypeError(
            f"List indices must be integers or slices, not '{type(obj).__name__}'."
        )

    def _process_index(self, index: int, check_index: bool = True) -> int:
        if index >= len(self):
            if check_index:
                raise IndexError("List index out of range.")
            else:
                index = len(self)
        if index < 0:
            index += len(self)
        if index < 0:
            if check_index:
                raise IndexError("List index out of range.")
            else:
                index = 0
        return index + 1

    def __getitem__(self, item: Union[int, slice]) -> Any:
        if isinstance(item, int):
            return self._obj[self._process_index(item)]
        elif isinstance(item, slice):
            obj: "LuaCollection" = self._obj
            runtime: "LuaRuntime" = obj._runtime
            lib = runtime.lib
            with runtime.get_state(2) as L:
                obj._pushobj_nts()
                rg = range(*item.indices(len(self)))
                l = len(rg)
                lib.lua_createtable(L, l, 0)
                j = 1
                for k in rg:
                    i = k + 1
                    lib.lua_geti(L, -2, i)
                    lib.lua_rawseti(L, -2, j)
                    j += 1
                return self.__class__(LuaTable(runtime, -1))
        else:
            self._raise_type(item)

    def __setitem__(self, key: Union[int, slice], value: Any) -> None:
        if isinstance(key, int):
            self._obj[self._process_index(key)] = value
        elif isinstance(key, slice):
            rg = range(*key.indices(len(self)))
            if len(rg) != len(value):
                raise ValueError(
                    f"Attempt to assign sequence of size {len(value)} to extended slice of size {len(rg)}"
                )
            for i, v in zip(rg, value):
                self[i] = v
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
    """Object-like proxy."""

    def __getattribute__(self, item):
        return unproxy(self)[item]

    def __setattr__(self, key, value):
        unproxy(self)[key] = value

    def __delattr__(self, item):
        del unproxy(self)[item]


class StrictObjectProxy(ObjectProxy):
    """Strict object-like proxy. Treat "nil" value as no such attribute."""

    def __getattribute__(self, item):
        rv = unproxy(self).__getitem__(item, keep=True)
        if isinstance(rv, LuaNil):
            raise AttributeError(
                "'{!r}' has no attribute '{}' or it's nil.".format(unproxy(self), item)
            )
        else:
            return rv.pull()


class DictProxy(Proxy, MutableMapping):
    """Dict-like proxy. Treat "nil" value as no such item."""

    def __getitem__(self, item):
        rv = self._obj.__getitem__(item, keep=True)
        if isinstance(rv, LuaNil):
            raise KeyError(item)
        else:
            return rv.pull()

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
            raise ValueError(
                "wrong instance (use 'foo:bar()' to call method, not 'foo.bar()')"
            )
        return self.obj(*args, **kwargs)


class DeferredLuaCodeProtocol(Py2LuaProtocol):
    def __init__(self, code: Union[str, bytes]) -> None:
        super().__init__()
        self._code = code

    def push_protocol(self, pi: "PushInfo") -> None:
        pi.pusher.internal_push(pi.with_new_obj(pi.runtime.eval(self._code)))


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


@dataclass(frozen=True)
class PushInfo:
    runtime: "LuaRuntime"
    L: Any
    obj: Any
    kwargs: Dict[Any, Any]
    pusher: "Pusher"

    def with_new_obj(self, new_obj: Any) -> "PushInfo":
        return dataclasses.replace(self, obj=new_obj)


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
        with runtime.get_state(0) as L:
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
    with pi.runtime.get_state(0) as fr:
        pi.obj._pushobj_nts()
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
        bk = runtime.lua_state
        runtime.lua_state = L
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
        runtime._store_exception_nts()
        return -1
    finally:
        try:
            runtime.lua_state = bk
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
        with runtime.get_state(2) as L:
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


def std_pylib_factory(runtime: "LuaRuntime") -> Optional[Mapping[bytes, Any]]:
    def keep_return(func):
        @functools.wraps(func)
        def _(*args, **kwargs):
            return as_is(func(*args, **kwargs))

        return _

    pack_table = runtime.eval(
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

    return {
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
        b"to_luaobject": pack_table(lambda o: as_is(o.__getitem__(1, keep=True))),
        b"to_bytes": pack_table(lambda o: as_is(o.__getitem__(1, autodecode=False))),
        b"to_str": pack_table(
            lambda o, encoding=None: as_is(
                o.__getitem__(1, autodecode=False).decode(
                    runtime.encoding
                    if encoding is None
                    else encoding
                    if isinstance(encoding, str)
                    else encoding.decode(runtime.encoding)
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
        b"runtime": runtime,
    }


PyLibFactory = Callable[["LuaRuntime"], Optional[Mapping[bytes, Any]]]


class LuaRuntime(NotCopyable):
    """Lua runtime."""

    def __init__(
        self,
        encoding: str = sys.getdefaultencoding(),
        source_encoding: Optional[str] = None,
        autodecode: Optional[bool] = None,
        *,
        lualib: Optional[LuaLib] = None,
        pusher: Optional[Pusher] = None,
        puller: Optional[Puller] = None,
        metatable: Optional[Metatable] = None,
        pylib_factory: Optional[PyLibFactory] = None,
        lua_state=None,
        lua_stdlibs: bool = True,
        lock=None,
    ) -> None:
        """
        :param encoding: The encoding to encode and decode Lua string.
        :param source_encoding: The encoding to encoding Lua code.
        :param autodecode: Whether automatically decode strings returned from Lua functions.
        :param lualib: The Lua lib.
        :param pusher: The pusher to push objects to Lua.
        :param puller: The pulled to pull objects from Lua.
        :param metatable: The metatable for Python objects.
        :param pylib_factory: The factory of "python" global variable in Lua.
        :param lua_state: The Lua state.
            If specified, the new runtime will use this existed Lua state rather than init a new one.
        :param lua_stdlibs: Whether to open Lua stdlibs such as "os", "io".
        :param lock: The reentrant lock to ensure thread-safe.
        """
        super().__init__()

        # init lock
        self._lock = lock or RLock()

        # init pusher & puller
        self._pusher = pusher or std_pusher
        self._puller = puller or std_puller

        # init variables
        self._exception: Optional[Tuple[Type, Exception, types.TracebackType]] = None
        self.refs: MutableSet[Any] = set()
        self._lock_context = type(
            "LockContext",
            (object,),
            {"__enter__": lambda _: None, "__exit__": lambda _, *args: self.unlock()},
        )()

        # init encoding
        self.encoding = encoding
        self.source_encoding = source_encoding or encoding or sys.getdefaultencoding()
        self.autodecode = encoding is not None if autodecode is None else autodecode

        # init ffi & lib
        self.lualib = lualib or get_default_lualib()
        self.luamod = self.lualib.import_mod()
        self.ffi = self.luamod.ffi
        self.lib = self.luamod.lib

        # init state
        if lua_state is None:
            self.lua_state = self.lib.luaL_newstate()
            if self.lua_state == self.ffi.NULL:
                raise RuntimeError('"luaL_newstate" returns NULL')
            if lua_stdlibs:
                self.lib.luaL_openlibs(self.lua_state)
        else:
            self.lua_state = self.ffi.cast("lua_State*", lua_state)

        # init variables
        self.nil = LuaNil(self)
        self._G = self.globals()
        self._db_traceback = self.lib._get_traceback_function()

        # init metatable & pylib
        (metatable or std_metatable).init_runtime(self)
        pylib = (pylib_factory or std_pylib_factory)(self)
        if pylib:
            self._G[b"python"] = self._G[b"package"][b"loaded"][
                b"python"
            ] = self.table_from(pylib)

    def compile(self, code: Union[str, bytes], name: bytes = b"=python") -> LuaFunction:
        """Compile Lua code."""
        if isinstance(code, str):
            code = code.encode(self.source_encoding)
        with self.get_state(2) as L:
            status = self.lib.luaL_loadbuffer(L, code, len(code), name)
            obj = self.pull(-1)
            if status != self.lib.LUA_OK:
                raise LuaErr.new(self, status, obj, self.encoding)
            else:
                return obj

    def compile_path(self, path: Union[str, bytes, os.PathLike]) -> LuaFunction:
        """Compile Lua source file."""
        pathname = ensure_bytespath(path)
        with self.get_state(2) as L:
            status = self.lib.luaL_loadfile(L, pathname)
            obj = self.pull(-1)
            if status != self.lib.LUA_OK:
                raise LuaErr.new(self, status, obj, self.encoding)
            else:
                return obj

    def execute(self, code: Union[str, bytes], *args) -> Any:
        """Execute lua source code."""
        return self.compile(code)(*args)

    def eval(self, code: Union[str, bytes], *args) -> Any:
        """Eval lua expression."""
        if isinstance(code, bytes):
            code = b"return " + code
        else:
            code = "return " + code
        return self.execute(code, *args)

    def globals(self) -> LuaTable:
        """Return the global table in Lua."""
        with self.get_state(2) as L:
            self.lib.lua_pushglobaltable(L)
            return self.pull(-1)

    def table(self, *args, **kwargs) -> LuaTable:
        """
        Create and return a Lua table.

        :param args: Items in args are set to the Lua table with index *starting from 1*.
        :param kwargs: Entries in kwargs are set to the Lua table.
        """
        return self.table_from(args, kwargs)

    def table_from(self, *args: Union[Iterable, Mapping, ItemsView]) -> LuaTable:
        """
        Create and return a Lua table from Python collections.

        :param args: Collection objects.
            Mapping and ItemsView objects are joined and entries are set to the Lua table.
            Other Iterable objects are chained and set to the Lua table with index *starting from 1*.
        :type args: Tuple[Union[Iterable, Mapping, ItemsView], ...]
        """
        lib = self.lib
        narr = nres = 0
        for obj in args:
            if isinstance(obj, (Mapping, ItemsView)):
                nres += operator.length_hint(obj)
            else:
                narr += operator.length_hint(obj)
        with self.get_state(2) as L:
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

    def require(self, modname: Union[str, bytes]) -> LuaTable:
        """Load and return a Lua module."""
        return self._G.require(modname)

    def close(self) -> None:
        """Close this LuaRuntime."""
        lib = self.lib
        with self.get_state(0) as L:
            if L:
                lib.lua_close(L)
                self.lua_state = None

    def __del__(self) -> None:
        self.close()

    def __enter__(self) -> "LuaRuntime":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def push(self, obj: Any, **kwargs) -> None:
        return self._pusher(self, obj, **kwargs)

    def pull(self, index: int, **kwargs) -> Any:
        return self._puller(self, index, **kwargs)

    def lock(self):
        """Lock the runtime. Return a context for unlocking."""
        self._lock.acquire()
        return self._lock_context

    def unlock(self) -> None:
        """Unlock the runtime."""
        self._lock.release()

    @contextmanager
    def get_state(self, stack_balance: int = 0, lock: bool = True):
        """
        Get the Lua state, for ``with`` statement.

        :param stack_balance: Acceptable values:
                * ``0``: Do nothing.
                * ``1``: Assert the stack balance.
                * ``2``: Ensure the stack balance.

            Stack balance means keeping the stack top not changed.
        :param lock: Whether to lock the runtime.
        """

        if lock:
            self._lock.acquire()
        try:
            L = self.lua_state
            if L is None:
                stack_balance = 0
            lib = self.lib
            oldtop = None if stack_balance == 0 else lib.lua_gettop(L)
            try:
                yield self.lua_state
            finally:
                if stack_balance == 0:
                    pass
                elif stack_balance == 1:
                    assert lib.lua_gettop(L) == oldtop, "Stack unbalance."
                elif stack_balance == 2:
                    assert lib.lua_gettop(L) >= oldtop, "Stack unbalance."
                    lib.lua_settop(L, oldtop)
        finally:
            if lock:
                self.unlock()

    def _store_exception_nts(self) -> None:
        self._exception = sys.exc_info()

    def _reraise_exception_nts(self) -> None:
        try:
            if self._exception:
                reraise(*self._exception)
        finally:
            self._clear_exception_nts()

    def _clear_exception_nts(self) -> None:
        self._exception = None
