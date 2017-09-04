from __future__ import absolute_import, unicode_literals
import cffi


def readfile(pathname):
    with open(pathname) as f:
        return f.read()

ffibuilder = cffi.FFI()
ffibuilder.set_source(
    'ffilupa.lua',
    """\
#include "lua.h"
#include "lstate.h"
#include "lauxlib.h"
#include "lualib.h"
#include "callback.c"
typedef struct{
    void* _runtime;
    void* _obj;
    void* _origin_obj;
    int _index_protocol;
}_py_handle;
""",
    sources=['lua/src/lapi.c', 'lua/src/lcode.c', 'lua/src/lctype.c', 'lua/src/ldebug.c', 'lua/src/ldo.c', 'lua/src/ldump.c', 'lua/src/lfunc.c', 'lua/src/lgc.c', 'lua/src/llex.c', 'lua/src/lmem.c', 'lua/src/lobject.c', 'lua/src/lopcodes.c', 'lua/src/lparser.c', 'lua/src/lstate.c', 'lua/src/lstring.c', 'lua/src/ltable.c', 'lua/src/ltm.c', 'lua/src/lundump.c', 'lua/src/lvm.c', 'lua/src/lzio.c', 'lua/src/lauxlib.c', 'lua/src/lbaselib.c', 'lua/src/lbitlib.c', 'lua/src/lcorolib.c', 'lua/src/ldblib.c', 'lua/src/liolib.c', 'lua/src/lmathlib.c', 'lua/src/loslib.c', 'lua/src/lstrlib.c', 'lua/src/ltablib.c', 'lua/src/lutf8lib.c', 'lua/src/loadlib.c', 'lua/src/linit.c'],
    include_dirs=['lua/src', 'c'],
    depends=['c/callback.c', 'c/lua_cdef.h'],
)
ffibuilder.cdef(readfile('c/lua_cdef.h'))