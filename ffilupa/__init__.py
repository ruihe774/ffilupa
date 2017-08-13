from threading import RLock
import six
from . import lua


class LuaError(Exception):
    """Base class for errors in the Lua runtime.
    """


class LuaSyntaxError(LuaError):
    """Syntax error in Lua code.
    """


class LuaRuntime:
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

      >>> from lupa import LuaRuntime
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
        self._pyrefs_in_lua = {}
        self._encoding = encoding
        self._source_encoding = source_encoding or self._encoding or b'UTF-8'
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
        # TODO: enable it
        # self.init_python_lib(register_eval, register_builtins)
        lua.lib.lua_settop(L, 0)
        lua.lib.lua_atpanic(L, lua.ffi.cast('lua_CFunction', 1))

    def __del__(self):
        if self._state is not lua.ffi.NULL:
            lua.lib.lua_close(self._state)
            self._state = lua.ffi.NULL

    def eval(self, lua_code, *args):
        """Evaluate a Lua expression passed in a string.
        """
        assert self._state is not lua.ffi.NULL
        if isinstance(lua_code, six.text_type):
            lua_code = lua_code.encode(self._source_encoding)
        return run_lua(self, b'return ' + lua_code, args)

    def execute(self, lua_code, *args):
        """Execute a Lua program passed in a string.
        """
        assert self._state is not lua.ffi.NULL
        if isinstance(lua_code, six.text_type):
            lua_code = lua_code.encode(self._source_encoding)
        return run_lua(self, lua_code, args)


def lock_runtime(runtime):
    runtime._lock.acquire()


def unlock_runtime(runtime):
    runtime._lock.release()


def build_lua_error_message(runtime, L, err_message, n):
    size = lua.ffi.new('size_t*')
    s = lua.lib.lua_tolstring(L, n, size)
    size = size[0]
    if runtime._encoding is not None:
        try:
            py_ustring = lua.ffi.string(s[0:size]).decode(runtime._encoding)
        except UnicodeDecodeError:
            py_ustring = lua.ffi.string(s[0:size]).decode('ISO-8859-1')
    else:
        py_ustring = lua.ffi.string(s[0:size]).decode('ISO-8859-1')
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
    """if result_status:
        if isinstance(results, BaseException):
            runtime.reraise_on_exception()
        raise_lua_error(runtime, L, result_status)"""
    return results


def push_lua_arguments(runtime, L, args, first_may_be_nil=True):
    if args:
        olds = lua.lib.lua_gettop(L)
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


def py_from_lua(runtime, L, n):
    """
    Convert a Lua object to a Python object by either mapping, wrapping
    or unwrapping it.
    """
    if lua.lib.lua_isnil(L, n):
        return None
    elif lua.lib.lua_isnumber(L, n):
        return lua.lib.lua_tonumber(L, n)
    elif lua.lib.lua_isinteger(L, n):
        return lua.lib.lua_tointeger(L, n)
    elif lua.lib.lua_isstring(L, n):
        size = lua.ffi.new('size_t*')
        s = lua.lib.lua_tolstring(L, n, size)
        size = size[0]
        if runtime._encoding is not None:
            return lua.ffi.string(s[0:size]).decode(runtime._encoding)
        else:
            return lua.ffi.string(s[0:size])
    elif lua.lib.lua_isboolean(L, n):
        return bool(lua.lib.lua_toboolean(L, n))
    """elif lua_type == lua.lib.LUA_TUSERDATA:
        py_obj = unpack_userdata(L, n)
        if py_obj:
            return <object>py_obj.obj
    elif lua_type == lua.lib.LUA_TTABLE:
        return new_lua_table(runtime, L, n)
    elif lua_type == lua.lib.LUA_TTHREAD:
        return new_lua_thread_or_function(runtime, L, n)
    elif lua_type == lua.lib.LUA_TFUNCTION:
        py_obj = unpack_wrapped_pyfunction(L, n)
        if py_obj:
            return <object>py_obj.obj
        return new_lua_function(runtime, L, n)
    return new_lua_object(runtime, L, n)"""


def py_to_lua(runtime, L, o, wrap_none=False):
    pushed_values_count = 0
    type_flags = 0

    if o is None:
        if wrap_none:
            lua.lib.lua_pushlstring(L, b"Py_None", 7)
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
    elif isinstance(o, six.integer_types[0]) or isinstance(o, six.integer_types[-1]):
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
    """elif isinstance(o, _LuaObject):
        if o._runtime is not runtime:
            raise LuaError("cannot mix objects from different Lua runtimes")
        lua.lib.lua_rawgeti(L, lua.lib.LUA_REGISTRYINDEX, o._ref)
        pushed_values_count = 1"""
    """else:
        if isinstance(o, _PyProtocolWrapper):
            type_flags = (<_PyProtocolWrapper>o)._type_flags
            o = (<_PyProtocolWrapper>o)._obj
        else:
            # prefer __getitem__ over __getattr__ by default
            type_flags = OBJ_AS_INDEX if hasattr(o, '__getitem__') else 0
        pushed_values_count = py_to_lua_custom(runtime, L, o, type_flags)"""
    return pushed_values_count

def push_encoded_unicode_string(runtime, L, ustring):
    bytes_string = ustring.encode(runtime._encoding)
    lua.lib.lua_pushlstring(L, bytes_string, len(bytes_string))

"""cdef bint py_to_lua_custom(LuaRuntime runtime, lua_State *L, object o, int type_flags):
    cdef py_object *py_obj = <py_object*> lua.lib.lua_newuserdata(L, sizeof(py_object))
    if not py_obj:
        return 0 # values pushed

    # originally, we just used:
    #cpython.ref.Py_INCREF(o)
    # now, we store an owned reference in "runtime._pyrefs_in_lua" to keep it visible to Python
    # and a borrowed reference in "py_obj.obj" for access from Lua
    obj_id = <object><uintptr_t><PyObject*>(o)
    if obj_id in runtime._pyrefs_in_lua:
        runtime._pyrefs_in_lua[obj_id].append(o)
    else:
        runtime._pyrefs_in_lua[obj_id] = [o]

    py_obj.obj = <PyObject*>o
    py_obj.runtime = <PyObject*>runtime
    py_obj.type_flags = type_flags
    lua.lib.luaL_getmetatable(L, POBJECT)
    lua.lib.lua_setmetatable(L, -2)
    return 1 # values pushed"""
