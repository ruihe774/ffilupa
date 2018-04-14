#include <lua.h>
#include <lauxlib.h>

void _ffilupa_init(lua_State*);

void ffilupa_init(lua_State* L){
    luaL_checkversion(L);
    _ffilupa_init(L);
}
