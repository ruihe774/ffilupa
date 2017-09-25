import pkg_resources
import json
from importlib import import_module
from findlua import PkgInfo


class LuaLibDesc:

    @staticmethod
    def get_libs():
        return {
            name: PkgInfo(**info)
            for name, info in json.loads(
                pkg_resources.resource_string(__package__, 'lua.json').decode()
            ).items()
        }

    def __init__(self, libname):
        self.libname = libname
        self.libinfo = self.__class__.get_libs()[libname]

    def to_modname(self):
        return 'ffilupa._{}'.format(self.libname)

    def import_mod(self):
        return import_module(self.to_modname())

    def get_version(self):
        return self.libinfo.version
