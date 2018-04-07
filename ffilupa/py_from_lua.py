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
    'LuaView',
    'LuaKView',
    'LuaVView',
    'LuaKVView',
    'LuaIter',
    'LuaKIter',
    'LuaVIter',
    'LuaKVIter',
    'pull',
)


from functools import partial
from collections import *
from .util import *
from .exception import *
from .compile import *


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
                return pull(runtime, -1)

def hasmetafield(runtime, index, key):
    """
    Returns whether the lua object in ``runtime`` at ``index`` has such metafield ``key``.
    The return value is the same as ``getmetafield(runtime, index, key) is not None``.
    """
    return getmetafield(runtime, index, key) is not None


class LuaLimitedObject(CompileHub, NotCopyable):
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
        super().__init__(runtime)
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
                return pull(self._runtime, -1, **kwargs)


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


_binary_code = """
    function(self, value)
        return self {} value
    end
"""
_rbinary_code = """
    function(self, value)
        return value {} self
    end
"""
_unary_code = """
    function(self)
        return {}self
    end
"""


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

    @compile_lua_method("""
        function(self)
            return type(self)
        end
    """, return_hook=lambda name: name.decode('ascii') if isinstance(name, bytes) else name)
    def typename(self):
        """
        Returns the typename of the wrapped lua object.
        The return value is the same as the return value
        of lua function ``type``, decoded with ascii.
        """

    @compile_lua_method(_binary_code.format('+'), except_hook=not_impl)
    def __add__(self, value): pass
    @compile_lua_method(_binary_code.format('-'), except_hook=not_impl)
    def __sub__(self, value): pass
    @compile_lua_method(_binary_code.format('*'), except_hook=not_impl)
    def __mul__(self, value): pass
    @compile_lua_method(_binary_code.format('/'), except_hook=not_impl)
    def __truediv__(self, value): pass
    @compile_lua_method(_binary_code.format('//'), except_hook=not_impl)
    def __floordiv__(self, value): pass
    @compile_lua_method(_binary_code.format('%'), except_hook=not_impl)
    def __mod__(self, value): pass
    @compile_lua_method(_binary_code.format('^'), except_hook=not_impl)
    def __pow__(self, value): pass
    @compile_lua_method(_binary_code.format('&'), except_hook=not_impl)
    def __and__(self, value): pass
    @compile_lua_method(_binary_code.format('|'), except_hook=not_impl)
    def __or__(self, value): pass
    @compile_lua_method(_binary_code.format('~'), except_hook=not_impl)
    def __xor__(self, value): pass
    @compile_lua_method(_binary_code.format('<<'), except_hook=not_impl)
    def __lshift__(self, value): pass
    @compile_lua_method(_binary_code.format('>>'), except_hook=not_impl)
    def __rshift__(self, value): pass
    @compile_lua_method(_binary_code.format('=='), except_hook=not_impl)
    def __eq__(self, value): pass
    @compile_lua_method(_binary_code.format('<'), except_hook=not_impl)
    def __lt__(self, value): pass
    @compile_lua_method(_binary_code.format('<='), except_hook=not_impl)
    def __le__(self, value): pass
    @compile_lua_method(_binary_code.format('>'), except_hook=not_impl)
    def __gt__(self, value): pass
    @compile_lua_method(_binary_code.format('>='), except_hook=not_impl)
    def __ge__(self, value): pass
    @compile_lua_method(_binary_code.format('~='), except_hook=not_impl)
    def __ne__(self, value): pass

    @compile_lua_method(_rbinary_code.format('+'), except_hook=not_impl)
    def __radd__(self, value): pass
    @compile_lua_method(_rbinary_code.format('-'), except_hook=not_impl)
    def __rsub__(self, value): pass
    @compile_lua_method(_rbinary_code.format('*'), except_hook=not_impl)
    def __rmul__(self, value): pass
    @compile_lua_method(_rbinary_code.format('/'), except_hook=not_impl)
    def __rtruediv__(self, value): pass
    @compile_lua_method(_rbinary_code.format('//'), except_hook=not_impl)
    def __rfloordiv__(self, value): pass
    @compile_lua_method(_rbinary_code.format('%'), except_hook=not_impl)
    def __rmod__(self, value): pass
    @compile_lua_method(_rbinary_code.format('^'), except_hook=not_impl)
    def __rpow__(self, value): pass
    @compile_lua_method(_rbinary_code.format('&'), except_hook=not_impl)
    def __rand__(self, value): pass
    @compile_lua_method(_rbinary_code.format('|'), except_hook=not_impl)
    def __ror__(self, value): pass
    @compile_lua_method(_rbinary_code.format('~'), except_hook=not_impl)
    def __rxor__(self, value): pass
    @compile_lua_method(_rbinary_code.format('<<'), except_hook=not_impl)
    def __rlshift__(self, value): pass
    @compile_lua_method(_rbinary_code.format('>>'), except_hook=not_impl)
    def __rrshift__(self, value): pass

    @compile_lua_method(_unary_code.format('~'), except_hook=not_impl)
    def __invert__(self): pass
    @compile_lua_method(_unary_code.format('-'), except_hook=not_impl)
    def __neg__(self): pass

    def __init__(self, runtime, index):
        super().__init__(runtime, index)
        self.edit_mode = False

    @compile_lua_method('tostring')
    def _tostring(self, autodecode=False): pass

    def __bytes__(self):
        return self._tostring(autodecode=False)

    def __str__(self):
        if self._runtime.encoding is not None:
            return bytes(self).decode(self._runtime.encoding)
        else:
            raise ValueError('encoding not specified')


class LuaCollection(LuaObject):
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
    @compile_lua_method(_unary_code.format('#'))
    def __len__(self): pass

    @compile_lua_method("""
        function(self, name)
            return self[name]
        end
    """)
    def __getitem__(self, name, keep=False): pass

    @compile_lua_method("""
        function(self, name, value)
            self[name] = value
        end
    """)
    def __setitem__(self, name, value): pass

    @compile_lua_method("""
        function(self, name)
            if type(name) == 'number' then
                table.remove(self, name)
            else
                self[name] = nil
            end
        end
    """)
    def __delitem__(self, name): pass

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

    @pending_deprecate('ambiguous iter. use keys()/values()/items() instead')
    def __iter__(self):
        return iter(self.keys())

MutableMapping.register(LuaCollection)


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
        from .py_to_lua import push
        lib = self._runtime.lib
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
                    push(self._runtime, obj)
                status = lib.lua_pcall(L, len(args), lib.LUA_MULTRET, (-len(args) - 2) * errfunc)
                if status != lib.LUA_OK:
                    err_msg = pull(self._runtime, -1)
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
                    rv = [pull(self._runtime, i, **kwargs) for i in range(oldtop + 1 + errfunc, lib.lua_gettop(L) + 1)]
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


class LuaThread(LuaObject):
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
        a, k = self._first
        rv = self.send(*a, **k)
        self._first[0] = ()
        return rv

    def __init__(self, runtime, index):
        lib = runtime.lib
        self._first = [(), {}]
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

    def __iter__(self):
        return self

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


class LuaIter:
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

    def __iter__(self):
        return self

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


def pull(runtime, index, *, keep=False, autodecode=None, autounpack=True):
    """
    "Pull" down lua object in ``runtime`` at position ``index``
    to python.

    * ``keep``: a boolean to specify whether not to "pull" down
      lua object in simple lua type to native python type. If
      it's False, "nil", "number", "boolean", "string" and wrapped
      python object will be convert to native python type,
      otherwise the lua object will be always wrapped.
      Default is False.

    * ``autodecode``: a boolean to specify whether decode
      lua string to unicode. If it's True and ``keep`` is
      not True, the lua string will be decoded with
      ``encoding`` in lua runtime, otherwise do not decode.
      Default is the same as specified in lua runtime.
    """
    from .metatable import PYOBJ_SIG
    from .protocol import Py2LuaProtocol
    lib = runtime.lib
    ffi = runtime.ffi
    obj = LuaVolatile(runtime, index)
    if keep:
        return obj.settle()
    tp = obj._type()
    if tp == lib.LUA_TNIL:
        return None
    elif tp == lib.LUA_TNUMBER:
        try:
            return LuaNumber.__int__(obj)
        except TypeError:
            return LuaNumber.__float__(obj)
    elif tp == lib.LUA_TBOOLEAN:
            return LuaBoolean.__bool__(obj)
    elif tp == lib.LUA_TSTRING:
        if (runtime.autodecode if autodecode is None else autodecode):
            return LuaString.__str__(obj)
        else:
            return LuaString.__bytes__(obj)
    else:
        with lock_get_state(runtime) as L:
            with ensure_stack_balance(runtime):
                obj._pushobj()
                if lib.lua_getmetatable(L, -1):
                    lib.luaL_getmetatable(L, PYOBJ_SIG)
                    if lib.lua_rawequal(L, -2, -1):
                        obj = ffi.from_handle(lib.lua_topointer(L, -3))
                        if isinstance(obj, Py2LuaProtocol) and autounpack:
                            obj = obj.obj
                        return obj
        return obj.settle()
