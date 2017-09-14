from __future__ import absolute_import
import cffi


def readfile(pathname):
    with open(pathname) as f:
        return f.read()

C_CALLBACKS = 128

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
    int _index_protocol;
}_py_handle;
""" + '\n'.join('_PY_CALLBACK({})'.format(i) for i in range(C_CALLBACKS)) + '\n#define _PY_C_CALLBACKS {}'.format(C_CALLBACKS),
    sources=['lua/src/lapi.c', 'lua/src/lcode.c', 'lua/src/lctype.c', 'lua/src/ldebug.c', 'lua/src/ldo.c', 'lua/src/ldump.c', 'lua/src/lfunc.c', 'lua/src/lgc.c', 'lua/src/llex.c', 'lua/src/lmem.c', 'lua/src/lobject.c', 'lua/src/lopcodes.c', 'lua/src/lparser.c', 'lua/src/lstate.c', 'lua/src/lstring.c', 'lua/src/ltable.c', 'lua/src/ltm.c', 'lua/src/lundump.c', 'lua/src/lvm.c', 'lua/src/lzio.c', 'lua/src/lauxlib.c', 'lua/src/lbaselib.c', 'lua/src/lbitlib.c', 'lua/src/lcorolib.c', 'lua/src/ldblib.c', 'lua/src/liolib.c', 'lua/src/lmathlib.c', 'lua/src/loslib.c', 'lua/src/lstrlib.c', 'lua/src/ltablib.c', 'lua/src/lutf8lib.c', 'lua/src/loadlib.c', 'lua/src/linit.c'],
    include_dirs=['lua/src', 'c'],
    depends=['c/callback.c', 'c/lua_cdef.h'],
)
ffibuilder.cdef(
    readfile('c/lua_cdef.h') +
    '\n'.join(
        """\
extern "Python" int _py_callback_server_{id}(lua_State*);
lua_CFunction _py_callback_client_get_{id}(void);
""".format(id=i) for i in range(C_CALLBACKS)
    ) + 'extern const int _PY_C_CALLBACKS;'
)
