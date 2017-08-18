"""
cffi implement of lupa with lowlevel lua API
"""

from threading import RLock
from sys import exc_info
from collections import Mapping
import six
from . import lua
from .version import __version__


def lua_type(obj):
    """
    Return the Lua type name of a wrapped object as string, as provided
    by Lua's type() function.

    For non-wrapper objects (i.e. normal Python objects), returns None.
    """
    if not isinstance(obj, _LuaObject):
        return None
    lua_object = obj
    lock_runtime(lua_object._runtime)
    L = lua_object._state
    old_top = lua.lib.lua_gettop(L)
    try:
        lua.lib.lua_rawgeti(L, lua.lib.LUA_REGISTRYINDEX, lua_object._ref)
        ltype = lua.lib.lua_type(L, -1)
        if ltype == lua.lib.LUA_TTABLE:
            return 'table'
        elif ltype == lua.lib.LUA_TFUNCTION:
            return 'function'
        elif ltype == lua.lib.LUA_TTHREAD:
            return 'thread'
        elif ltype in (lua.lib.LUA_TUSERDATA, lua.lib.LUA_TLIGHTUSERDATA):
            return 'userdata'
        else:
            lua_type_name = lua.lib.lua_typename(L, ltype)
            return lua.ffi.string(lua_type_name).decode('ascii')
    finally:
        lua.lib.lua_settop(L, old_top)
        unlock_runtime(lua_object._runtime)


class LuaError(Exception):
    """Base class for errors in the Lua runtime.
    """

class LuaSyntaxError(LuaError):
    """Syntax error in Lua code.
    """

class LuaPanic(LuaError):
    """Lua panic
    """

@lua.ffi.def_extern('_py_lua_panic')
def py_lua_panic(L):
    raise LuaPanic("PANIC: unprotected error in call to Lua API (%s)" % lua.ffi.string(lua.lib.lua_tostring(L, -1)).decode('ascii'))


class LuaRuntime(object):
    """The main entry point to the Lua runtime.

    Available options:

    * ``encoding``: the string encoding, defaulting to UTF-8.  If set
      to ``None``, all string values will be returned as byte strings.
      Otherwise, they will be decoded to unicode strings on the way
      from Lua to Python and unicode strings will be encoded on the
      way to Lua.  Note that ``str()`` calls on Lua objects will
      always return a unicode object.

    * ``source_encoding``: the encoding used for Lua code, defaulting to
      the string encoding or UTF-8 if the string encoding is ``None``.

    * ``attribute_filter``: filter function for attribute access
      (get/set).  Must have the signature ``func(obj, attr_name,
      is_setting)``, where ``is_setting`` is True when the attribute
      is being set.  If provided, the function will be called for all
      Python object attributes that are being accessed from Lua code.
      Normally, it should return an attribute name that will then be
      used for the lookup.  If it wants to prevent access, it should
      raise an ``AttributeError``.  Note that Lua does not guarantee
      that the names will be strings.  (New in Lupa 0.20)

    * ``attribute_handlers``: like ``attribute_filter`` above, but
      handles the getting/setting itself rather than giving hints
      to the LuaRuntime.  This must be a 2-tuple, ``(getter, setter)``
      where ``getter`` has the signature ``func(obj, attr_name)``
      and either returns the value for ``obj.attr_name`` or raises an
      ``AttributeError``  The function ``setter`` has the signature
      ``func(obj, attr_name, value)`` and may raise an ``AttributeError``.
      The return value of the setter is unused.  (New in Lupa 1.0)

    * ``register_eval``: should Python's ``eval()`` function be available
      to Lua code as ``python.eval()``?  Note that this does not remove it
      from the builtins.  Use an ``attribute_filter`` function for that.
      (default: True)

    * ``register_builtins``: should Python's builtins be available to Lua
      code as ``python.builtins.*``?  Note that this does not prevent access
      to the globals available as special Python function attributes, for
      example.  Use an ``attribute_filter`` function for that.
      (default: True, new in Lupa 1.2)

    * ``unpack_returned_tuples``: should Python tuples be unpacked in Lua?
      If ``py_fun()`` returns ``(1, 2, 3)``, then does ``a, b, c = py_fun()``
      give ``a == 1 and b == 2 and c == 3`` or does it give
      ``a == (1,2,3), b == nil, c == nil``?  ``unpack_returned_tuples=True``
      gives the former.
      (default: False, new in Lupa 0.21)

    Example usage::

      >>> from ffilupa import LuaRuntime
      >>> lua = LuaRuntime()

      >>> lua.eval('1+1')
      2

      >>> lua_func = lua.eval('function(f, n) return f(n) end')

      >>> def py_add1(n): return n+1
      >>> lua_func(py_add1, 2)
      3
    """

    def __init__(self, encoding='UTF-8', source_encoding=None,
                  attribute_filter=None, attribute_handlers=None,
                  register_eval=True, unpack_returned_tuples=False,
                  register_builtins=True):
        L = lua.lib.luaL_newstate()
        if L is lua.ffi.NULL:
            raise LuaError("Failed to initialise Lua runtime")
        self._state = L
        self._lock = RLock()
        self._pyrefs_in_lua = []
        self._rtrefs_in_lua = []
        self._raised_exception = None
        self._encoding = encoding
        self._source_encoding = source_encoding or self._encoding or 'UTF-8'
        self._attribute_filter = None
        self._attribute_getter = None
        self._attribute_setter = None
        if attribute_filter is not None and not callable(attribute_filter):
            raise ValueError("attribute_filter must be callable")
        self._attribute_filter = attribute_filter
        self._unpack_returned_tuples = unpack_returned_tuples

        if attribute_handlers:
            raise_error = False
            try:
                getter, setter = attribute_handlers
            except (ValueError, TypeError):
                raise_error = True
            else:
                if (getter is not None and not callable(getter) or
                        setter is not None and not callable(setter)):
                    raise_error = True
            if raise_error:
                raise ValueError("attribute_handlers must be a sequence of two callables")
            if attribute_filter and (getter is not None or setter is not None):
                raise ValueError("attribute_filter and attribute_handlers are mutually exclusive")
            self._attribute_getter, self._attribute_setter = getter, setter

        lua.lib.luaL_openlibs(L)
        self.init_python_lib(register_eval, register_builtins)
        lua.lib.lua_settop(L, 0)
        lua.lib.lua_atpanic(L, lua.lib._py_lua_panic)

    def __del__(self):
        if self._state is not lua.ffi.NULL:
            lua.lib.lua_close(self._state)
            self._state = lua.ffi.NULL

    def reraise_on_exception(self):
        if self._raised_exception is not None:
            exception = self._raised_exception
            self._raised_exception = None
            six.reraise(exception[0], exception[1], exception[2])

    def store_raised_exception(self, L, lua_error_msg):
        try:
            self._raised_exception = exc_info()
            py_to_lua(self, L, self._raised_exception[1])
        except:
            lua.lib.lua_pushlstring(L, lua_error_msg, len(lua_error_msg))
            raise

    def eval(self, lua_code, *args):
        """Evaluate a Lua expression passed in a string.
        """
        if isinstance(lua_code, six.text_type):
            lua_code = lua_code.encode(self._source_encoding)
        return run_lua(self, b'return ' + lua_code, args)

    def execute(self, lua_code, *args):
        """Execute a Lua program passed in a string.
        """
        if isinstance(lua_code, six.text_type):
            lua_code = lua_code.encode(self._source_encoding)
        return run_lua(self, lua_code, args)

    def register_py_object(self, cname, pyname, obj):
        L = self._state
        lua.lib.lua_pushlstring(L, cname, len(cname))
        if not py_to_lua_custom(self, L, obj, 0):
            lua.lib.lua_pop(L, 1)
            raise LuaError("failed to convert %s object" % pyname)
        lua.lib.lua_pushlstring(L, pyname, len(pyname))
        lua.lib.lua_pushvalue(L, -2)
        lua.lib.lua_rawset(L, -5)
        lua.lib.lua_rawset(L, lua.lib.LUA_REGISTRYINDEX)

    def init_python_lib(self, register_eval, register_builtins):
        L = self._state
        oldtop = lua.lib.lua_gettop(L)
        lua.lib.luaL_newmetatable(L, POBJECT)
        py_object_lib = [
            {'name': lua.ffi.new('char[]', b"__call"),     'func': lua.lib._py_object_call},
            {'name': lua.ffi.new('char[]', b"__tostring"), 'func': lua.lib._py_object_str},
            {'name': lua.ffi.new('char[]', b"__index"),    'func': lua.lib._py_object_getindex},
            {'name': lua.ffi.new('char[]', b"__newindex"), 'func': lua.lib._py_object_setindex},
            {'name': lua.ffi.new('char[]', b"__gc"),       'func': lua.lib._py_object_gc},
        ]
        lua.lib.luaL_setfuncs(L, lua.ffi.new('luaL_Reg[]', py_object_lib + [{'name': lua.ffi.NULL, 'func': lua.ffi.NULL}]), 0)
        lua.lib.lua_pop(L, 1)
        lua.lib.lua_pushglobaltable(L)
        lua.lib.lua_pushstring(L, b'python')
        lua.lib.lua_newtable(L)
        self.register_py_object(b'Py_None',  b'none', None)
        if register_eval:
            self.register_py_object(b'eval',     b'eval', eval)
        if register_builtins:
            self.register_py_object(b'builtins', b'builtins', six.moves.builtins)
        py_lib = [
            {'name': lua.ffi.new('char[]', b"as_attrgetter"),   'func': lua.lib._py_as_attrgetter},
            {'name': lua.ffi.new('char[]', b"as_itemgetter"),   'func': lua.lib._py_as_itemgetter},
            {'name': lua.ffi.new('char[]', b"as_function"),     'func': lua.lib._py_as_function},
            {'name': lua.ffi.new('char[]', b"iter"),            'func': lua.lib._py_iter},
            {'name': lua.ffi.new('char[]', b"iterex"),          'func': lua.lib._py_iterex},
            {'name': lua.ffi.new('char[]', b"enumerate"),       'func': lua.lib._py_enumerate},
        ]
        lua.lib.luaL_setfuncs(L, lua.ffi.new('luaL_Reg[]', py_lib + [{'name': lua.ffi.NULL, 'func': lua.ffi.NULL}]), 0)
        lua.lib.lua_rawset(L, -3)
        lua.lib.lua_pop(L, 1)

    def globals(self):
        """Return the globals defined in this Lua runtime as a Lua
        table.
        """
        L = self._state
        lua.lib.lua_pushglobaltable(L)
        G = py_from_lua(self, L, -1)
        lua.lib.lua_pop(L, 1)
        return G

    def table(self, *items, **kwargs):
        """Create a new table with the provided items.  Positional
        arguments are placed in the table in order, keyword arguments
        are set as key-value pairs.
        """
        return self.table_from(items, kwargs)

    def table_from(self, *args):
        """Create a new table from Python mapping or iterable.

        table_from() accepts either a dict/mapping or an iterable with items.
        Items from dicts are set as key-value pairs; items from iterables
        are placed in the table in order.

        Nested mappings / iterables are passed to Lua as userdata
        (wrapped Python objects); they are not converted to Lua tables.
        """
        L = self._state
        i = 1
        lock_runtime(self)
        old_top = lua.lib.lua_gettop(L)
        try:
            lua.lib.lua_newtable(L)
            for obj in args:
                if isinstance(obj, _LuaTable):
                    obj.push_lua_object()
                    lua.lib.lua_pushnil(L)
                    while lua.lib.lua_next(L, -2):
                        lua.lib.lua_pushvalue(L, -2)
                        lua.lib.lua_insert(L, -2)
                        lua.lib.lua_settable(L, -5)
                    lua.lib.lua_pop(L, 1)

                elif isinstance(obj, Mapping):
                    for key in obj:
                        value = obj[key]
                        py_to_lua(self, L, key)
                        py_to_lua(self, L, value)
                        lua.lib.lua_rawset(L, -3)
                else:
                    for arg in obj:
                        py_to_lua(self, L, arg)
                        lua.lib.lua_rawseti(L, -2, i)
                        i += 1
            return py_from_lua(self, L, -1)
        finally:
            lua.lib.lua_settop(L, old_top)
            unlock_runtime(self)

    def require(self, modulename):
        """Load a Lua library into the runtime.
        """
        return self.globals().require(modulename)

    @property
    def lua_state(self):
        """the pointer to ``lua_State`` object"""
        return self._state


def unpacks_lua_table(func):
    """
    A decorator to make the decorated function receive kwargs
    when it is called from Lua with a single Lua table argument.

    Python functions wrapped in this decorator can be called from Lua code
    as ``func(foo, bar)``, ``func{foo=foo, bar=bar}`` and ``func{foo, bar=bar}``.

    See also: http://lua-users.org/wiki/NamedParameters

    WARNING: avoid using this decorator for functions where the
    first argument can be a Lua table.

    WARNING: be careful with ``nil`` values.  Depending on the context,
    passing ``nil`` as a parameter can mean either "omit a parameter"
    or "pass None".  This even depends on the Lua version.  It is
    possible to use ``python.none`` instead of ``nil`` to pass None values
    robustly.
    """
    @six.wraps(func)
    def wrapper(*args):
        args, kwargs = _fix_args_kwargs(args)
        return func(*args, **kwargs)
    return wrapper


def unpacks_lua_table_method(meth):
    """
    This is :func:`unpacks_lua_table` for methods
    (i.e. it knows about the 'self' argument).
    """
    @six.wraps(meth)
    def wrapper(self, *args):
        args, kwargs = _fix_args_kwargs(args)
        return meth(self, *args, **kwargs)
    return wrapper


def _fix_args_kwargs(args):
    """
    Extract named arguments from args passed to a Python function by Lua
    script. Arguments are processed only if a single argument is passed and
    it is a table.
    """
    if len(args) != 1:
        return args, {}

    arg = args[0]
    if not isinstance(arg, _LuaTable):
        return args, {}

    table = arg
    encoding = table._runtime._source_encoding

    # arguments with keys from 1 to #tbl are passed as positional
    new_args = [
        table._getitem(key, is_attr_access=False)
        for key in range(1, table._len() + 1)
    ]

    # arguments with non-integer keys are passed as named
    new_kwargs = {
        key.decode(encoding) if isinstance(key, six.binary_type) else key: value
        for key, value in _LuaIter(table, ITEMS)
        if not isinstance(key, six.integer_types)
    }
    return new_args, new_kwargs


def lock_runtime(runtime):
    runtime._lock.acquire()


def unlock_runtime(runtime):
    runtime._lock.release()


@six.python_2_unicode_compatible
class _LuaObject(object):
    """A wrapper around a Lua object such as a table or function.
    """
    def __init__(self):
        raise TypeError("Type cannot be instantiated manually")

    def __del__(self):
        if self._runtime is None:
            return
        L = self._state
        try:
            lock_runtime(self._runtime)
            locked = True
        except:
            locked = False
        lua.lib.luaL_unref(L, lua.lib.LUA_REGISTRYINDEX, self._ref)
        if locked:
            unlock_runtime(self._runtime)

    def push_lua_object(self):
        L = self._state
        lua.lib.lua_rawgeti(L, lua.lib.LUA_REGISTRYINDEX, self._ref)
        if lua.lib.lua_isnil(L, -1):
            lua.lib.lua_pop(L, 1)
            raise LuaError("lost reference")

    def __call__(self, *args):
        L = self._state
        lock_runtime(self._runtime)
        try:
            lua.lib.lua_settop(L, 0)
            self.push_lua_object()
            return call_lua(self._runtime, L, args)
        finally:
            lua.lib.lua_settop(L, 0)
            unlock_runtime(self._runtime)

    def __len__(self):
        return self._len()

    def _len(self):
        L = self._state
        lock_runtime(self._runtime)
        size = 0
        try:
            self.push_lua_object()
            size = lua.lib.lua_rawlen(L, -1)
            lua.lib.lua_pop(L, 1)
        finally:
            unlock_runtime(self._runtime)
        return size

    def __nonzero__(self):
        return True

    def __bool__(self):
        return self.__nonzero__()

    def __iter__(self):
        raise TypeError("iteration is only supported for tables")

    def __repr__(self):
        L = self._state
        encoding = self._runtime._encoding or 'UTF-8'
        lock_runtime(self._runtime)
        try:
            self.push_lua_object()
            return lua_object_repr(L, encoding)
        finally:
            lua.lib.lua_pop(L, 1)
            unlock_runtime(self._runtime)

    def __str__(self):
        L = self._state
        py_string = None
        encoding = self._runtime._encoding or 'UTF-8'
        lock_runtime(self._runtime)
        old_top = lua.lib.lua_gettop(L)
        try:
            self.push_lua_object()
            if lua.lib.lua_getmetatable(L, -1):
                lua.lib.lua_pushstring(L, b"__tostring")
                lua.lib.lua_rawget(L, -2)
                if not lua.lib.lua_isnil(L, -1) and lua.lib.lua_pcall(L, 1, 1, 0) == 0:
                    size = lua.ffi.new('size_t*')
                    s = lua.lib.lua_tolstring(L, -1, size)
                    size = size[0]
                    if s:
                        try:
                            py_string = lua.ffi.unpack(s, size).decode(encoding)
                        except UnicodeDecodeError:
                            # safe 'decode'
                            py_string = lua.ffi.unpack(s, size).decode('ISO-8859-1')
            if py_string is None:
                lua.lib.lua_settop(L, old_top + 1)
                py_string = lua_object_repr(L, encoding)
        finally:
            lua.lib.lua_settop(L, old_top)
            unlock_runtime(self._runtime)
        return py_string

    def __getattr__(self, name):
        if isinstance(name, six.text_type):
            name = name.encode(self._runtime._source_encoding)
        return self._getitem(name, is_attr_access=True)

    def __getitem__(self, index_or_name):
        return self._getitem(index_or_name, is_attr_access=False)

    def _getitem(self, name, is_attr_access):
        L = self._state
        lock_runtime(self._runtime)
        old_top = lua.lib.lua_gettop(L)
        try:
            self.push_lua_object()
            lua_type = lua.lib.lua_type(L, -1)
            if lua_type == lua.lib.LUA_TFUNCTION or lua_type == lua.lib.LUA_TTHREAD:
                lua.lib.lua_pop(L, 1)
                raise (AttributeError if is_attr_access else TypeError)(
                    "item/attribute access not supported on functions")
            py_to_lua(self._runtime, L, name, wrap_none=lua_type == lua.lib.LUA_TTABLE)
            lua.lib.lua_gettable(L, -2)
            return py_from_lua(self._runtime, L, -1)
        finally:
            lua.lib.lua_settop(L, old_top)
            unlock_runtime(self._runtime)


def new_lua_object(runtime, L, n):
    obj = _LuaObject.__new__(_LuaObject)
    init_lua_object(obj, runtime, L, n)
    return obj

def init_lua_object(obj, runtime, L, n):
    object.__setattr__(obj, '_runtime', runtime)
    object.__setattr__(obj, '_state', L)
    lua.lib.lua_pushvalue(L, n)
    object.__setattr__(obj, '_ref', lua.lib.luaL_ref(L, lua.lib.LUA_REGISTRYINDEX))

def lua_object_repr(L, encoding):
    lua_type = lua.lib.lua_type(L, -1)
    if lua_type in (lua.lib.LUA_TTABLE, lua.lib.LUA_TFUNCTION):
        ptr = lua.ffi.cast('void*', lua.lib.lua_topointer(L, -1))
    elif lua_type in (lua.lib.LUA_TUSERDATA, lua.lib.LUA_TLIGHTUSERDATA):
        ptr = lua.ffi.cast('void*', lua.lib.lua_touserdata(L, -1))
    elif lua_type == lua.lib.LUA_TTHREAD:
        ptr = lua.ffi.cast('void*', lua.lib.lua_tothread(L, -1))
    else:
        ptr = lua.ffi.NULL
    if ptr:
        py_bytes = b"<Lua %s at 0x%x>" % (lua.ffi.string(lua.lib.lua_typename(L, lua_type)), ptr - lua.ffi.NULL)
    else:
        py_bytes = b"<Lua %s>" % lua.ffi.string(lua.lib.lua_typename(L, lua_type))
    try:
        return py_bytes.decode(encoding)
    except UnicodeDecodeError:
        return py_bytes.decode('ISO-8859-1')


class _LuaTable(_LuaObject):
    def __iter__(self):
        return _LuaIter(self, KEYS)

    def keys(self):
        """Returns an iterator over the keys of a table that this
        object represents.  Same as iter(obj).
        """
        return _LuaIter(self, KEYS)

    def values(self):
        """Returns an iterator over the values of a table that this
        object represents.
        """
        return _LuaIter(self, VALUES)

    def items(self):
        """Returns an iterator over the key-value pairs of a table
        that this object represents.
        """
        return _LuaIter(self, ITEMS)

    def __setattr__(self, name, value):
        if isinstance(name, six.text_type):
            name = name.encode(self._runtime._source_encoding)
        self._setitem(name, value)

    def __setitem__(self, index_or_name, value):
        self._setitem(index_or_name, value)

    def _setitem(self, name, value):
        L = self._state
        lock_runtime(self._runtime)
        old_top = lua.lib.lua_gettop(L)
        try:
            self.push_lua_object()
            py_to_lua(self._runtime, L, name, wrap_none=True)
            py_to_lua(self._runtime, L, value)
            lua.lib.lua_settable(L, -3)
        finally:
            lua.lib.lua_settop(L, old_top)
            unlock_runtime(self._runtime)

    def __delattr__(self, item):
        if isinstance(item, six.text_type):
            item = item.encode(self._runtime._source_encoding)
        self._delitem(item)

    def __delitem__(self, key):
        self._delitem(key)

    def _delitem(self, name):
        L = self._state
        lock_runtime(self._runtime)
        old_top = lua.lib.lua_gettop(L)
        try:
            self.push_lua_object()
            py_to_lua(self._runtime, L, name, wrap_none=True)
            lua.lib.lua_pushnil(L)
            lua.lib.lua_settable(L, -3)
        finally:
            lua.lib.lua_settop(L, old_top)
            unlock_runtime(self._runtime)


KEYS = 1
VALUES = 2
ITEMS = 3


class _LuaIter(six.Iterator):
    def __init__(self, obj, what):
        self._runtime = obj._runtime
        self._obj = obj
        self._state = obj._state
        self._refiter = 0
        self._what = what

    def __del__(self):
        if self._runtime is None:
            return
        L = self._state
        if L is not lua.ffi.NULL and self._refiter:
            locked = False
            try:
                lock_runtime(self._runtime)
                locked = True
            except:
                pass
            lua.lib.luaL_unref(L, lua.lib.LUA_REGISTRYINDEX, self._refiter)
            if locked:
                unlock_runtime(self._runtime)

    def __repr__(self):
        return u"LuaIter(%r)" % (self._obj)

    def __iter__(self):
        return self

    def __next__(self):
        if self._obj is None:
            raise StopIteration
        L = self._obj._state
        lock_runtime(self._runtime)
        old_top = lua.lib.lua_gettop(L)
        try:
            if self._obj is None:
                raise StopIteration
            lua.lib.lua_rawgeti(L, lua.lib.LUA_REGISTRYINDEX, self._obj._ref)
            if not lua.lib.lua_istable(L, -1):
                if lua.lib.lua_isnil(L, -1):
                    lua.lib.lua_pop(L, 1)
                    raise LuaError("lost reference")
                raise TypeError("cannot iterate over non-table (found %r)" % self._obj)
            if not self._refiter:
                lua.lib.lua_pushnil(L)
            else:
                lua.lib.lua_rawgeti(L, lua.lib.LUA_REGISTRYINDEX, self._refiter)
            if lua.lib.lua_next(L, -2):
                try:
                    if self._what == KEYS:
                        retval = py_from_lua(self._runtime, L, -2)
                    elif self._what == VALUES:
                        retval = py_from_lua(self._runtime, L, -1)
                    else:
                        retval = (py_from_lua(self._runtime, L, -2), py_from_lua(self._runtime, L, -1))
                finally:
                    lua.lib.lua_pop(L, 1)
                    if not self._refiter:
                        self._refiter = lua.lib.luaL_ref(L, lua.lib.LUA_REGISTRYINDEX)
                    else:
                        lua.lib.lua_rawseti(L, lua.lib.LUA_REGISTRYINDEX, self._refiter)
                return retval
            if self._refiter:
                lua.lib.luaL_unref(L, lua.lib.LUA_REGISTRYINDEX, self._refiter)
                self._refiter = 0
            self._obj = None
        finally:
            lua.lib.lua_settop(L, old_top)
            unlock_runtime(self._runtime)
        raise StopIteration


def new_lua_table(runtime, L, n):
    obj = _LuaTable.__new__(_LuaTable)
    init_lua_object(obj, runtime, L, n)
    return obj


class _LuaFunction(_LuaObject):
    """A Lua function (which may become a coroutine).
    """
    def coroutine(self, *args):
        """Create a Lua coroutine from a Lua function and call it with
        the passed parameters to start it up.
        """
        L = self._state
        lock_runtime(self._runtime)
        old_top = lua.lib.lua_gettop(L)
        try:
            self.push_lua_object()
            if not lua.lib.lua_isfunction(L, -1) or lua.lib.lua_iscfunction(L, -1):
                raise TypeError("Lua object is not a function")
            co = lua.lib.lua_newthread(L)
            lua.lib.lua_pushvalue(L, 1)
            lua.lib.lua_xmove(L, co, 1)
            thread = new_lua_thread(self._runtime, L, -1)
            thread._arguments = args
            return thread
        finally:
            lua.lib.lua_settop(L, old_top)
            unlock_runtime(self._runtime)

def new_lua_function(runtime, L, n):
    obj = _LuaFunction.__new__(_LuaFunction)
    init_lua_object(obj, runtime, L, n)
    return obj


class _LuaCoroutineFunction(_LuaFunction):
    """A function that returns a new coroutine when called.
    """
    def __call__(self, *args):
        return self.coroutine(*args)

def new_lua_coroutine_function(runtime, L, n):
    obj = _LuaCoroutineFunction.__new__(_LuaCoroutineFunction)
    init_lua_object(obj, runtime, L, n)
    return obj


class _LuaThread(_LuaObject, six.Iterator):
    """A Lua thread (coroutine).
    """
    def __iter__(self):
        return self

    def __next__(self):
        args = self._arguments
        if args is not None:
            self._arguments = None
        return resume_lua_thread(self, args)

    def send(self, value):
        """Send a value into the coroutine.  If the value is a tuple,
        send the unpacked elements.
        """
        if value is not None:
            if self._arguments is not None:
                raise TypeError("can't send non-None value to a just-started generator")
            if not isinstance(value, tuple):
                value = (value,)
        elif self._arguments is not None:
            value = self._arguments
            self._arguments = None
        return resume_lua_thread(self, value)

    def __nonzero__(self):
        status = lua.lib.lua_status(self._co_state)
        if status == lua.lib.LUA_YIELD:
            return True
        if status == lua.lib.LUA_OK:
            if lua.lib.lua_getstack(self._co_state, 0, lua.ffi.NULL) > 0:
                return True
            elif lua.lib.lua_gettop(self._co_state) > 0:
                return True
        return False

def new_lua_thread(runtime, L, n):
    obj = _LuaThread.__new__(_LuaThread)
    init_lua_object(obj, runtime, L, n)
    object.__setattr__(obj, '_co_state', lua.lib.lua_tothread(L, n))
    object.__setattr__(obj, '_arguments', None)
    return obj


def new_lua_thread_or_function(runtime, L, n):
    co = lua.lib.lua_tothread(L, n)
    if lua.lib.lua_status(co) == 0 and lua.lib.lua_gettop(co) == 1:
        lua.lib.lua_pushvalue(co, 1)
        lua.lib.lua_xmove(co, L, 1)
        try:
            return new_lua_coroutine_function(runtime, L, -1)
        finally:
            lua.lib.lua_pop(L, 1)
    else:
        return new_lua_thread(runtime, L, n)


def resume_lua_thread(thread, args):
    co = thread._co_state
    L = thread._state
    nargs = 0
    nres = 0
    lock_runtime(thread._runtime)
    old_top = lua.lib.lua_gettop(L)
    try:
        if lua.lib.lua_status(co) == 0 and lua.lib.lua_gettop(co) == 0:
            raise StopIteration
        if args:
            nargs = len(args)
            push_lua_arguments(thread._runtime, co, args)
        status = lua.lib.lua_resume(co, L, nargs)
        nres = lua.lib.lua_gettop(co)
        if status != lua.lib.LUA_YIELD:
            if status == 0:
                if nres == 0:
                    raise StopIteration
            else:
                raise_lua_error(thread._runtime, co, status)

        lua.lib.lua_xmove(co, L, nres)
        return unpack_lua_results(thread._runtime, L)
    finally:
        lua.lib.lua_settop(L, old_top)
        unlock_runtime(thread._runtime)


def raise_lua_error(runtime, L, result):
    if result == 0:
        return
    elif result == lua.lib.LUA_ERRMEM:
        raise MemoryError()
    else:
        raise LuaError( build_lua_error_message(runtime, L, None, -1) )


def build_lua_error_message(runtime, L, err_message, n):
    size = lua.ffi.new('size_t*')
    s = lua.lib.lua_tolstring(L, n, size)
    size = size[0]
    if runtime._encoding is not None:
        try:
            py_ustring = lua.ffi.unpack(s, size).decode(runtime._encoding)
        except UnicodeDecodeError:
            py_ustring = lua.ffi.unpack(s, size).decode('ISO-8859-1')
    else:
        py_ustring = lua.ffi.unpack(s, size).decode('ISO-8859-1')
    if err_message is None:
        return py_ustring
    else:
        return err_message % py_ustring


def run_lua(runtime, lua_code, args):
    L = runtime._state
    lock_runtime(runtime)
    old_top = lua.lib.lua_gettop(L)
    try:
        if lua.lib.luaL_loadbuffer(L, lua_code, len(lua_code), b'<python>'):
            raise LuaSyntaxError(build_lua_error_message(
                runtime, L, u"error loading code: %s", -1))
        return call_lua(runtime, L, args)
    finally:
        lua.lib.lua_settop(L, old_top)
        unlock_runtime(runtime)


def call_lua(runtime, L, args):
    push_lua_arguments(runtime, L, args)
    return execute_lua_call(runtime, L, len(args))


def execute_lua_call(runtime, L, nargs):
    errfunc = 0
    lua.lib.lua_getglobal(L, b"debug")
    if not lua.lib.lua_istable(L, -1):
        lua.lib.lua_pop(L, 1)
    else:
        lua.lib.lua_getfield(L, -1, b"traceback")
        if not lua.lib.lua_isfunction(L, -1):
            lua.lib.lua_pop(L, 2)
        else:
            lua.lib.lua_replace(L, -2)
            lua.lib.lua_insert(L, 1)
            errfunc = 1
    result_status = lua.lib.lua_pcall(L, nargs, lua.lib.LUA_MULTRET, errfunc)
    if errfunc:
        lua.lib.lua_remove(L, 1)
    results = unpack_lua_results(runtime, L)
    if result_status:
        if isinstance(results, BaseException):
            runtime.reraise_on_exception()
        raise_lua_error(runtime, L, result_status)
    return results


def push_lua_arguments(runtime, L, args, first_may_be_nil=True):
    if args:
        old_top = lua.lib.lua_gettop(L)
        for i, arg in enumerate(args):
            if not py_to_lua(runtime, L, arg, wrap_none=not first_may_be_nil):
                lua.lib.lua_settop(L, old_top)
                raise TypeError("failed to convert argument at index %d" % i)
            first_may_be_nil = True


def unpack_lua_results(runtime, L):
    nargs = lua.lib.lua_gettop(L)
    if nargs == 1:
        return py_from_lua(runtime, L, 1)
    if nargs == 0:
        return None
    return unpack_multiple_lua_results(runtime, L, nargs)


def unpack_multiple_lua_results(runtime, L, nargs):
    return tuple([py_from_lua(runtime, L, i + 1) for i in range(nargs)])


_PYFUNCTION_SIG = lua.ffi.new('char*')
PYFUNCTION_SIG = lua.ffi.cast('void*', _PYFUNCTION_SIG)
OBJ_AS_INDEX = 1
OBJ_UNPACK_TUPLE = 2
OBJ_ENUMERATOR = 4
POBJECT = b'POBJECT'

@lua.ffi.def_extern('_py_asfunc_call')
def py_asfunc_call(L):
    if (lua.lib.lua_gettop(L) == 1 and lua.lib.lua_islightuserdata(L, 1)
            and lua.lib.lua_topointer(L, 1) == PYFUNCTION_SIG):
        lua.lib.lua_pushvalue(L, lua.lib.lua_upvalueindex(1))
        return 1
    lua.lib.lua_pushvalue(L, lua.lib.lua_upvalueindex(1))
    lua.lib.lua_insert(L, 1)
    return py_object_call(L)

def unpack_wrapped_pyfunction(L, n):
    cfunction = lua.lib.lua_tocfunction(L, n)
    if cfunction is lua.ffi.cast('lua_CFunction', lua.lib._py_asfunc_call):
        lua.lib.lua_pushvalue(L, n)
        lua.lib.lua_pushlightuserdata(L, PYFUNCTION_SIG)
        if lua.lib.lua_pcall(L, 1, 1, 0) == 0:
            return unpack_userdata(L, -1)
    return lua.ffi.NULL


class _PyProtocolWrapper(object):
    def __init__(self):
        raise TypeError("Type cannot be instantiated from Python")


def as_attrgetter(obj):
    wrap = _PyProtocolWrapper.__new__(_PyProtocolWrapper)
    object.__setattr__(wrap, '_obj', obj)
    object.__setattr__(wrap, '_type_flags', 0)
    return wrap

def as_itemgetter(obj):
    wrap = _PyProtocolWrapper.__new__(_PyProtocolWrapper)
    object.__setattr__(wrap, '_obj', obj)
    object.__setattr__(wrap, '_type_flags', OBJ_AS_INDEX)
    return wrap


def py_from_lua(runtime, L, n):
    """
    Convert a Lua object to a Python object by either mapping, wrapping
    or unwrapping it.
    """
    lua_type = lua.lib.lua_type(L, n)
    if lua_type == lua.lib.LUA_TNIL:
        return None
    elif lua_type == lua.lib.LUA_TNUMBER:
        if lua.lib.lua_isinteger(L, n):
            return lua.lib.lua_tointeger(L, n)
        else:
            return lua.lib.lua_tonumber(L, n)
    elif lua_type == lua.lib.LUA_TSTRING:
        size = lua.ffi.new('size_t*')
        s = lua.lib.lua_tolstring(L, n, size)
        size = size[0]
        if runtime._encoding is not None:
            return lua.ffi.unpack(s, size).decode(runtime._encoding)
        else:
            return lua.ffi.unpack(s, size)
    elif lua_type == lua.lib.LUA_TBOOLEAN:
        return bool(lua.lib.lua_toboolean(L, n))
    elif lua_type == lua.lib.LUA_TTABLE:
        return new_lua_table(runtime, L, n)
    elif lua_type == lua.lib.LUA_TTHREAD:
        return new_lua_thread_or_function(runtime, L, n)
    elif lua_type == lua.lib.LUA_TFUNCTION:
        py_obj = unpack_wrapped_pyfunction(L, n)
        if py_obj:
            return py_obj.obj
        return new_lua_function(runtime, L, n)
    elif lua_type == lua.lib.LUA_TUSERDATA:
        py_obj = unpack_userdata(L, n)
        if py_obj:
            return lua.ffi.from_handle(py_obj[0].obj)
    return new_lua_object(runtime, L, n)

def unpack_userdata(L, n):
    """
    Like luaL_checkudata(), unpacks a userdata object and validates that
    it's a wrapped Python object.  Returns NULL on failure.
    """
    p = lua.lib.lua_touserdata(L, n)
    if p and lua.lib.lua_getmetatable(L, n):
        lua.lib.luaL_getmetatable(L, POBJECT)
        if lua.lib.lua_rawequal(L, -1, -2):
            lua.lib.lua_pop(L, 2)
            return lua.ffi.cast('_py_object*', p)
        lua.lib.lua_pop(L, 2)
    return lua.ffi.NULL

def py_to_lua(runtime, L, o, wrap_none=False):
    pushed_values_count = 0
    type_flags = 0

    if o is None:
        if wrap_none:
            lua.lib.lua_pushstring(L, b"Py_None")
            lua.lib.lua_rawget(L, lua.lib.LUA_REGISTRYINDEX)
            if lua.lib.lua_isnil(L, -1):
                lua.lib.lua_pop(L, 1)
                return 0
            pushed_values_count = 1
        else:
            lua.lib.lua_pushnil(L)
            pushed_values_count = 1
    elif isinstance(o, bool):
        lua.lib.lua_pushboolean(L, int(o))
        pushed_values_count = 1
    elif isinstance(o, float):
        lua.lib.lua_pushnumber(L, o)
        pushed_values_count = 1
    elif isinstance(o, six.integer_types):
        if lua.ffi.cast('lua_Integer', o) != o:
            lua.lib.lua_pushnumber(L, o)
        else:
            lua.lib.lua_pushinteger(L, o)
        pushed_values_count = 1
    elif isinstance(o, six.binary_type):
        lua.lib.lua_pushlstring(L, o, len(o))
        pushed_values_count = 1
    elif isinstance(o, six.text_type) and runtime._encoding is not None:
        pushed_values_count = push_encoded_unicode_string(runtime, L, o)
    elif isinstance(o, _LuaObject):
        if o._runtime is not runtime:
            raise LuaError("cannot mix objects from different Lua runtimes")
        lua.lib.lua_rawgeti(L, lua.lib.LUA_REGISTRYINDEX, o._ref)
        pushed_values_count = 1
    else:
        if isinstance(o, _PyProtocolWrapper):
            type_flags = o._type_flags
            o = o._obj
        else:
            type_flags = OBJ_AS_INDEX if hasattr(o, '__getitem__') else 0
        pushed_values_count = py_to_lua_custom(runtime, L, o, type_flags)
    return pushed_values_count

def push_encoded_unicode_string(runtime, L, ustring):
    bytes_string = ustring.encode(runtime._encoding)
    lua.lib.lua_pushlstring(L, bytes_string, len(bytes_string))
    return 1

def py_to_lua_custom(runtime, L, o, type_flags):
    py_obj = lua.ffi.cast('_py_object*', lua.lib.lua_newuserdata(L, lua.ffi.sizeof('_py_object')))
    if not py_obj:
        return 0
    o_handle = lua.ffi.new_handle(o)
    runtime_handle = lua.ffi.new_handle(runtime)
    runtime._pyrefs_in_lua.append(o_handle)
    runtime._rtrefs_in_lua.append(runtime_handle)

    py_obj[0] = {
        'obj': o_handle,
        'runtime': runtime_handle,
        'type_flags': type_flags,
    }
    lua.lib.luaL_getmetatable(L, POBJECT)
    lua.lib.lua_setmetatable(L, -2)
    return 1

def py_function_result_to_lua(runtime, L, o):
     if runtime._unpack_returned_tuples and isinstance(o, tuple):
         push_lua_arguments(runtime, L, o)
         return len(o)
     return py_to_lua(runtime, L, o)

def call_python(runtime, L, py_obj):
    nargs = lua.lib.lua_gettop(L) - 1

    if not py_obj:
        raise TypeError("not a python object")

    f = lua.ffi.from_handle(py_obj[0].obj)

    if not nargs:
        lua.lib.lua_settop(L, 0)
        result = f()
    else:
        arg = py_from_lua(runtime, L, 2)

        if hasattr(f, '__func__') and hasattr(f, '__self__') and f.__self__ is arg:
            f = f.__func__

        args = [arg]

        for i in range(1, nargs):
            arg = py_from_lua(runtime, L, i+2)
            args.append(arg)

        lua.lib.lua_settop(L, 0)
        result = f(*args)

    return py_function_result_to_lua(runtime, L, result)

def unwrap_lua_object(L, n):
    if lua.lib.lua_isuserdata(L, n):
        return unpack_userdata(L, n)
    else:
        return unpack_wrapped_pyfunction(L, n)

@lua.ffi.def_extern('_py_object_call')
def py_object_call(L):
    py_obj = unwrap_lua_object(L, 1)
    if not py_obj:
        return lua.lib.luaL_argerror(L, 1, "not a python object")
    stored_state = None
    try:
        runtime = lua.ffi.from_handle(py_obj[0].runtime)
        if runtime._state is not L:
            stored_state = runtime._state
            runtime._state = L
        return call_python(runtime, L, py_obj)
    except:
        runtime.store_raised_exception(L, b'error during Python call')
        return lua.lib.lua_error(L)
    finally:
        if stored_state is not None:
            runtime._state = stored_state

@lua.ffi.def_extern('_py_object_str')
def py_object_str(L):
    py_obj = unwrap_lua_object(L, 1)
    if not py_obj:
        return lua.lib.luaL_argerror(L, 1, "not a python object")
    try:
        runtime = lua.ffi.from_handle(py_obj[0].runtime)
        s = six.text_type(lua.ffi.from_handle(py_obj[0].obj))
        s = s.encode(runtime._encoding or 'UTF-8')
        lua.lib.lua_pushlstring(L, s, len(s))
        return 1
    except:
        try:
            runtime.store_raised_exception(L, b'error during Python str() call')
        finally:
            return lua.lib.lua_error(L)


def getitem_for_lua(runtime, L, py_obj, key_n):
    return py_to_lua(runtime, L,
                     lua.ffi.from_handle(py_obj[0].obj)[ py_from_lua(runtime, L, key_n) ])

def setitem_for_lua(runtime, L, py_obj, key_n, value_n):
    lua.ffi.from_handle(py_obj[0].obj)[ py_from_lua(runtime, L, key_n) ] = py_from_lua(runtime, L, value_n)
    return 0

def getattr_for_lua(runtime, L, py_obj, key_n):
    obj = lua.ffi.from_handle(py_obj[0].obj)
    attr_name = py_from_lua(runtime, L, key_n)
    if runtime._attribute_getter is not None:
        value = runtime._attribute_getter(obj, attr_name)
        return py_to_lua(runtime, L, value)
    if runtime._attribute_filter is not None:
        attr_name = runtime._attribute_filter(obj, attr_name, False)
    if isinstance(attr_name, six.binary_type):
        attr_name = attr_name.decode(runtime._source_encoding)
    return py_to_lua(runtime, L, getattr(obj, attr_name))

def setattr_for_lua(runtime, L, py_obj, key_n, value_n):
    obj = lua.ffi.from_handle(py_obj[0].obj)
    attr_name = py_from_lua(runtime, L, key_n)
    attr_value = py_from_lua(runtime, L, value_n)
    if runtime._attribute_setter is not None:
        runtime._attribute_setter(obj, attr_name, attr_value)
    else:
        if runtime._attribute_filter is not None:
            attr_name = runtime._attribute_filter(obj, attr_name, True)
        if isinstance(attr_name, six.binary_type):
            attr_name = attr_name.decode(runtime._source_encoding)
        setattr(obj, attr_name, attr_value)
    return 0

@lua.ffi.def_extern('_py_object_getindex')
def py_object_getindex(L):
    py_obj = unwrap_lua_object(L, 1)
    if not py_obj:
        return lua.lib.luaL_argerror(L, 1, "not a python object")
    try:
        runtime = lua.ffi.from_handle(py_obj[0].runtime)
        if (py_obj[0].type_flags & OBJ_AS_INDEX) and not runtime._attribute_getter:
            return getitem_for_lua(runtime, L, py_obj, 2)
        else:
            return getattr_for_lua(runtime, L, py_obj, 2)
    except:
        runtime.store_raised_exception(L, b'error reading Python attribute/item')
        return lua.lib.lua_error(L)

@lua.ffi.def_extern('_py_object_setindex')
def py_object_setindex(L):
    py_obj = unwrap_lua_object(L, 1)
    if not py_obj:
        return lua.lib.luaL_argerror(L, 1, "not a python object")
    try:
        runtime = lua.ffi.from_handle(py_obj[0].runtime)
        if (py_obj.type_flags & OBJ_AS_INDEX) and not runtime._attribute_setter:
            return setitem_for_lua(runtime, L, py_obj, 2, 3)
        else:
            return setattr_for_lua(runtime, L, py_obj, 2, 3)
    except:
        runtime.store_raised_exception(L, b'error writing Python attribute/item')
        return lua.lib.lua_error(L)

@lua.ffi.def_extern('_py_object_gc')
def py_object_gc(L):
    if not lua.lib.lua_isuserdata(L, 1):
        return 0
    py_obj = unpack_userdata(L, 1)
    runtime = lua.ffi.from_handle(py_obj[0].runtime)
    runtime._pyrefs_in_lua.remove(py_obj[0].obj)
    runtime._rtrefs_in_lua.remove(py_obj[0].runtime)
    return 0


def unpack_single_python_argument_or_jump(L):
    if lua.lib.lua_gettop(L) > 1:
        lua.lib.luaL_argerror(L, 2, "invalid arguments")
    py_obj = unwrap_lua_object(L, 1)
    if not py_obj:
        lua.lib.luaL_argerror(L, 1, "not a python object")
    return py_obj

def py_wrap_object_protocol(L, type_flags):
    py_obj = unpack_single_python_argument_or_jump(L)
    try:
        runtime = lua.ffi.from_handle(py_obj[0].runtime)
        return py_to_lua_custom(runtime, L, lua.ffi.from_handle(py_obj[0].obj), type_flags)
    except:
        try:
            runtime.store_raised_exception(L, b'error during type adaptation')
        finally:
            return lua.lib.lua_error(L)

@lua.ffi.def_extern('_py_as_attrgetter')
def py_as_attrgetter(L):
    return py_wrap_object_protocol(L, 0)

@lua.ffi.def_extern('_py_as_itemgetter')
def py_as_itemgetter(L):
    return py_wrap_object_protocol(L, OBJ_AS_INDEX)

@lua.ffi.def_extern('_py_as_function')
def py_as_function(L):
    py_obj = unpack_single_python_argument_or_jump(L)
    lua.lib.lua_pushcclosure(L, lua.lib._py_asfunc_call, 1)
    return 1

@lua.ffi.def_extern('_py_iter')
def py_iter(L):
    py_obj = unpack_single_python_argument_or_jump(L)
    try:
        runtime = lua.ffi.from_handle(py_obj[0].runtime)
        obj = iter(lua.ffi.from_handle(py_obj[0].obj))
        return py_push_iterator(runtime, L, obj, 0, 0)
    except:
        try:
            runtime.store_raised_exception(L, b'error creating an iterator')
        finally:
            return lua.lib.lua_error(L)

@lua.ffi.def_extern('_py_iterex')
def py_iterex(L):
    py_obj = unpack_single_python_argument_or_jump(L)
    try:
        runtime = lua.ffi.from_handle(py_obj[0].runtime)
        obj = iter(lua.ffi.from_handle(py_obj[0].obj))
        return py_push_iterator(runtime, L, obj, OBJ_UNPACK_TUPLE, 0)
    except:
        try:
            runtime.store_raised_exception(L, b'error creating an iterator')
        finally:
            return lua.lib.lua_error(L)

@lua.ffi.def_extern('_py_enumerate')
def py_enumerate(L):
    if lua.lib.lua_gettop(L) > 2:
        lua.lib.luaL_argerror(L, 3, "invalid arguments")
    py_obj = unwrap_lua_object(L, 1)
    if not py_obj:
        lua.lib.luaL_argerror(L, 1, "not a python object")
    start = lua.lib.lua_tointeger(L, -1) if lua.lib.lua_gettop(L) == 2 else 0
    try:
        runtime = lua.ffi.from_handle(py_obj[0].runtime)
        obj = iter(lua.ffi.from_handle(py_obj[0].obj))
        return py_push_iterator(runtime, L, obj, OBJ_ENUMERATOR, start - 1)
    except:
        try:
            runtime.store_raised_exception(L, b'error creating an iterator with enumerate()')
        finally:
            return lua.lib.lua_error(L)

def py_push_iterator(runtime, L, iterator, type_flags, initial_value):
    old_top = lua.lib.lua_gettop(L)
    lua.lib.lua_pushcfunction(L, lua.lib._py_iter_next)
    if runtime._unpack_returned_tuples:
        type_flags |= OBJ_UNPACK_TUPLE
    if py_to_lua_custom(runtime, L, iterator, type_flags) < 1:
        lua.lib.lua_settop(L, old_top)
        return lua.lib.lua_error(L)
    if type_flags & OBJ_ENUMERATOR:
        lua.lib.lua_pushinteger(L, initial_value)
    else:
        lua.lib.lua_pushnil(L)
    return 3

@lua.ffi.def_extern('_py_iter_next')
def py_iter_next(L):
    py_iter = unwrap_lua_object(L, 1)
    if not py_iter:
        return lua.lib.luaL_argerror(L, 1, "not a python object")
    try:
        runtime = lua.ffi.from_handle(py_iter[0].runtime)
        try:
            obj = six.next(lua.ffi.from_handle(py_iter[0].obj))
        except StopIteration:
            lua.lib.lua_pushnil(L)
            return 1

        allow_nil = False
        if py_iter.type_flags & OBJ_ENUMERATOR:
            lua.lib.lua_pushinteger(L, lua.lib.lua_tointeger(L, -1) + 1)
            allow_nil = True
        if (py_iter.type_flags & OBJ_UNPACK_TUPLE) and isinstance(obj, tuple):
            push_lua_arguments(runtime, L, obj, first_may_be_nil=allow_nil)
            result = len(obj)
        else:
            result = py_to_lua(runtime, L, obj, wrap_none=not allow_nil)
            if result < 1:
                return lua.lib.lua_error(L)
        if py_iter.type_flags & OBJ_ENUMERATOR:
            result += 1
        return result
    except:
        try:
            runtime.store_raised_exception(L, b'error while calling next(iterator)')
        finally:
            return lua.lib.lua_error(L)


__all__ = ('LuaRuntime', 'LuaError', 'LuaSyntaxError',
           'as_itemgetter', 'as_attrgetter', 'lua_type',
           'unpacks_lua_table', 'unpacks_lua_table_method',
           'lua')
