project(ffilupa C)
cmake_minimum_required(VERSION 3.8)
find_package(PythonInterp 3.5 REQUIRED)
find_package(Lua 5.2 REQUIRED)
include(cmake/dist.cmake)
include(cmake/lua.cmake)

set(embed_lib "_ffilupa_embedding_lua${LUA_VERSION_MAJOR}${LUA_VERSION_MINOR}${CMAKE_SHARED_LIBRARY_SUFFIX}")
add_custom_command(OUTPUT "${embed_lib}"
    COMMAND ${PYTHON_EXECUTABLE} setup.py build_ext -i
    COMMAND ${PYTHON_EXECUTABLE} tool.py trim_libname ${CMAKE_SHARED_LIBRARY_SUFFIX}
    COMMAND ${PYTHON_EXECUTABLE} tool.py mv ${embed_lib} ${PROJECT_BINARY_DIR}
    DEPENDS "setup.py;findlua/embedding.c;findlua/embedding.h;findlua/embedding-template.py;findlua/__init__.py"
    WORKING_DIRECTORY ${PROJECT_SOURCE_DIR}
    COMMENT "Building embedding library"
)
add_custom_target(ffilupa_embedding ALL DEPENDS "${embed_lib}")
install(FILES "${PROJECT_BINARY_DIR}/${embed_lib}" DESTINATION "${INSTALL_CMOD}")
