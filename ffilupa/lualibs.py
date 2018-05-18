import importlib
import itertools
import functools
import types
import time
import copy
import json
import sys
import gc
from collections import namedtuple
from pathlib import Path
import semantic_version as sv


__all__ = ('LuaLib', 'LuaLibs', 'get_lualibs', 'PkgInfo', 'set_default_lualib', 'get_default_lualib')


PkgInfo = namedtuple(
    'PkgInfo',
    (
        'include_dirs',
        'library_dirs',
        'libraries',
        'extra_compile_args',
        'extra_link_args',
        'version',
    ),
)


class LuaLib:
    def __init__(self, name, info):
        self.name = name
        self.info = info

    @property
    def version(self):
        return self.info.version

    @property
    def lua_version(self):
        mod = self.import_mod()
        return sv.Version(mod.ffi.string(mod.lib.LUA_RELEASE).decode()[4:])

    @property
    def modname(self):
        return 'ffilupa._' + self.name

    def import_mod(self):
        return importlib.import_module(self.modname)

    def to_trace(self, db_name, verbose=False):
        import sqlite3
        trace_lib = copy.copy(self)
        trace_lib.__class__ = LuaTraceLib
        trace_lib.verbose = verbose
        trace_lib.database = sqlite3.connect(db_name)
        trace_lib.database.execute('CREATE TABLE IF NOT EXISTS trace ( \
            id INTEGER PRIMARY KEY AUTOINCREMENT, \
            func_name       TEXT NOT NULL, \
            args            TEXT NOT NULL, \
            return_value    TEXT NOT NULL, \
            start_time      REAL NOT NULL, \
            call_time       REAL NOT NULL \
        )')
        trace_lib.database.execute('CREATE INDEX IF NOT EXISTS idx_call_time ON trace(call_time)')
        return trace_lib


class LuaLibs(list):
    def filter_version(self, spec):
        return LuaLibs(filter(lambda lualib: spec.match(lualib.version), self))

    def select_version(self, spec):
        try:
            return max(self.filter_version(spec), key=lambda ll: ll.version)
        except ValueError as e:
            raise ValueError('Required lua lib not found') from e

    def select_name(self, name):
        try:
            return next(filter(lambda lualib: lualib.name == name, self))
        except StopIteration as e:
            raise ValueError('Required lua lib not found') from e


def read_resource(filename):
    try:
        with (Path(__file__).parent / filename).open() as f:
            return f.read()
    except FileNotFoundError:
        import pkg_resources
        return pkg_resources.resource_string(__package__, filename).decode()


def get_lualibs():
    dic = json.loads(read_resource('lua.json'))
    for v in dic.values():
        v['version'] = sv.Version(v['version'])
    for k in dic:
        dic[k] = PkgInfo(**dic[k])
    return LuaLibs(itertools.starmap(LuaLib, dic.items()))


_default_lualib = None


def set_default_lualib(lualib):
    global _default_lualib
    _default_lualib = lualib


def get_default_lualib():
    if _default_lualib is None:
        return get_lualibs().select_version(sv.Spec('>=5.2,<5.4'))
    else:
        return _default_lualib


class LuaTraceLib(LuaLib):
    def __init__(self, *args, **kwargs):
        raise TypeError('use LuaLib.to_trace() to create a LuaTraceLib object')

    def import_mod(self):
        origin_mod = super().import_mod()
        mod = types.ModuleType(origin_mod.__name__)
        mod.ffi = origin_mod.ffi
        class TraceLib:
            def __getattr__(lib, item):
                func = getattr(origin_mod.lib, item)
                if not isinstance(func, types.BuiltinFunctionType):
                    return func
                @functools.wraps(func)
                def _(*args):
                    store_args = tuple(repr(arg) for arg in args)
                    gcold = gc.isenabled()
                    if gcold:
                        gc.disable()
                    try:
                        start_time = time.time()
                        start_counter = time.perf_counter()
                        return_value = func(*args)
                        end_counter = time.perf_counter()
                    finally:
                        if gcold:
                            gc.enable()
                    self.database.execute('INSERT INTO trace (func_name, args, return_value, start_time, call_time) \
                                          VALUES (?, ?, ?, ?, ?)', (item, ', '.join(store_args), repr(return_value), start_time, end_counter - start_counter))
                    if self.verbose:
                        print('{}  {:4.3f}s:  {}({}) = {}'.format(time.ctime(start_time), end_counter - start_counter, item, ', '.join(store_args), repr(return_value)), file=sys.stderr)
                    return return_value
                setattr(lib, item, _)
                return _
        mod.lib = TraceLib()
        return mod

    def commit_db(self):
        self.database.commit()
