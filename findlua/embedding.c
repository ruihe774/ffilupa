#include <lua.h>
#include <lauxlib.h>

void _ffilupa_init(lua_State*, const char*);

void ffilupa_init(lua_State* L){
    const char *path;
    luaL_checkversion(L);
    path = luaL_checkstring(L, 1);
    _ffilupa_init(L, path);
}
