"module contains python wrapper for lua objects and utils"


__all__ = (
    'getmetafield',
    'hasmetafield',
    'LuaLimitedObject',
    'LuaObject',
    'LuaCollection',
    'LuaCallable',
    'LuaNil',
    'LuaNumber',
    'LuaString',
    'LuaBoolean',
    'LuaTable',
    'LuaFunction',
    'LuaThread',
    'LuaUserdata',
    'LuaKIter',
    'Puller',
    'std_puller',
    'Proxy',
    'unproxy',
    'ListProxy',
    'ObjectProxy'
)


import sys
import itertools
from collections.abc import *
from .util import *
from .exception import *
from .protocol import *


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
    This class does not contains "lua method".
    """
    def _ref_to_key(self, key):
        self._ref = key

    def _ref_to_index(self, runtime, index):
        lib = runtime.lib
        ffi = runtime.ffi
        with lock_get_state(runtime) as L:
            with assert_stack_balance(runtime):
                index = lib.lua_absindex(L, index)
                key = ffi.new('char*')
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
        is garbadge collected.

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


def not_impl(exc_type, exc_value, exc_traceback):
    """check whether lua error is happened in first stack frame.
    if it is, returns ``NotImplemented``, otherwise reraise the lua error.

    This function is a helper for operator overloading."""
    if issubclass(exc_type, LuaErrRun):
        err_msg = exc_value.err_msg
        if isinstance(err_msg, bytes):
            lns = err_msg.split(b'\n')
        else:
            lns = err_msg.split('\n')
        if len(lns) == 3:
            return NotImplemented
    reraise(exc_type, exc_value, exc_traceback)


_method_template = '''\
def {name}({outer_args}, **kwargs):
    runtime = self._runtime
    lib = runtime.lib
    with lock_get_state(runtime) as L:
        with ensure_stack_balance(runtime):
            lib.lua_pushcfunction(L, lib._get_{client}_client())
            try:
                return LuaCallable.__call__(LuaVolatile(runtime, -1), lib.{op}, {args}, set_metatable=False, **kwargs)
            except LuaErrRun:
                return not_impl(*sys.exc_info())
'''

class LuaObject(LuaLimitedObject):
    """
    Base class for other lua object wrapper classes.

    A lua object wrapper wraps a lua object for python.
    Commonly it's used to wrap lua tables, functions etc
    which cannot be simply translate to a plain python
    object. The wrapped lua object won't be garbadge
    collected until the wrapper is garbadge collected.

    Operations like ``len()`` and "add" on lua object
    wrapper will be passed to lua and done in lua with
    the wrapped lua object. This class contains some "lua
    methods" which will call into lua to support operations.
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
                return ffi.string(lib.lua_typename(L, lib.lua_type(L, -1))).decode('ascii')

    for name, op in (
        ('add', 'LUA_OPADD'),
        ('sub', 'LUA_OPSUB'),
        ('mul', 'LUA_OPMUL'),
        ('truediv', 'LUA_OPDIV'),
        ('floordiv', 'LUA_OPIDIV'),
        ('mod', 'LUA_OPMOD'),
        ('pow', 'LUA_OPPOW'),
        ('and', 'LUA_OPBAND'),
        ('or', 'LUA_OPBOR'),
        ('xor', 'LUA_OPBXOR'),
        ('lshift', 'LUA_OPSHL'),
        ('rshift', 'LUA_OPSHR'),
    ):
        exec(_method_template.format(name='__{}__'.format(name), client='arith', op=op, args='self, value', outer_args='self, value'))
        exec(_method_template.format(name='__r{}__'.format(name), client='arith', op=op, args='value, self', outer_args='self, value'))

    for name, rname, op in (
        ('eq', None, 'LUA_OPEQ'),
        ('lt', 'gt', 'LUA_OPLT'),
        ('le', 'ge', 'LUA_OPLE'),
    ):
        exec(_method_template.format(name='__{}__'.format(name), client='compare', op=op, args='self, value', outer_args='self, value'))
        if rname:
            exec(_method_template.format(name='__{}__'.format(rname), client='compare', op=op, args='value, self', outer_args='self, value'))

    for name, op in (
        ('invert', 'LUA_OPBNOT'),
        ('neg', 'LUA_OPUNM'),
    ):
        exec(_method_template.format(name='__{}__'.format(name), client='arith', op=op, args='self', outer_args='self'))

    del name; del rname; del op

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
            raise ValueError('encoding not specified')


_index_template = '''\
def {name}({args}, **kwargs):
    runtime = self._runtime
    lib = runtime.lib
    with lock_get_state(runtime) as L:
        with ensure_stack_balance(runtime):
            lib.lua_pushcfunction(L, lib._get_index_client())
            try:
                return LuaCallable.__call__(LuaVolatile(runtime, -1), {op}, {args}, **kwargs)
            except LuaErrRun:
                return not_impl(*sys.exc_info())
'''

class LuaCollection(LuaObject, MutableMapping):
    """
    Lua collection type wrapper. ("table" and "userdata")

    LuaCollection is a MutableMapping type in python.
    That means the instance can be treat as a dict-like
    object and support item getting/setting. The item
    getting/setting will be passed to lua and modify the
    wrapped lua object.

    Getting/setting through attributes is also supported.
    The same name python attributes will override that in
    lua.

    The indexing key name will be encoded with ``encoding``
    specified in lua runtime if it's a unicode.

    Indexing example:

    ..
        ## doctest helper
        >>> from ffilupa import *
        >>> runtime = LuaRuntime()

    ::

        >>> table = runtime.eval('{5, 6, 7, awd="dwa", ["__init__"]="ccc"}')
        >>> table[2]            # indexing with integer index, starting from 1
        6
        >>> table[2] = 9        # setting with integer index
        >>> table[2]
        9
        >>> table['awd']        # indexing with key
        'dwa'
        >>> table.awd           # indexing with attr
        'dwa'
        >>> table['__init__']   # item will not be overridden
        'ccc'
        >>> table.__init__      # the same name attr will be overridden # doctest: +ELLIPSIS
        <bound method ...>
        >>> table[b'awd']       # indexing with binary key
        'dwa'
        >>> table['awd'] = 'ddd'# setting with key
        >>> table.awd
        'ddd'
        >>> table.awd = 'eee'   # setting with attr
        >>> table['awd']
        'eee'

    Iterating example:

    ::

        >>> table.keys()        # will return a KeysView    # doctest: +ELLIPSIS
        <ffilupa.py_from_lua.LuaKView object at ...>
        >>> table.values()      # will return a ValuesView  # doctest: +ELLIPSIS
        <ffilupa.py_from_lua.LuaVView object at ...>
        >>> table.items()       # will return a ItemsView   # doctest: +ELLIPSIS
        <ffilupa.py_from_lua.LuaKVView object at ...>

        >>> itemview = table.items()
        >>> itemiter = iter(itemview)
        >>> itemiter            # itemiter is a ItemsIter   # doctest: +ELLIPSIS
        <ffilupa.py_from_lua.LuaKVIter object at ...>

        >>> sorted(itemview, key=str)  # get sorted items
        [('__init__', 'ccc'), ('awd', 'eee'), (1, 5), (2, 9), (3, 7)]

    """
    exec(_index_template.format(name='array_len', op=0, args='self'))
    exec(_index_template.format(name='__getitem__', op=1, args='self, name'))
    exec(_index_template.format(name='__setitem__', op=2, args='self, name, value'))

    def __delitem__(self, name):
        if isinstance(name, int):
            self._runtime._G.table.remove(self, name)
        else:
            self[name] = self._runtime.nil

    def attr_filter(self, name):
        """
        Attr filter. Accepts a attr name unicode and returns a
        boolean. Used in attr getting/setting. If returns True,
        the attr getting/setting will be passed to lua, otherwise
        the attr getting/setting will not be passed to lua and
        operation will be done on ``self`` the python object.

        You can change the behavior to specify which attr to filtered
        or not in this method.
        """
        return self.__dict__.get('edit_mode', True) is False and \
               name not in self.__dict__

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

    def __iter__(self):
        return LuaKIter(self)

    def __contains__(self, item):
        return item in iter(self)

    def __len__(self):
        i = 0
        for i, _ in zip(itertools.count(1), self):
            pass
        return i


class LuaCallable(LuaObject):
    """
    Lua callable type wrapper. ("function" and "userdata")

    LuaCallable is a callable type in python.
    That means the instance is callable. The
    call on the instance will be translated to
    the call to the wrapped lua object.
    """
    def __call__(self, *args, **kwargs):
        """
        Call the wrapped lua object.

        Lua functions do not support keyword arguments.
        ``*args`` will be "pushed" to lua and as the
        arguments to call the lua object.

        *All keyword arguments are keyword-only arguments*
        and will be processed in python, not passed to lua.
        Extra keyword arguments:

        * ``keep``: a boolean to specify whether not to "pull" down
          return value in simple lua type to native python type. If
          it's False, "nil", "number", "boolean", "string" and wrapped
          python object will be convert to native python type,
          otherwise the return value will be always wrapped.
          Default is False.

        * ``autodecode``: a boolean to specify whether decode
          string type return value to unicode. If it's True and
          ``keep`` is not True, the string returned from lua will
          be decoded with ``encoding`` in lua runtime, otherwise
          do not decode. Default is the same as specified in lua
          runtime.
        """
        lib = self._runtime.lib
        set_metatable = kwargs.pop('set_metatable', True)
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                oldtop = lib.lua_gettop(L)
                try:
                    self._runtime._pushvar(b'debug', b'traceback')
                    if lib.lua_isfunction(L, -1) or hasmetafield(self._runtime, -1, b'__call'):
                        errfunc = 1
                    else:
                        lib.lua_pop(L, 1)
                        errfunc = 0
                except TypeError:
                    errfunc = 0
                self._pushobj()
                for obj in args:
                    self._runtime.push(obj, set_metatable=set_metatable)
                status = lib.lua_pcall(L, len(args), lib.LUA_MULTRET, (-len(args) - 2) * errfunc)
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
                    raise LuaErr.new(self._runtime, status, err_msg, self._runtime.encoding)
                else:
                    rv = [self._runtime.pull(i, **kwargs) for i in range(oldtop + 1 + errfunc, lib.lua_gettop(L) + 1)]
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
        isnum = ffi.new('int*')
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                self._pushobj()
                value = lib.lua_tointegerx(L, -1, isnum)
        isnum = isnum[0]
        if isnum:
            return value
        else:
            raise TypeError('not a integer')

    def __float__(self):
        lib = self._runtime.lib
        ffi = self._runtime.ffi
        isnum = ffi.new('int*')
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                self._pushobj()
                value = lib.lua_tonumberx(L, -1, isnum)
        isnum = isnum[0]
        if isnum:
            return value
        else:
            raise TypeError('not a number')


class LuaString(LuaObject):
    """
    Lua string type wrapper.
    """
    def __bytes__(self):
        lib = self._runtime.lib
        ffi = self._runtime.ffi
        sz = ffi.new('size_t*')
        with lock_get_state(self._runtime) as L:
            with ensure_stack_balance(self._runtime):
                self._pushobj()
                value = lib.lua_tolstring(L, -1, sz)
                sz = sz[0]
                if value == ffi.NULL:
                    raise TypeError('not a string')
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
    def coroutine(self, *args, **kwargs):
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

    A LuaThread instance behaviors like native python
    coroutine but does not support ``throw()`` and
    ``close()``. In fact, lua coroutine has some
    difference with python coroutine. The lua coroutine
    is not created by a factory and not need to prime.
    The arguments sent to lua coroutine in first resume
    are treat as the arguments of the coroutine function,
    and the second resume is at first yield place. But
    first resume of python coroutine is to prime it, the
    arguments of the coroutine function is given when it's
    generated in factory, and the second resume is at first
    yield place.

    To let lua coroutine more like python coroutine,
    LuaThread behavior like both factory and coroutine.
    If you call it before the coroutine is started, the
    arguments will be stored and a copy of this coroutine
    will be returned, which will pass the stored arguments to
    lua coroutine and do not need extra arguments at first
    resume just like priming of python coroutine. After the
    "priming", you can use ``.send()`` and ``next()`` just like
    using them on python coroutine.

    The bool value of LuaThread is special and not the same as
    other lua object wrappers. ``bool(thread)`` will returns True
    if the lua coroutine is not dead otherwise returns False.

    A LuaThread instance can be also created from a lua function.
    See ``LuaFunction.coroutine()``.
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
        return self._send(*args, **kwargs)

    def _send(self, *args, **kwargs):
        with self._runtime.lock():
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

    def __call__(self, *args, **kwargs):
        """
        Behaviors like calling a coroutine factory.
        Returns a copy of this lua coroutine stored
        arguments for first resume.
        """
        if self._func is None:
            raise RuntimeError('original function not found')
        newthread = self._runtime._G.coroutine.create(self._func)
        newthread._first = [args, kwargs]
        return newthread

    def status(self):
        """
        Returns the status of lua coroutine.
        The return value is the same as the
        return value of ``coroutine.status``,
        decoded with ascii.
        """
        return self._runtime._G.coroutine.status(self, autodecode=False).decode('ascii')

    def __bool__(self):
        """
        Returns whether the lua coroutine is not dead.
        """
        return self.status() != 'dead'

    def throw(self, typ, val=None, tb=None):
        if val is None:
            val = typ()
        if tb is not None:
            val = val.with_traceback(tb)
        def raise_exc(*args):
            raise val
        with self._runtime.lock():
            self._runtime._G.debug.sethook(self, as_function(raise_exc), 'c')
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


from .metatable import PYOBJ_SIG
from .protocol import Py2LuaProtocol

class Puller(Registry):
    def __init__(self):
        super().__init__()
        self._default_puller = None

    def __call__(self, runtime, index, *, keep=False, **kwargs):
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
        if self._default_puller is not None: return self._default_puller
        raise TypeError('cannot find puller for lua type \'' + str(tp) + '\'')

    def register_default(self, func):
        self._default_puller = func

std_puller = Puller()

@std_puller.register('LUA_TNIL')
def _(runtime, obj, **kwargs):
    return None

@std_puller.register('LUA_TNUMBER')
def _(runtime, obj, **kwargs):
    try:
        return LuaNumber.__int__(obj)
    except TypeError:
        return LuaNumber.__float__(obj)

@std_puller.register('LUA_TBOOLEAN')
def _(runtime, obj, **kwargs):
    return LuaBoolean.__bool__(obj)

@std_puller.register('LUA_TSTRING')
def _(runtime, obj, *, autodecode=None, autounpack=True, keep_handle=False):
    if (runtime.autodecode if autodecode is None else autodecode):
        return LuaString.__str__(obj)
    else:
        return LuaString.__bytes__(obj)

@std_puller.register_default
def _(runtime, obj, *, autodecode=None, autounpack=True, keep_handle=False):
    lib = runtime.lib
    ffi = runtime.ffi
    with lock_get_state(runtime) as L:
        with ensure_stack_balance(runtime):
            obj._pushobj()
            if lib.lua_getmetatable(L, -1):
                lib.luaL_getmetatable(L, PYOBJ_SIG)
                if lib.lua_rawequal(L, -2, -1):
                    handle = ffi.cast('void**', lib.lua_topointer(L, -3))[0]
                    if keep_handle:
                        return handle
                    obj = ffi.from_handle(handle)
                    del handle
                    if isinstance(obj, Py2LuaProtocol) and autounpack:
                        obj = obj.obj
                    return obj
    return obj.settle()


class Proxy:
    def __init__(self, obj: LuaCollection):
        object.__setattr__(self, '_obj', obj)

def unproxy(proxy: Proxy):
    return object.__getattribute__(proxy, '_obj')

class ListProxy(Proxy, MutableSequence):
    @staticmethod
    def _raise_type(obj):
        raise TypeError('list indices must be integers or slices, not ' + type(obj).__name__)

    def _process_index(self, index, check_index=True):
        if index >= len(self):
            if check_index:
                raise IndexError('list index out of range')
            else:
                index = len(self)
        if index < 0:
            index += len(self)
        if index < 0:
            if check_index:
                raise IndexError('list index out of range')
            else:
                index = 0
        return index + 1

    def __getitem__(self, item):
        if isinstance(item, int):
            return self._obj[self._process_index(item)]
        elif isinstance(item, slice):
            return self.__class__(self._obj._runtime.table_from(self[i] for i in range(*item.indices(len(self)))))
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
        return self._obj.array_len()

    def insert(self, index, value):
        self._obj._runtime._G.table.insert(self._obj, self._process_index(index, False), value)

class ObjectProxy(Proxy):
    def __getattribute__(self, item):
        return unproxy(self)[item]

    def __setattr__(self, key, value):
        unproxy(self)[key] = value

    def __delattr__(self, item):
        del unproxy(self)[item]
