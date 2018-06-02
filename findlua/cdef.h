extern "Python" int _caller_server(lua_State*);
lua_CFunction _get_caller_client(void);
lua_CFunction _get_arith_client(void);
lua_CFunction _get_compare_client(void);
lua_CFunction _get_index_client(void);
