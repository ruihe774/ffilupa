#include "lua.h"
#include "lauxlib.h"
#include "lualib.h"

static int _caller_server(lua_State*);

static int _caller_client(lua_State *L){
    const int result = _caller_server(L);
    if(result == -1)
        return lua_error(L);
    else
        return result;
}

static lua_CFunction _get_caller_client(void){
    return _caller_client;
}
