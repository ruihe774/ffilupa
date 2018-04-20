local lib, dir
for path in package.cpath:gmatch('[^;]+') do
    lib = path:gsub('%?', '_ffilupa')
    if package.loadlib(lib, '*') then
        dir = path:gsub('/[^/]*$', '')
        break
    end
end
if dir == nil then
    error('ffilupa embedding library is not found (maybe installation is incorrect)')
end
local python_backup = _G.python
local pypkg_backup = package.loaded['python']
package.loadlib(lib, 'ffilupa_init')(dir)
local ffilupa = _G.python
_G.python = python_backup
package.loaded['python'] = pypkg_backup
if ffilupa == nil then
    error('python error during loading')
end
-- add debug info
ffilupa._path = dir
ffilupa._lib = lib
return ffilupa
