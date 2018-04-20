package = "ffilupa"
version = "2.3.0.dev1-1"
source = {
   url = "git+https://github.com/TitanSnow/ffilupa.git"
}
description = {
   summary = "A modern two-way bridge between Python and Lua",
   homepage = "https://github.com/TitanSnow/ffilupa",
   license = "LGPL-3"
}
dependencies = {
   "lua >= 5.2, < 5.4"
}
build = {
   type = "make",
   build_variables = {
      LUA_LIBDIR = "$(LUA_LIBDIR)",
      LUA_INCDIR = "$(LUA_INCDIR)",
      LUA = "$(LUA)"
   },
   install_variables = {
      LIBDIR = "$(LIBDIR)",
      LUADIR = "$(LUADIR)"
   }
}
