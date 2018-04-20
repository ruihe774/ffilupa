local lib, dir
for path in package.cpath:gmatch('[^;]+') do
    lib = path:gsub('%?', '_ffilupa')
    if package.loadlib(lib, '*') then
        dir = path:gsub('/[^/]*$', '/')
        break
    end
end
if dir == nil then
    os.error('ffilupa lib not found')
end
local python_backup = _G.python
local pypkg_backup = package.loaded['python']
package.loadlib(lib, 'ffilupa_init')(dir)
local ffilupa = _G.python
_G.python = python_backup
package.loaded['python'] = pypkg_backup
return ffilupa
