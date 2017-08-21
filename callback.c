#include "lua.h"


#define _PY_CALLBACK_CLIENT(name) static int (_py_callback_client_##name) (lua_State *L) { \
    int result = (_py_callback_server_##name)(L); \
    if(result == -1) \
        return lua_error(L); \
    return result; \
}

#define _PY_CALLBACK_CLIENT_GETTER(name) static lua_CFunction (_py_callback_client_get_##name) (void) { \
    return (_py_callback_client_##name); \
}

#define _PY_CALLBACK(name) static int (_py_callback_server_##name) (lua_State*); \
_PY_CALLBACK_CLIENT(name) \
_PY_CALLBACK_CLIENT_GETTER(name)


_PY_CALLBACK(object_call)
_PY_CALLBACK(object_str)
_PY_CALLBACK(object_getindex)
_PY_CALLBACK(object_setindex)
_PY_CALLBACK(object_gc)
_PY_CALLBACK(as_attrgetter)
_PY_CALLBACK(as_itemgetter)
_PY_CALLBACK(as_function)
_PY_CALLBACK(asfunc_call)
_PY_CALLBACK(iter)
_PY_CALLBACK(iterex)
_PY_CALLBACK(enumerate)
_PY_CALLBACK(iter_next)
