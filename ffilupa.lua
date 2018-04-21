local lib, err = package.searchpath('_ffilupa', package.cpath)
if lib == nil then
    error('ffilupa embedding library is not found (maybe installation is incorrect)' .. err)
end
local path = lib:sub(1, lib:len() - lib:reverse():find(package.config:sub(1, 1), 1, true))
local python_backup = _G.python
local pypkg_backup = package.loaded['python']
package.loadlib(lib, '*')
package.loadlib(lib, 'ffilupa_init')(path)
local ffilupa = _G.python
_G.python = python_backup
package.loaded['python'] = pypkg_backup
if ffilupa == nil then
    error('python error during loading')
end
-- add debug info
ffilupa._path = path
ffilupa._lib = lib
return ffilupa
