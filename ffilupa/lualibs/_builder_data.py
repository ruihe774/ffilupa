import os
import sys
from pathlib import Path
from typing import Optional, Tuple, Collection

from packaging.markers import Marker
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from ._build_options import BuildOptions


__all__ = ('CAPI', 'CTypeDef', 'CFunctionTypeDef', 'CConstant', 'CFunction', 'CHelper', 'generate_cdef_and_source', 'lua_apis',
           'bundle_lua_buildoptions')


class CAPI:
    def __init__(self, require: Optional[str] = None) -> None:
        if not require:
            self.spec = None
            self.marker = None
        else:
            sm = require.split(";")
            assert len(sm) <= 2
            self.spec = SpecifierSet(sm[0])
            if len(sm) == 2:
                self.marker = Marker(sm[1])
            else:
                self.marker = None

    def to_cdef(self) -> Optional[str]:
        raise NotImplementedError

    def to_source(self) -> Optional[str]:
        raise NotImplementedError


class CTypeDef(CAPI):
    def __init__(self, origin: str, alias: str, require: Optional[str] = None) -> None:
        super().__init__(require)
        self.origin = origin
        self.alias = alias

    def to_cdef(self) -> Optional[str]:
        return f"typedef {self.origin} {self.alias};"

    def to_source(self) -> Optional[str]:
        return None


class CFunctionTypeDef(CAPI):
    def __init__(
        self,
        alias: str,
        arg_types: Tuple[str, ...],
        return_type: str,
        require: Optional[str] = None,
    ) -> None:
        super().__init__(require)
        self.alias = alias
        self.arg_types = arg_types
        self.return_type = return_type

    def to_cdef(self) -> Optional[str]:
        return (
            f"typedef {self.return_type} (*{self.alias})({','.join(self.arg_types)});"
        )

    def to_source(self) -> Optional[str]:
        return None


class CConstant(CAPI):
    def __init__(self, ident: str, type: str, require: Optional[str] = None) -> None:
        super().__init__(require)
        self.ident = ident
        self.type = type

    def to_cdef(self) -> Optional[str]:
        if self.type.endswith("[]"):
            return f"extern const {self.type[:-2]} ({self.ident})[];"
        else:
            return f"extern const {self.type} ({self.ident});"

    def to_source(self) -> Optional[str]:
        return None


class CFunction(CAPI):
    def __init__(
        self,
        ident: str,
        arg_types: Tuple[str, ...],
        return_type: str,
        require: Optional[str] = None,
    ) -> None:
        super().__init__(require)
        self.ident = ident
        self.arg_types = arg_types
        self.return_type = return_type

    def to_cdef(self) -> Optional[str]:
        return f"{self.return_type} ({self.ident})({','.join(self.arg_types)});"

    def to_source(self) -> Optional[str]:
        return None


class CHelper(CFunction):
    def __init__(
        self,
        ident: str,
        arg_types: Tuple[str, ...],
        return_type: str,
        impl: str,
        require: Optional[str] = None,
    ) -> None:
        super().__init__(ident, arg_types, return_type, require)
        self.impl = impl

    def to_source(self) -> Optional[str]:
        return self.impl


def generate_cdef_and_source(
    version: Version, apis: Collection[CAPI]
) -> Tuple[str, str]:
    cdef_chunks = []
    source_chunks = [
        """\
#include "lua.h"
#include "lauxlib.h"
#include "lualib.h"
"""
    ]
    for api in apis:
        if (not api.spec or version in api.spec) and (not api.marker or api.marker.evaluate()):
            cdef = api.to_cdef()
            if cdef:
                cdef_chunks.append(cdef)
            source = api.to_source()
            if source:
                source_chunks.append(source)
    return "".join(cdef_chunks), "".join(source_chunks)


lua_apis = (
    CConstant("LUA_RELEASE", "char[]"),
    CConstant("LUA_MULTRET", "int"),
    CConstant("LUA_REGISTRYINDEX", "int"),
    CFunction("lua_upvalueindex", ("int",), "int"),
    CConstant("LUA_YIELD", "int"),
    CConstant("LUA_ERRRUN", "int"),
    CConstant("LUA_ERRSYNTAX", "int"),
    CConstant("LUA_ERRMEM", "int"),
    CConstant("LUA_ERRGCMM", "int"),
    CConstant("LUA_ERRERR", "int"),
    CConstant("LUA_ERRFILE", "int"),
    CTypeDef("struct lua_State", "lua_State"),
    CConstant("LUA_TNONE", "int"),
    CConstant("LUA_TNIL", "int"),
    CConstant("LUA_TBOOLEAN", "int"),
    CConstant("LUA_TLIGHTUSERDATA", "int"),
    CConstant("LUA_TNUMBER", "int"),
    CConstant("LUA_TSTRING", "int"),
    CConstant("LUA_TTABLE", "int"),
    CConstant("LUA_TFUNCTION", "int"),
    CConstant("LUA_TUSERDATA", "int"),
    CConstant("LUA_TTHREAD", "int"),
    CTypeDef("float...", "lua_Number"),
    CTypeDef("int...", "lua_Integer"),
    CFunctionTypeDef("lua_CFunction", ("lua_State*",), "int"),
    CFunction("lua_close", ("lua_State*",), "void"),
    CFunction("lua_newthread", ("lua_State*",), "lua_State*"),
    CFunction("lua_absindex", ("lua_State*", "int"), "int"),
    CFunction("lua_gettop", ("lua_State*",), "int"),
    CFunction("lua_settop", ("lua_State*", "int"), "void"),
    CFunction("lua_pushvalue", ("lua_State*", "int"), "void"),
    CFunction("lua_xmove", ("lua_State*", "lua_State*", "int"), "void"),
    CFunction("lua_type", ("lua_State*", "int"), "int"),
    CFunction("lua_isinteger", ("lua_State*", "int"), "int"),
    CFunction("lua_tointeger", ("lua_State*", "int"), "lua_Integer"),
    CFunction("lua_tonumber", ("lua_State*", "int"), "lua_Number"),
    CFunction("lua_toboolean", ("lua_State*", "int"), "int"),
    CFunction("lua_tolstring", ("lua_State*", "int", "size_t*"), "const char*"),
    CFunction("lua_rawlen", ("lua_State*", "int"), "size_t"),
    CFunction("lua_tothread", ("lua_State*", "int"), "lua_State*"),
    CFunction("lua_topointer", ("lua_State*", "int"), "const void*"),
    CConstant("LUA_OPADD", "int"),
    CConstant("LUA_OPSUB", "int"),
    CConstant("LUA_OPMUL", "int"),
    CConstant("LUA_OPMOD", "int"),
    CConstant("LUA_OPPOW", "int"),
    CConstant("LUA_OPDIV", "int"),
    CConstant("LUA_OPIDIV", "int"),
    CConstant("LUA_OPBAND", "int"),
    CConstant("LUA_OPBOR", "int"),
    CConstant("LUA_OPBXOR", "int"),
    CConstant("LUA_OPSHL", "int"),
    CConstant("LUA_OPSHR", "int"),
    CConstant("LUA_OPUNM", "int"),
    CConstant("LUA_OPBNOT", "int"),
    CHelper(
        "ffilupa_get_arith_f",
        (),
        "lua_CFunction",
        # language=C
        """
static int ffilupa_arith_f(lua_State* L) {
    const int op = (int)luaL_checkinteger(L, 1);
    lua_arith(L, op);
    return 1;
}
static lua_CFunction ffilupa_get_arith_f(void) {
    return ffilupa_arith_f;
}
""",
    ),
    CConstant("LUA_OPEQ", "int"),
    CConstant("LUA_OPLT", "int"),
    CConstant("LUA_OPLE", "int"),
    CFunction("lua_rawequal", ("lua_State*", "int", "int"), "int"),
    CHelper(
        "ffilupa_get_compare_f",
        (),
        "lua_CFunction",
        # language=C
        """
static int ffilupa_compare_f(lua_State* L) {
    const int op = (int)luaL_checkinteger(L, 1);
    lua_pushboolean(L, lua_compare(L, 2, 3, op));
    return 1;
}
static lua_CFunction ffilupa_get_compare_f(void) {
    return ffilupa_compare_f;
}
""",
    ),
    CFunction("lua_pushnil", ("lua_State*",), "void"),
    CFunction("lua_pushnumber", ("lua_State*", "lua_Number"), "void"),
    CFunction("lua_pushinteger", ("lua_State*", "lua_Integer"), "void"),
    CFunction(
        "lua_pushlstring", ("lua_State*", "const char*", "size_t"), "const char*"
    ),
    CFunction("lua_pushcclosure", ("lua_State*", "lua_CFunction", "int"), "void"),
    CFunction("lua_pushboolean", ("lua_State*", "int"), "void"),
    CFunction("lua_getglobal", ("lua_State*", "const char*"), "int"),
    CFunction("lua_rawget", ("lua_State*", "int"), "int"),
    CFunction("lua_rawgeti", ("lua_State*", "int", "lua_Integer"), "int"),
    CHelper(
        "ffilupa_rawgetlf",
        ("lua_State*", "int", "const char*", "size_t"),
        "int",
        # language=C
        """
static int ffilupa_rawgetlf(lua_State* L, int index, const char* k, size_t len) {
    lua_pushlstring(L, k, len);
    return lua_rawget(L, index);
}
""",
    ),
    CFunction("lua_createtable", ("lua_State*", "int", "int"), "void"),
    CFunction("lua_newuserdata", ("lua_State*", "size_t"), "void*"),
    CFunction("lua_setglobal", ("lua_State*", "const char*"), "void"),
    CFunction("lua_rawset", ("lua_State*", "int"), "void"),
    CFunction("lua_rawseti", ("lua_State*", "int", "lua_Integer"), "void"),
    CHelper(
        "ffilupa_rawsetlf",
        ("lua_State*", "int", "const char*", "size_t"),
        "void",
        # language=C
        """
static void ffilupa_rawsetlf(lua_State* L, int index, const char* k, size_t len) {
    const int absindex = lua_absindex(L, index);
    lua_pushlstring(L, k, len);
    lua_insert(L, -2);
    lua_rawset(L, absindex);
}
""",
    ),
    CHelper(
        "ffilupa_get_index_f",
        (),
        "lua_CFunction",
        # language=C
        """
static int ffilupa_index_f(lua_State* L) {
    const int op = (int)luaL_checkinteger(L, 1);
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
static lua_CFunction ffilupa_get_index_f(void) {
    return ffilupa_index_f;
}
""",
    ),
    CFunction("lua_pcall", ("lua_State*", "int", "int", "int"), "int"),
    CFunction("lua_resume", ("lua_State*", "lua_State*", "int"), "int"),
    CFunction("lua_status", ("lua_State*",), "int"),
    CConstant("LUA_GCSTOP", "int"),
    CConstant("LUA_GCRESTART", "int"),
    CConstant("LUA_GCCOLLECT", "int"),
    CConstant("LUA_GCCOUNT", "int"),
    CConstant("LUA_GCCOUNTB", "int"),
    CConstant("LUA_GCSTEP", "int"),
    CConstant("LUA_GCSETPAUSE", "int"),
    CConstant("LUA_GCSETSTEPMUL", "int"),
    CConstant("LUA_GCISRUNNING", "int"),
    CFunction("lua_gc", ("lua_State*", "int", "int"), "int"),
    CFunction("lua_pop", ("lua_State*", "int"), "void"),
    CFunction("lua_pushcfunction", ("lua_State*", "lua_CFunction"), "void"),
    CFunction("lua_pushglobaltable", ("lua_State*",), "void"),
    CFunction("luaL_newmetatable", ("lua_State*", "const char*"), "int"),
    CFunction("luaL_setmetatable", ("lua_State*", "const char*"), "void"),
    CFunction("luaL_testudata", ("lua_State*", "int", "const char*"), "void*"),
    CFunction("luaL_ref", ("lua_State*", "int"), "int"),
    CFunction("luaL_unref", ("lua_State*", "int", "int"), "void"),
    CFunction("luaL_loadfile", ("lua_State*", "const char*"), "int"),
    CFunction("luaL_newstate", (), "lua_State*"),
    CFunction(
        "luaL_loadbuffer", ("lua_State*", "const char*", "size_t", "const char*"), "int"
    ),
    CFunction("luaL_openlibs", ("lua_State*",), "void"),
)



lua_sources = (
    "lapi.c",
    "lcode.c",
    "lctype.c",
    "ldebug.c",
    "ldo.c",
    "ldump.c",
    "lfunc.c",
    "lgc.c",
    "llex.c",
    "lmem.c",
    "lobject.c",
    "lopcodes.c",
    "lparser.c",
    "lstate.c",
    "lstring.c",
    "ltable.c",
    "ltm.c",
    "lundump.c",
    "lvm.c",
    "lzio.c",
    "lauxlib.c",
    "lbaselib.c",
    "lbitlib.c",
    "lcorolib.c",
    "ldblib.c",
    "liolib.c",
    "lmathlib.c",
    "loslib.c",
    "lstrlib.c",
    "ltablib.c",
    "lutf8lib.c",
    "loadlib.c",
    "linit.c",
)
bundle_lua_path = Path("lua")


macros = []
libraries = []
if os.name == "posix":
    macros.append(("LUA_USE_POSIX", None))
if sys.platform.startswith("linux") or sys.platform.startswith("freebsd"):
    macros.append(("LUA_USE_DLOPEN", None))
    libraries.append("dl")
if sys.platform.startswith("darwin"):
    macros.append(("LUA_USE_DLOPEN", None))
macros = tuple(macros)
libraries = tuple(libraries)


bundle_lua_buildoptions = BuildOptions(
    version=Version("5.3.5"),
    sources=tuple((bundle_lua_path / "src" / p).__fspath__() for p in lua_sources),
    include_dirs=((bundle_lua_path / "src").__fspath__(),),
    define_macros=macros,
    libraries=libraries,
)
