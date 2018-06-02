from {libname} import ffi

@ffi.def_extern()
def _ffilupa_init(L, path):
    import os
    path = os.fsdecode(ffi.string(path))
    import sys
    sys.path.insert(0, path)
    from ffilupa.lualibs import get_lualibs
    from ffilupa.runtime import LuaRuntime
    global runtime
    libname = '{libname}'[19:]
    runtime = LuaRuntime(lualib=get_lualibs().select_name(libname), lua_state=L)
