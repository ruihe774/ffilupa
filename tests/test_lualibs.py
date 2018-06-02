from pathlib import Path
import pytest
import semantic_version as sv
from ffilupa import *
from ffilupa import lualibs


def test_read_source():
    with (Path(lualibs.__file__).parent / 'lua.json').open() as f:
        content = f.read()
        assert lualibs.read_resource('lua.json') == content
        def rfnf(*args, **kwargs):
            raise FileNotFoundError
        open = Path.open
        Path.open = rfnf
        assert lualibs.read_resource('lua.json') == content
        Path.open = open


def test_get_lualibs():
    lualibs = get_lualibs()
    assert isinstance(lualibs, list)
    assert isinstance(lualibs, LuaLibs)
    for lualib in lualibs:
        assert isinstance(lualib, LuaLib)
        assert isinstance(lualib.lua_version, sv.Version)


def test_LuaLib():
    info = PkgInfo(['incd'], ['libd'], ['libs'], ['eca'], ['ela'], sv.Version('2.2.2'))
    lualib = LuaLib('awd', info)
    assert lualib.name == 'awd'
    assert lualib.info == info
    assert lualib.info.include_dirs == ['incd']
    assert lualib.info.library_dirs == ['libd']
    assert lualib.info.libraries == ['libs']
    assert lualib.info.extra_compile_args == ['eca']
    assert lualib.info.extra_link_args == ['ela']
    assert lualib.info.version is lualib.version
    assert lualib.version == sv.Version('2.2.2')
    assert isinstance(lualib.version, sv.Version)
    assert lualib.modname == 'ffilupa._awd'
    with pytest.raises(ImportError):
        lualib.import_mod()


def test_LuaLibs():
    geninfo = lambda ver: PkgInfo(['incd'], ['libd'], ['libs'], ['eca'], ['ela'], sv.Version(ver))
    awds = [LuaLib('awd1', geninfo('1.0.0')), LuaLib('awd2', geninfo('2.0.0')), LuaLib('awd3', geninfo('3.0.0'))]
    lualibs = LuaLibs(awds)
    assert lualibs.filter_version(sv.Spec('>=2')) == awds[1:]
    assert lualibs.filter_version(sv.Spec('>=3')) == awds[2:]
    assert lualibs.select_version(sv.Spec('>=2')) is awds[-1]
    assert lualibs.select_name('awd1') is awds[0]
    assert lualibs.filter_version(sv.Spec('>=4')) == []
    with pytest.raises(ValueError):
        assert lualibs.select_version(sv.Spec('>=4'))
    with pytest.raises(ValueError):
        assert lualibs.select_name('awd4')
