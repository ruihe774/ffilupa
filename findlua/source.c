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

static int _arith_client(lua_State *L){
    const int op = luaL_checkinteger(L, 1);
    lua_arith(L, op);
    return 1;
}

static lua_CFunction _get_arith_client(void){
    return _arith_client;
}

static int _compare_client(lua_State *L){
    const int op = luaL_checkinteger(L, 1);
    lua_pushboolean(L, lua_compare(L, 2, 3, op));
    return 1;
}

static lua_CFunction _get_compare_client(void){
    return _compare_client;
}

static int _index_client(lua_State *L){
    const int op = luaL_checkinteger(L, 1);
    switch(op){
        case 0:
            lua_len(L, -1);
            return 1;
        case 1:
            lua_gettable(L, -2);
            return 1;
        case 2:
            lua_settable(L, -3);
            return 0;
        default:
            luaL_error(L, "unexpected op");
            return 0;
    }
}

static lua_CFunction _get_index_client(void){
    return _index_client;
}
