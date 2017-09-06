from __future__ import absolute_import, unicode_literals
__all__ = ('CompileHub', 'compile_lua_method')

import inspect
from collections import namedtuple
import six


CompileInfo = namedtuple('CompileInfo', ('code', 'method_wrap', 'return_hook', 'origin_func'))


def compile_lua_method(code, method_wrap=six.create_bound_method, return_hook=lambda obj: obj):
    def wrapper(func):
        @six.wraps(func)
        def newfunc(self, *args):
            target = six.get_method_function(getattr(self, func.__name__))
            if target is newfunc:
                raise RuntimeError('not compiled')
            return target(self, *args)
        newfunc.compile_info = CompileInfo(code, method_wrap, return_hook, func)
        return newfunc
    return wrapper


class CompileHub(object):
    def __init__(self, runtime):
        try:
            cache = runtime.compile_cache
        except AttributeError:
            cache = runtime.compile_cache = {}

        def do_set(self, name, value):
            ci = value.compile_info
            luafunc = cache[ci.code]
            @six.wraps(ci.origin_func)
            def selffunc(self, *args):
                ci.origin_func(self, *args) # for coverage
                return ci.return_hook(luafunc(self, *args))
            setattr(self, name, six.create_bound_method(selffunc, self))

        for name, value in inspect.getmembers(self):
            if inspect.ismethod(value) and hasattr(value, 'compile_info'):
                ci = value.compile_info
                if ci.code not in cache:
                    cache[ci.code] = runtime.eval(ci.code)
                do_set(self, name, value)
