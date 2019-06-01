__all__ = ('cdef', 'source', 'bundle_lua_pkginfo',)


from ._pkginfo import PkgInfo
from packaging.version import Version
from pathlib import Path
import os
import sys


cdef = '''
/*
** $Id: lua.h,v 1.331 2016/05/30 15:53:28 roberto Exp $
** Lua - A Scripting Language
** Lua.org, PUC-Rio, Brazil (http://www.lua.org)
** See Copyright Notice at the end of this file
*/


extern const char LUA_VERSION_MAJOR[];		//VER: >=5.2
extern const char LUA_VERSION_MINOR[];		//VER: >=5.2
extern const int LUA_VERSION_NUM;
extern const char LUA_VERSION_RELEASE[];	//VER: >=5.2

extern const char LUA_VERSION[];
extern const char LUA_RELEASE[];
extern const char LUA_COPYRIGHT[];
extern const char LUA_AUTHORS[];


/* mark for precompiled code ('<esc>Lua') */
extern const char LUA_SIGNATURE[];

/* option for multiple returns in 'lua_pcall' and 'lua_call' */
extern const int LUA_MULTRET;


/*
** Pseudo-indices
** (-LUAI_MAXSTACK is the minimum valid index; we keep some free empty
** space after that to help overflow detection)
*/
extern const int LUA_REGISTRYINDEX;
int lua_upvalueindex (int i);


/* thread status */
extern const int LUA_OK;		//VER: >=5.2
extern const int LUA_YIELD;
extern const int LUA_ERRRUN;
extern const int LUA_ERRSYNTAX;
extern const int LUA_ERRMEM;
extern const int LUA_ERRGCMM;	//VER: >=5.2
extern const int LUA_ERRERR;


typedef struct lua_State lua_State;


/*
** basic types
*/
extern const int LUA_TNONE;

extern const int LUA_TNIL;
extern const int LUA_TBOOLEAN;
extern const int LUA_TLIGHTUSERDATA;
extern const int LUA_TNUMBER;
extern const int LUA_TSTRING;
extern const int LUA_TTABLE;
extern const int LUA_TFUNCTION;
extern const int LUA_TUSERDATA;
extern const int LUA_TTHREAD;

extern const int LUA_NUMTAGS;	//VER: >=5.2



/* minimum Lua stack available to a C function */
extern const int LUA_MINSTACK;


/* predefined values in the registry */
extern const int LUA_RIDX_MAINTHREAD;	//VER: >=5.2
extern const int LUA_RIDX_GLOBALS;		//VER: >=5.2
extern const int LUA_RIDX_LAST;			//VER: >=5.2


/* type of numbers in Lua */
typedef float... lua_Number;


/* type for integer functions */
typedef int... lua_Integer;

/* unsigned integer type */
typedef int... lua_Unsigned;	//VER: >=5.2

/* type for continuation-function contexts */
typedef int... lua_KContext;	//VER: >=5.3


/*
** Type for C functions registered with Lua
*/
typedef int (*lua_CFunction) (lua_State *L);

/*
** Type for continuation functions
*/
typedef int (*lua_KFunction) (lua_State *L, int status, lua_KContext ctx);	//VER: >=5.3


/*
** Type for functions that read/write blocks when loading/dumping Lua chunks
*/
typedef const char * (*lua_Reader) (lua_State *L, void *ud, size_t *sz);

typedef int (*lua_Writer) (lua_State *L, const void *p, size_t sz, void *ud);


/*
** Type for memory-allocation functions
*/
typedef void * (*lua_Alloc) (void *ud, void *ptr, size_t osize, size_t nsize);



/*
** state manipulation
*/
lua_State *(lua_newstate) (lua_Alloc f, void *ud);
void       (lua_close) (lua_State *L);
lua_State *(lua_newthread) (lua_State *L);

lua_CFunction (lua_atpanic) (lua_State *L, lua_CFunction panicf);


const lua_Number *(lua_version) (lua_State *L);	//VER: >=5.2


/*
** basic stack manipulation
*/
int   (lua_absindex) (lua_State *L, int idx);			//VER: >=5.2
int   (lua_gettop) (lua_State *L);
void  (lua_settop) (lua_State *L, int idx);
void  (lua_pushvalue) (lua_State *L, int idx);
void  (lua_rotate) (lua_State *L, int idx, int n);		//VER: >=5.3
void  (lua_copy) (lua_State *L, int fromidx, int toidx);	//VER: >=5.2
int   (lua_checkstack) (lua_State *L, int n);

void  (lua_xmove) (lua_State *from, lua_State *to, int n);


/*
** access functions (stack -> C)
*/

int             (lua_isnumber) (lua_State *L, int idx);
int             (lua_isstring) (lua_State *L, int idx);
int             (lua_iscfunction) (lua_State *L, int idx);
int             (lua_isinteger) (lua_State *L, int idx);	//VER: >=5.3
int             (lua_isuserdata) (lua_State *L, int idx);
int             (lua_type) (lua_State *L, int idx);
const char     *(lua_typename) (lua_State *L, int tp);

lua_Number      (lua_tonumberx) (lua_State *L, int idx, int *isnum);	//VER: >=5.2
lua_Integer     (lua_tointegerx) (lua_State *L, int idx, int *isnum);	//VER: >=5.2
int             (lua_toboolean) (lua_State *L, int idx);
const char     *(lua_tolstring) (lua_State *L, int idx, size_t *len);
size_t          (lua_rawlen) (lua_State *L, int idx);					//VER: >=5.2
lua_CFunction   (lua_tocfunction) (lua_State *L, int idx);
void	       *(lua_touserdata) (lua_State *L, int idx);
lua_State      *(lua_tothread) (lua_State *L, int idx);
const void     *(lua_topointer) (lua_State *L, int idx);


/*
** Comparison and arithmetic functions
*/

extern const int LUA_OPADD;		//VER: >=5.2
extern const int LUA_OPSUB;		//VER: >=5.2
extern const int LUA_OPMUL;		//VER: >=5.2
extern const int LUA_OPMOD;		//VER: >=5.2
extern const int LUA_OPPOW;		//VER: >=5.2
extern const int LUA_OPDIV;		//VER: >=5.2
extern const int LUA_OPIDIV;	//VER: >=5.3
extern const int LUA_OPBAND;	//VER: >=5.3
extern const int LUA_OPBOR;		//VER: >=5.3
extern const int LUA_OPBXOR;	//VER: >=5.3
extern const int LUA_OPSHL;		//VER: >=5.3
extern const int LUA_OPSHR;		//VER: >=5.3
extern const int LUA_OPUNM;		//VER: >=5.2
extern const int LUA_OPBNOT;	//VER: >=5.3

void  (lua_arith) (lua_State *L, int op);	//VER: >=5.2

extern const int LUA_OPEQ;		//VER: >=5.2
extern const int LUA_OPLT;		//VER: >=5.2
extern const int LUA_OPLE;		//VER: >=5.2

int   (lua_rawequal) (lua_State *L, int idx1, int idx2);
int   (lua_compare) (lua_State *L, int idx1, int idx2, int op);	//VER: >=5.2


/*
** push functions (C -> stack)
*/
void        (lua_pushnil) (lua_State *L);
void        (lua_pushnumber) (lua_State *L, lua_Number n);
void        (lua_pushinteger) (lua_State *L, lua_Integer n);
const char *(lua_pushlstring) (lua_State *L, const char *s, size_t len);	//VER: >=5.2
void (lua_pushlstring) (lua_State *L, const char *s, size_t len);			//VER: <5.2
const char *(lua_pushstring) (lua_State *L, const char *s);					//VER: >=5.2
void (lua_pushstring) (lua_State *L, const char *s);						//VER: <5.2
const char *(lua_pushfstring) (lua_State *L, const char *fmt, ...);
void  (lua_pushcclosure) (lua_State *L, lua_CFunction fn, int n);
void  (lua_pushboolean) (lua_State *L, int b);
void  (lua_pushlightuserdata) (lua_State *L, void *p);
int   (lua_pushthread) (lua_State *L);


/*
** get functions (Lua -> stack)
*/
int (lua_getglobal) (lua_State *L, const char *name);		//VER: >=5.3
void (lua_getglobal) (lua_State *L, const char *name);		//VER: <5.3
int (lua_gettable) (lua_State *L, int idx);					//VER: >=5.3
void (lua_gettable) (lua_State *L, int idx);				//VER: <5.3
int (lua_getfield) (lua_State *L, int idx, const char *k);	//VER: >=5.3
void (lua_getfield) (lua_State *L, int idx, const char *k);	//VER: <5.3
int (lua_geti) (lua_State *L, int idx, lua_Integer n);		//VER: >=5.3
int (lua_rawget) (lua_State *L, int idx);					//VER: >=5.3
void (lua_rawget) (lua_State *L, int idx);					//VER: <5.3
int (lua_rawgeti) (lua_State *L, int idx, lua_Integer n);	//VER: >=5.3
void (lua_rawgeti) (lua_State *L, int idx, lua_Integer n);	//VER: <5.3
int (lua_rawgetp) (lua_State *L, int idx, const void *p);	//VER: >=5.3
void (lua_rawgetp) (lua_State *L, int idx, const void *p);	//VER: <5.3,>=5.2

void  (lua_createtable) (lua_State *L, int narr, int nrec);
void *(lua_newuserdata) (lua_State *L, size_t sz);
int   (lua_getmetatable) (lua_State *L, int objindex);
int  (lua_getuservalue) (lua_State *L, int idx);			//VER: >=5.3
void  (lua_getuservalue) (lua_State *L, int idx);			//VER: <5.3,>=5.2


/*
** set functions (stack -> Lua)
*/
void  (lua_setglobal) (lua_State *L, const char *name);
void  (lua_settable) (lua_State *L, int idx);
void  (lua_setfield) (lua_State *L, int idx, const char *k);
void  (lua_seti) (lua_State *L, int idx, lua_Integer n);	//VER: >=5.3
void  (lua_rawset) (lua_State *L, int idx);
void  (lua_rawseti) (lua_State *L, int idx, lua_Integer n);
void  (lua_rawsetp) (lua_State *L, int idx, const void *p);	//VER: >=5.2
int   (lua_setmetatable) (lua_State *L, int objindex);
void  (lua_setuservalue) (lua_State *L, int idx);			//VER: >=5.2


/*
** 'load' and 'call' functions (load and run Lua code)
*/
void  (lua_callk) (lua_State *L, int nargs, int nresults,		//VER: >=5.3
                           lua_KContext ctx, lua_KFunction k);	//VER: >=5.3
void lua_call (lua_State *L, int nargs, int nresults);

int   (lua_pcallk) (lua_State *L, int nargs, int nresults, int errfunc,	//VER: >=5.3
                            lua_KContext ctx, lua_KFunction k);			//VER: >=5.3
int lua_pcall (lua_State *L, int nargs, int nresults, int msgh);

int   (lua_load) (lua_State *L, lua_Reader reader, void *dt,			//VER: >=5.2
                          const char *chunkname, const char *mode);		//VER: >=5.2

int   (lua_load) (lua_State *L, lua_Reader reader, void *dt,			//VER: <5.2
                          const char *chunkname);						//VER: <5.2

int (lua_dump) (lua_State *L, lua_Writer writer, void *data, int strip);	//VER: >=5.3
int (lua_dump) (lua_State *L, lua_Writer writer, void *data);				//VER: <5.3


/*
** coroutine functions
*/
int  (lua_yieldk)     (lua_State *L, int nresults, lua_KContext ctx,	//VER: >=5.3
                               lua_KFunction k);						//VER: >=5.3
int  (lua_resume)     (lua_State *L, lua_State *from, int narg);		//VER: >=5.2
int lua_resume (lua_State *L, int narg);								//VER: <5.2
int  (lua_status)     (lua_State *L);
int (lua_isyieldable) (lua_State *L);	//VER: >=5.3

int lua_yield (lua_State *L, int nresults);


/*
** garbage-collection function and options
*/

extern const int LUA_GCSTOP;
extern const int LUA_GCRESTART;
extern const int LUA_GCCOLLECT;
extern const int LUA_GCCOUNT;
extern const int LUA_GCCOUNTB;
extern const int LUA_GCSTEP;
extern const int LUA_GCSETPAUSE;
extern const int LUA_GCSETSTEPMUL;
extern const int LUA_GCISRUNNING;	//VER: >=5.2

int (lua_gc) (lua_State *L, int what, int data);


/*
** miscellaneous functions
*/

int   (lua_error) (lua_State *L);

int   (lua_next) (lua_State *L, int idx);

void  (lua_concat) (lua_State *L, int n);
void  (lua_len)    (lua_State *L, int idx);	//VER: >=5.2

size_t   (lua_stringtonumber) (lua_State *L, const char *s);	//VER: >=5.3

lua_Alloc (lua_getallocf) (lua_State *L, void **ud);
void      (lua_setallocf) (lua_State *L, lua_Alloc f, void *ud);



/*
** {==============================================================
** some useful macros
** ===============================================================
*/

void *lua_getextraspace (lua_State *L);	//VER: >=5.3

lua_Number lua_tonumber (lua_State *L, int index);
lua_Integer lua_tointeger (lua_State *L, int index);

void lua_pop (lua_State *L, int n);

void lua_newtable (lua_State *L);

void lua_register (lua_State *L, const char *name, lua_CFunction f);

void lua_pushcfunction (lua_State *L, lua_CFunction f);

int lua_isfunction (lua_State *L, int index);
int lua_istable (lua_State *L, int index);
int lua_islightuserdata (lua_State *L, int index);
int lua_isnil (lua_State *L, int index);
int lua_isboolean (lua_State *L, int index);
int lua_isthread (lua_State *L, int index);
int lua_isnone (lua_State *L, int index);
int lua_isnoneornil (lua_State *L, int index);

void lua_pushglobaltable (lua_State *L);	//VER: >=5.2

const char *lua_tostring (lua_State *L, int index);


void lua_insert (lua_State *L, int index);

void lua_remove (lua_State *L, int index);

void lua_replace (lua_State *L, int index);

/* }============================================================== */


/*
** {======================================================================
** Debug API
** =======================================================================
*/


/*
** Event codes
*/
extern const int LUA_HOOKCALL;
extern const int LUA_HOOKRET;
extern const int LUA_HOOKLINE;
extern const int LUA_HOOKCOUNT;
extern const int LUA_HOOKTAILCALL;	//VER: >=5.2


/*
** Event masks
*/
extern const int LUA_MASKCALL;
extern const int LUA_MASKRET;
extern const int LUA_MASKLINE;
extern const int LUA_MASKCOUNT;

typedef struct lua_Debug lua_Debug;  /* activation record */


/* Functions to be called by the debugger in specific events */
typedef void (*lua_Hook) (lua_State *L, lua_Debug *ar);


int (lua_getstack) (lua_State *L, int level, lua_Debug *ar);
int (lua_getinfo) (lua_State *L, const char *what, lua_Debug *ar);
const char *(lua_getlocal) (lua_State *L, const lua_Debug *ar, int n);
const char *(lua_setlocal) (lua_State *L, const lua_Debug *ar, int n);
const char *(lua_getupvalue) (lua_State *L, int funcindex, int n);
const char *(lua_setupvalue) (lua_State *L, int funcindex, int n);

void *(lua_upvalueid) (lua_State *L, int fidx, int n);				//VER: >=5.2
void  (lua_upvaluejoin) (lua_State *L, int fidx1, int n1,			//VER: >=5.2
                                               int fidx2, int n2);	//VER: >=5.2

void (lua_sethook) (lua_State *L, lua_Hook func, int mask, int count);
lua_Hook (lua_gethook) (lua_State *L);
int (lua_gethookmask) (lua_State *L);
int (lua_gethookcount) (lua_State *L);


struct lua_Debug {
  int event;
  const char *name;	/* (n) */
  const char *namewhat;	/* (n) 'global', 'local', 'field', 'method' */
  const char *what;	/* (S) 'Lua', 'C', 'main', 'tail' */
  const char *source;	/* (S) */
  int currentline;	/* (l) */
  int linedefined;	/* (S) */
  int lastlinedefined;	/* (S) */
  unsigned char nups;	/* (u) number of upvalues */
  unsigned char nparams;/* (u) number of parameters */	//VER: >=5.2
  char isvararg;        /* (u) */						//VER: >=5.2
  char istailcall;	/* (t) */							//VER: >=5.2
  char short_src[]; /* (S) */
  /* private part */
  ...;
};

/* }====================================================================== */


/******************************************************************************
* Copyright (C) 1994-2016 Lua.org, PUC-Rio.
*
* Permission is hereby granted, free of charge, to any person obtaining
* a copy of this software and associated documentation files (the
* "Software"), to deal in the Software without restriction, including
* without limitation the rights to use, copy, modify, merge, publish,
* distribute, sublicense, and/or sell copies of the Software, and to
* permit persons to whom the Software is furnished to do so, subject to
* the following conditions:
*
* The above copyright notice and this permission notice shall be
* included in all copies or substantial portions of the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
******************************************************************************/





/*
** $Id: lauxlib.h,v 1.129 2015/11/23 11:29:43 roberto Exp $
** Auxiliary functions for building Lua libraries
** See Copyright Notice in lua.h
*/


/* extra error code for 'luaL_load' */
extern const int LUA_ERRFILE;


typedef struct luaL_Reg {
  const char *name;
  lua_CFunction func;
} luaL_Reg;


void (luaL_checkversion) (lua_State *L);	//VER: >=5.2

int (luaL_getmetafield) (lua_State *L, int obj, const char *e);
int (luaL_callmeta) (lua_State *L, int obj, const char *e);
const char *(luaL_tolstring) (lua_State *L, int idx, size_t *len);	//VER: >=5.2
int (luaL_argerror) (lua_State *L, int arg, const char *extramsg);
const char *(luaL_checklstring) (lua_State *L, int arg,
                                                          size_t *l);
const char *(luaL_optlstring) (lua_State *L, int arg,
                                          const char *def, size_t *l);
lua_Number (luaL_checknumber) (lua_State *L, int arg);
lua_Number (luaL_optnumber) (lua_State *L, int arg, lua_Number def);

lua_Integer (luaL_checkinteger) (lua_State *L, int arg);
lua_Integer (luaL_optinteger) (lua_State *L, int arg,
                                          lua_Integer def);

void (luaL_checkstack) (lua_State *L, int sz, const char *msg);
void (luaL_checktype) (lua_State *L, int arg, int t);
void (luaL_checkany) (lua_State *L, int arg);

int   (luaL_newmetatable) (lua_State *L, const char *tname);
void  (luaL_setmetatable) (lua_State *L, const char *tname);		//VER: >=5.2
void *(luaL_testudata) (lua_State *L, int ud, const char *tname);	//VER: >=5.2
void *(luaL_checkudata) (lua_State *L, int ud, const char *tname);

void (luaL_where) (lua_State *L, int lvl);
int (luaL_error) (lua_State *L, const char *fmt, ...);

int (luaL_checkoption) (lua_State *L, int arg, const char *def,
                                   const char *const lst[]);

int (luaL_fileresult) (lua_State *L, int stat, const char *fname);	//VER: >=5.2
int (luaL_execresult) (lua_State *L, int stat);						//VER: >=5.2

/* predefined references */
extern const int LUA_NOREF;
extern const int LUA_REFNIL;

int (luaL_ref) (lua_State *L, int t);
void (luaL_unref) (lua_State *L, int t, int ref);

int (luaL_loadfilex) (lua_State *L, const char *filename,			//VER: >=5.2
                                               const char *mode);	//VER: >=5.2

int (luaL_loadfile) (lua_State *L, const char *filename);

int (luaL_loadbufferx) (lua_State *L, const char *buff, size_t sz,		//VER: >=5.2
                                   const char *name, const char *mode);	//VER: >=5.2
int (luaL_loadstring) (lua_State *L, const char *s);

lua_State *(luaL_newstate) (void);

lua_Integer (luaL_len) (lua_State *L, int idx);	//VER: >=5.2

const char *(luaL_gsub) (lua_State *L, const char *s, const char *p,
                                                  const char *r);

void (luaL_setfuncs) (lua_State *L, const luaL_Reg *l, int nup);	//VER: >=5.2

int (luaL_getsubtable) (lua_State *L, int idx, const char *fname);	//VER: >=5.2

void (luaL_traceback) (lua_State *L, lua_State *L1,				//VER: >=5.2
                                  const char *msg, int level);	//VER: >=5.2

void (luaL_requiref) (lua_State *L, const char *modname,		//VER: >=5.2
                                 lua_CFunction openf, int glb);	//VER: >=5.2

/*
** ===============================================================
** some useful macros
** ===============================================================
*/


void luaL_argcheck (lua_State *L,
                    int cond,
                    int arg,
                    const char *extramsg);
const char *luaL_checkstring (lua_State *L, int arg);
const char *luaL_optstring (lua_State *L,
                            int arg,
                            const char *d);

const char *luaL_typename (lua_State *L, int index);

int luaL_dofile (lua_State *L, const char *filename);

int luaL_dostring (lua_State *L, const char *str);

int luaL_getmetatable (lua_State *L, const char *tname);	//VER: >=5.3
void luaL_getmetatable (lua_State *L, const char *tname);	//VER: <5.3

int luaL_loadbuffer (lua_State *L,
                     const char *buff,
                     size_t sz,
                     const char *name);


/*
** {======================================================
** Generic Buffer manipulation
** =======================================================
*/

typedef struct luaL_Buffer luaL_Buffer;


void luaL_addchar (luaL_Buffer *B, char c);

void luaL_addsize (luaL_Buffer *B, size_t n);

void (luaL_buffinit) (lua_State *L, luaL_Buffer *B);
char *(luaL_prepbuffsize) (luaL_Buffer *B, size_t sz);					//VER: >=5.2
void (luaL_addlstring) (luaL_Buffer *B, const char *s, size_t l);
void (luaL_addstring) (luaL_Buffer *B, const char *s);
void (luaL_addvalue) (luaL_Buffer *B);
void (luaL_pushresult) (luaL_Buffer *B);
void (luaL_pushresultsize) (luaL_Buffer *B, size_t sz);					//VER: >=5.2
char *(luaL_buffinitsize) (lua_State *L, luaL_Buffer *B, size_t sz);	//VER: >=5.2

char *luaL_prepbuffer (luaL_Buffer *B);

/* }====================================================== */



/*
** {======================================================
** File handles for IO library
** =======================================================
*/

/*
** A file handle is a userdata with metatable 'LUA_FILEHANDLE' and
** initial structure 'luaL_Stream' (it may contain other fields
** after that initial structure).
*/

extern const char LUA_FILEHANDLE[];


typedef struct luaL_Stream {												//VER: >=5.2
  FILE *f;  /* stream (NULL for incompletely created streams) */			//VER: >=5.2
  lua_CFunction closef;  /* to close stream (NULL for closed streams) */	//VER: >=5.2
} luaL_Stream;																//VER: >=5.2

/* }====================================================== */





/*
** $Id: lualib.h,v 1.44 2014/02/06 17:32:33 roberto Exp $
** Lua standard libraries
** See Copyright Notice in lua.h
*/


int (luaopen_base) (lua_State *L);

extern const char LUA_COLIBNAME[];		//VER: >=5.2
int (luaopen_coroutine) (lua_State *L);	//VER: >=5.2

extern const char LUA_TABLIBNAME[];
int (luaopen_table) (lua_State *L);

extern const char LUA_IOLIBNAME[];
int (luaopen_io) (lua_State *L);

extern const char LUA_OSLIBNAME[];
int (luaopen_os) (lua_State *L);

extern const char LUA_STRLIBNAME[];
int (luaopen_string) (lua_State *L);

extern const char LUA_UTF8LIBNAME[];	//VER: >=5.3
int (luaopen_utf8) (lua_State *L);		//VER: >=5.3

extern const char LUA_BITLIBNAME[];		//VER: >=5.2
int (luaopen_bit32) (lua_State *L);		//VER: >=5.2

extern const char LUA_MATHLIBNAME[];
int (luaopen_math) (lua_State *L);

extern const char LUA_DBLIBNAME[];
int (luaopen_debug) (lua_State *L);

extern const char LUA_LOADLIBNAME[];
int (luaopen_package) (lua_State *L);


/* open all previous libraries */
void (luaL_openlibs) (lua_State *L);



extern "Python" int _caller_server(lua_State*);
lua_CFunction _get_caller_client(void);
lua_CFunction _get_arith_client(void);
lua_CFunction _get_compare_client(void);
lua_CFunction _get_index_client(void);
'''

source = '''
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
'''


lua_sources = \
        ['lapi.c', 'lcode.c', 'lctype.c', 'ldebug.c', 'ldo.c', 'ldump.c', 'lfunc.c', 'lgc.c', 'llex.c', 'lmem.c',
         'lobject.c', 'lopcodes.c', 'lparser.c', 'lstate.c', 'lstring.c', 'ltable.c', 'ltm.c', 'lundump.c', 'lvm.c',
         'lzio.c', 'lauxlib.c', 'lbaselib.c', 'lbitlib.c', 'lcorolib.c', 'ldblib.c', 'liolib.c', 'lmathlib.c',
         'loslib.c', 'lstrlib.c', 'ltablib.c', 'lutf8lib.c', 'loadlib.c', 'linit.c']
bundle_lua_path = Path('lua')


macros = []
libraries = []
if os.name == 'posix':
    macros.append(('LUA_USE_POSIX', None))
if sys.platform.startswith('linux') or sys.platform.startswith('freebsd'):
    macros.append(('LUA_USE_DLOPEN', None))
    libraries.append('dl')
if sys.platform.startswith('darwin'):
    macros.append(('LUA_USE_DLOPEN', None))
macros = tuple(macros)
libraries = tuple(libraries)


bundle_lua_pkginfo = PkgInfo(
    version=Version('5.3.5'),
    sources=tuple((bundle_lua_path / 'src' / p).__fspath__() for p in lua_sources),
    include_dirs=((bundle_lua_path / 'src').__fspath__(),),
    module_location='ffilupa._lua',
    define_macros=macros,
    libraries=libraries,
)
