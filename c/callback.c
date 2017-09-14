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
