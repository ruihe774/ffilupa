typedef long long lua_Integer;

typedef double lua_Number;

typedef struct {...;} lua_State;

typedef void * (*lua_Alloc) (void *ud,
                             void *ptr,
                             size_t osize,
                             size_t nsize);

typedef int (*lua_CFunction) (lua_State *L);

typedef struct{...;} lua_KContext;

typedef int (*lua_KFunction) (lua_State *L, int status, lua_KContext ctx);

typedef const char * (*lua_Reader) (lua_State *L,
                                    void *data,
                                    size_t *size);

typedef unsigned long long lua_Unsigned;

typedef int (*lua_Writer) (lua_State *L,
                           const void* p,
                           size_t sz,
                           void* ud);

int lua_absindex (lua_State *L, int idx);

void lua_arith (lua_State *L, int op);

lua_CFunction lua_atpanic (lua_State *L, lua_CFunction panicf);

void lua_call (lua_State *L, int nargs, int nresults);

void lua_callk (lua_State *L,
                int nargs,
                int nresults,
                lua_KContext ctx,
                lua_KFunction k);

int lua_checkstack (lua_State *L, int n);

void lua_close (lua_State *L);

int lua_compare (lua_State *L, int index1, int index2, int op);

void lua_concat (lua_State *L, int n);

void lua_copy (lua_State *L, int fromidx, int toidx);

void lua_createtable (lua_State *L, int narr, int nrec);

int lua_dump (lua_State *L,
                        lua_Writer writer,
                        void *data,
                        int strip);

int lua_error (lua_State *L);

int lua_gc (lua_State *L, int what, int data);

lua_Alloc lua_getallocf (lua_State *L, void **ud);

int lua_getfield (lua_State *L, int index, const char *k);

void *lua_getextraspace (lua_State *L);

int lua_getglobal (lua_State *L, const char *name);

int lua_geti (lua_State *L, int index, lua_Integer i);

int lua_getmetatable (lua_State *L, int index);

int lua_gettable (lua_State *L, int index);

int lua_gettop (lua_State *L);

int lua_getuservalue (lua_State *L, int index);

void lua_insert (lua_State *L, int index);



int lua_isboolean (lua_State *L, int index);

int lua_iscfunction (lua_State *L, int index);

int lua_isfunction (lua_State *L, int index);

int lua_isinteger (lua_State *L, int index);

int lua_islightuserdata (lua_State *L, int index);

int lua_isnil (lua_State *L, int index);

int lua_isnone (lua_State *L, int index);

int lua_isnoneornil (lua_State *L, int index);

int lua_isnumber (lua_State *L, int index);

int lua_isstring (lua_State *L, int index);

int lua_istable (lua_State *L, int index);

int lua_isthread (lua_State *L, int index);

int lua_isuserdata (lua_State *L, int index);

int lua_isyieldable (lua_State *L);

void lua_len (lua_State *L, int index);

int lua_load (lua_State *L,
              lua_Reader reader,
              void *data,
              const char *chunkname,
              const char *mode);

lua_State *lua_newstate (lua_Alloc f, void *ud);

void lua_newtable (lua_State *L);

lua_State *lua_newthread (lua_State *L);

void *lua_newuserdata (lua_State *L, size_t size);

int lua_next (lua_State *L, int index);

int lua_numbertointeger (lua_Number n, lua_Integer *p);

int lua_pcall (lua_State *L, int nargs, int nresults, int msgh);

int lua_pcallk (lua_State *L,
                int nargs,
                int nresults,
                int msgh,
                lua_KContext ctx,
                lua_KFunction k);

void lua_pop (lua_State *L, int n);

void lua_pushboolean (lua_State *L, int b);

void lua_pushcclosure (lua_State *L, lua_CFunction fn, int n);

void lua_pushcfunction (lua_State *L, lua_CFunction f);

const char *lua_pushfstring (lua_State *L, const char *fmt, ...);

void lua_pushglobaltable (lua_State *L);

void lua_pushinteger (lua_State *L, lua_Integer n);

void lua_pushlightuserdata (lua_State *L, void *p);

const char *lua_pushlstring (lua_State *L, const char *s, size_t len);

void lua_pushnil (lua_State *L);

void lua_pushnumber (lua_State *L, lua_Number n);

const char *lua_pushstring (lua_State *L, const char *s);

int lua_pushthread (lua_State *L);

void lua_pushvalue (lua_State *L, int index);

int lua_rawequal (lua_State *L, int index1, int index2);

int lua_rawget (lua_State *L, int index);

int lua_rawgeti (lua_State *L, int index, lua_Integer n);

int lua_rawgetp (lua_State *L, int index, const void *p);

size_t lua_rawlen (lua_State *L, int index);

void lua_rawset (lua_State *L, int index);

void lua_rawseti (lua_State *L, int index, lua_Integer i);

void lua_rawsetp (lua_State *L, int index, const void *p);

void lua_register (lua_State *L, const char *name, lua_CFunction f);

void lua_remove (lua_State *L, int index);

void lua_replace (lua_State *L, int index);

int lua_resume (lua_State *L, lua_State *from, int nargs);

void lua_rotate (lua_State *L, int idx, int n);

void lua_setallocf (lua_State *L, lua_Alloc f, void *ud);

void lua_setfield (lua_State *L, int index, const char *k);

void lua_setglobal (lua_State *L, const char *name);

void lua_seti (lua_State *L, int index, lua_Integer n);

void lua_setmetatable (lua_State *L, int index);

void lua_settable (lua_State *L, int index);

void lua_settop (lua_State *L, int index);

void lua_setuservalue (lua_State *L, int index);

int lua_status (lua_State *L);

size_t lua_stringtonumber (lua_State *L, const char *s);

int lua_toboolean (lua_State *L, int index);

lua_CFunction lua_tocfunction (lua_State *L, int index);

lua_Integer lua_tointeger (lua_State *L, int index);

lua_Integer lua_tointegerx (lua_State *L, int index, int *isnum);

const char *lua_tolstring (lua_State *L, int index, size_t *len);

lua_Number lua_tonumber (lua_State *L, int index);

lua_Number lua_tonumberx (lua_State *L, int index, int *isnum);

const void *lua_topointer (lua_State *L, int index);

const char *lua_tostring (lua_State *L, int index);

lua_State *lua_tothread (lua_State *L, int index);

void *lua_touserdata (lua_State *L, int index);

int lua_type (lua_State *L, int index);

const char *lua_typename (lua_State *L, int tp);

int lua_upvalueindex (int i);

const lua_Number *lua_version (lua_State *L);

void lua_xmove (lua_State *from, lua_State *to, int n);

int lua_yield (lua_State *L, int nresults);

int lua_yieldk (lua_State *L,
                int nresults,
                lua_KContext ctx,
                lua_KFunction k);


typedef struct {...;} luaL_Buffer;

typedef struct luaL_Reg {
  const char *name;
  lua_CFunction func;
} luaL_Reg;

typedef struct luaL_Stream {
  FILE *f;
  lua_CFunction closef;
} luaL_Stream;

void luaL_addchar (luaL_Buffer *B, char c);

void luaL_addlstring (luaL_Buffer *B, const char *s, size_t l);

void luaL_addsize (luaL_Buffer *B, size_t n);

void luaL_addstring (luaL_Buffer *B, const char *s);

void luaL_addvalue (luaL_Buffer *B);

void luaL_argcheck (lua_State *L,
                    int cond,
                    int arg,
                    const char *extramsg);

int luaL_argerror (lua_State *L, int arg, const char *extramsg);

void luaL_buffinit (lua_State *L, luaL_Buffer *B);

char *luaL_buffinitsize (lua_State *L, luaL_Buffer *B, size_t sz);

int luaL_callmeta (lua_State *L, int obj, const char *e);

void luaL_checkany (lua_State *L, int arg);

lua_Integer luaL_checkinteger (lua_State *L, int arg);

const char *luaL_checklstring (lua_State *L, int arg, size_t *l);

lua_Number luaL_checknumber (lua_State *L, int arg);

int luaL_checkoption (lua_State *L,
                      int arg,
                      const char *def,
                      const char *const lst[]);

void luaL_checkstack (lua_State *L, int sz, const char *msg);

const char *luaL_checkstring (lua_State *L, int arg);

void luaL_checktype (lua_State *L, int arg, int t);

void *luaL_checkudata (lua_State *L, int arg, const char *tname);

void luaL_checkversion (lua_State *L);

int luaL_dofile (lua_State *L, const char *filename);

int luaL_dostring (lua_State *L, const char *str);

int luaL_error (lua_State *L, const char *fmt, ...);

int luaL_execresult (lua_State *L, int stat);

int luaL_fileresult (lua_State *L, int stat, const char *fname);

int luaL_getmetafield (lua_State *L, int obj, const char *e);

int luaL_getmetatable (lua_State *L, const char *tname);

int luaL_getsubtable (lua_State *L, int idx, const char *fname);

const char *luaL_gsub (lua_State *L,
                       const char *s,
                       const char *p,
                       const char *r);

lua_Integer luaL_len (lua_State *L, int index);

int luaL_loadbuffer (lua_State *L,
                     const char *buff,
                     size_t sz,
                     const char *name);

int luaL_loadbufferx (lua_State *L,
                      const char *buff,
                      size_t sz,
                      const char *name,
                      const char *mode);

int luaL_loadfile (lua_State *L, const char *filename);

int luaL_loadfilex (lua_State *L, const char *filename,
                                            const char *mode);

int luaL_loadstring (lua_State *L, const char *s);

void luaL_newlib (lua_State *L, const luaL_Reg l[]);

void luaL_newlibtable (lua_State *L, const luaL_Reg l[]);

int luaL_newmetatable (lua_State *L, const char *tname);

lua_State *luaL_newstate (void);

void luaL_openlibs (lua_State *L);

lua_Integer luaL_optinteger (lua_State *L,
                             int arg,
                             lua_Integer d);

const char *luaL_optlstring (lua_State *L,
                             int arg,
                             const char *d,
                             size_t *l);

lua_Number luaL_optnumber (lua_State *L, int arg, lua_Number d);

const char *luaL_optstring (lua_State *L,
                            int arg,
                            const char *d);

char *luaL_prepbuffer (luaL_Buffer *B);

char *luaL_prepbuffsize (luaL_Buffer *B, size_t sz);

void luaL_pushresult (luaL_Buffer *B);

void luaL_pushresultsize (luaL_Buffer *B, size_t sz);

int luaL_ref (lua_State *L, int t);

void luaL_requiref (lua_State *L, const char *modname,
                    lua_CFunction openf, int glb);

void luaL_setfuncs (lua_State *L, const luaL_Reg *l, int nup);

void luaL_setmetatable (lua_State *L, const char *tname);

void *luaL_testudata (lua_State *L, int arg, const char *tname);

const char *luaL_tolstring (lua_State *L, int idx, size_t *len);

void luaL_traceback (lua_State *L, lua_State *L1, const char *msg,
                     int level);

const char *luaL_typename (lua_State *L, int index);

void luaL_unref (lua_State *L, int t, int ref);

void luaL_where (lua_State *L, int lvl);


extern const int LUA_REGISTRYINDEX;
extern const int LUA_MULTRET;
