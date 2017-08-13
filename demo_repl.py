import sys
import readline
import ffilupa._lua as lua


L = lua.lib.luaL_newstate()
lua.lib.luaL_openlibs(L)

try:
    while True:
        buff = input('>>> ').encode()
        error = bool(lua.lib.luaL_loadbuffer(L, buff, len(buff), b"line")) or \
                bool(lua.lib.lua_pcall(L, 0, 0, 0))
        if error:
            print(lua.ffi.string(lua.lib.lua_tostring(L, -1)).decode(), file=sys.stderr)
            lua.lib.lua_pop(L, 1)
except EOFError:
    lua.lib.lua_close(L)
