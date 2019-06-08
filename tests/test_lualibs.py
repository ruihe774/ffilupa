import os
from datetime import datetime
import dataclasses
from pathlib import Path
from setuptools import pep425tags, Extension
from packaging.version import Version
import pytest
import ffilupa
from ffilupa import lualibs
from ffilupa.lualibs import builder
from ffilupa.lualibs import _pkginfo
from ffilupa.lualibs import _datadir

def test_pkginfo_defaults():
    p = lualibs.PkgInfo(Version('5.3.5'))
    assert p.ffilupa_version == Version(ffilupa.__version__)
    assert p.python_tag in pep425tags.get_supported()


def test_pkginfo_serialize():
    p = builder.bundle_lua_pkginfo
    assert lualibs.PkgInfo.deserialize(p.serialize()) == p
    p = dataclasses.replace(p, build_time=datetime.utcnow(), module_location=Path().absolute())
    assert lualibs.PkgInfo.deserialize(p.serialize()) == p


def test_pkginfo_deserialize_error():
    v = Version('5.3.5')
    p = lualibs.PkgInfo(v, ffilupa_version=Version('999.99.9'))
    t = p.serialize()
    with pytest.raises(_pkginfo.VersionIncompatible):
        lualibs.PkgInfo.deserialize(t)
    p = lualibs.PkgInfo(v, python_tag=('awd', 'dwa', 'def'))
    t = p.serialize()
    with pytest.raises(_pkginfo.AbiIncompatible):
        lualibs.PkgInfo.deserialize(t)
    p = builder.bundle_lua_pkginfo
    t = p.serialize()
    t['_hash'] = 'awd'
    with pytest.raises(_pkginfo.HashMismatch):
        lualibs.PkgInfo.deserialize(t)


def test_datadir():
    datadir = _datadir.get_data_dir()
    assert datadir.is_absolute()
    assert datadir.is_dir()
    assert datadir.parts[-1] == 'ffilupa'
    with (datadir / 'awd').open('w') as f:
        f.write('awd')
    (datadir / 'awd').unlink()

    datadir = _datadir.get_global_data_dir()
    if datadir is not None:
        assert datadir.is_absolute()
        assert datadir.is_dir()


def test_lualib():
    l = lualibs.get_default_lualib()
    assert l.info is builder.bundle_lua_pkginfo
    assert l.name == 'ffilupa._lua'
    assert l.lua_version == l.version == builder.bundle_lua_pkginfo.version
    assert l.import_mod().__name__ == 'ffilupa._lua'
    dl = l

    l = lualibs.LuaLib(builder.bundle_lua_pkginfo)
    lualibs.register_lualib(l)
    assert lualibs.get_lualibs()[-1] is l
    lualibs.set_default_lualib(l)
    assert lualibs.get_default_lualib() is l
    lualibs.get_lualibs().pop()
    lualibs.set_default_lualib(dl)

    p = lualibs.PkgInfo(Version('5.3.5'), module_location=Path(), module_name='dwa')
    with pytest.raises(ModuleNotFoundError):
        lualibs.LuaLib(p).import_mod()
    p = lualibs.PkgInfo(Version('5.3.5'), module_location='awd')
    with pytest.raises(ModuleNotFoundError):
        lualibs.LuaLib(p).import_mod()
    p = lualibs.PkgInfo(Version('5.3.5'))
    with pytest.raises(ValueError):
        lualibs.LuaLib(p).import_mod()
