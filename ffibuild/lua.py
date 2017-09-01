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
    sources=('lua/lapi.c', 'lua/lcode.c', 'lua/lctype.c', 'lua/ldebug.c', 'lua/ldo.c', 'lua/ldump.c', 'lua/lfunc.c', 'lua/lgc.c', 'lua/llex.c', 'lua/lmem.c', 'lua/lobject.c', 'lua/lopcodes.c', 'lua/lparser.c', 'lua/lstate.c', 'lua/lstring.c', 'lua/ltable.c', 'lua/ltm.c', 'lua/lundump.c', 'lua/lvm.c', 'lua/lzio.c', 'lua/ltests.c', 'lua/lauxlib.c', 'lua/lbaselib.c', 'lua/ldblib.c', 'lua/liolib.c', 'lua/lmathlib.c', 'lua/loslib.c', 'lua/ltablib.c', 'lua/lstrlib.c', 'lua/lutf8lib.c', 'lua/lbitlib.c', 'lua/loadlib.c', 'lua/lcorolib.c', 'lua/linit.c'),
    include_dirs=('lua', 'c'),
    depends=['c/callback.c', 'c/lua_cdef.h'],
)
ffibuilder.cdef(readfile('c/lua_cdef.h'))
