project(ffilupa C)
cmake_minimum_required(VERSION 3.8)
find_package(PythonInterp 3.5 REQUIRED)
find_package(Lua 5.2 REQUIRED)
include(cmake/dist.cmake)
include(cmake/lua.cmake)

set(embed_libname "_ffilupa_embedding_lua${LUA_VERSION_MAJOR}${LUA_VERSION_MINOR}")
set(embed_lib "${embed_libname}${CMAKE_SHARED_LIBRARY_SUFFIX}")
add_custom_command(OUTPUT "${embed_lib}"
    COMMAND ${PYTHON_EXECUTABLE} setup.py build_ext -i
    COMMAND ${PYTHON_EXECUTABLE} tool.py trim_libname ${CMAKE_SHARED_LIBRARY_SUFFIX}
    COMMAND ${PYTHON_EXECUTABLE} tool.py cp ${embed_lib} ${PROJECT_BINARY_DIR}/${embed_lib}
    DEPENDS "setup.py;findlua/embedding.c;findlua/embedding.h;findlua/embedding-template.py;findlua/__init__.py"
    WORKING_DIRECTORY ${PROJECT_SOURCE_DIR}
    COMMENT "Building embedding library"
)
add_custom_target(ffilupa_embedding ALL DEPENDS "${embed_lib}")
install(FILES "${PROJECT_BINARY_DIR}/${embed_lib}" DESTINATION "${INSTALL_CMOD}")

file(WRITE "${PROJECT_BINARY_DIR}/ffilupa.lua"
"local python_backup = _G.python
local libname = '${embed_libname}'
for path in package.cpath:gmatch('[^;]+') do
    local libpath = path:gsub('%?', libname)
    if package.loadlib(libpath, '*') then
        package.loadlib(libpath, 'ffilupa_init')()
        break
    end
end
local python = _G.python
_G.python = python_backup
package.loaded['python'] = nil
return python"
)
install(FILES "${PROJECT_BINARY_DIR}/ffilupa.lua" DESTINATION "${INSTALL_LMOD}")
