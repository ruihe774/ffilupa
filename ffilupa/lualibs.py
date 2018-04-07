import importlib
import itertools
import pkg_resources
import yaml


__all__ = ('LuaLib', 'LuaLibs', 'get_lualibs',)


class LuaLib:
    def __init__(self, name, info):
        self.name = name
        self.info = info

    @property
    def version(self):
        return self.info.version

    @property
    def modname(self):
        return 'ffilupa._' + self.name

    def import_mod(self):
        return importlib.import_module(self.modname)


class LuaLibs(list):
    def filter_version(self, spec):
        return LuaLibs(filter(lambda lualib: spec.match(lualib.version), self))

    def select_version(self, spec):
        return max(self.filter_version(spec), key=lambda ll: ll.version)


def get_lualibs():
    return LuaLibs(itertools.starmap(LuaLib, yaml.load(pkg_resources.resource_stream(__package__, 'lua.yml')).items()))
