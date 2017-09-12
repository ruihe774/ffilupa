from __future__ import absolute_import, unicode_literals
__all__ = tuple(map(str, ('CompileHub', 'compile_lua_method')))

import sys
import inspect
from collections import namedtuple
import six
from kwonly_args import first_kwonly_arg


CompileInfo = namedtuple('CompileInfo', ('code', 'method_wrap', 'return_hook', 'except_hook', 'origin_func'))


@first_kwonly_arg('method_wrap')
def compile_lua_method(code, method_wrap=six.create_bound_method, return_hook=lambda obj: obj, except_hook=six.reraise):
    def wrapper(func):
        @six.wraps(func)
        def newfunc(self, *args, **kwargs):
            target = six.get_method_function(getattr(self, func.__name__))
            if target is newfunc:
                raise RuntimeError('not compiled')
            return target(self, *args, **kwargs)
        newfunc.compile_info = CompileInfo(code, method_wrap, return_hook, except_hook, func)
        return newfunc
    return wrapper


class CompileHub(object):
    def __init__(self, runtime):
        super(CompileHub, self).__init__()
        cache = runtime.compile_cache

        def do_set(self, name, value):
            ci = value.compile_info
            luafunc = cache[ci.code]
            @six.wraps(ci.origin_func)
            def selffunc(self, *args, **kwargs):
                ci.origin_func(self, *args, **kwargs) # for coverage
                try:
                    return ci.return_hook(luafunc(self, *args, **kwargs))
                except:
                    return ci.except_hook(*sys.exc_info())
            setattr(self, name, six.create_bound_method(selffunc, self))

        for name, value in inspect.getmembers(self):
            if inspect.ismethod(value) and hasattr(value, 'compile_info'):
                ci = value.compile_info
                if ci.code not in cache:
                    cache[ci.code] = runtime.eval(ci.code)
                do_set(self, name, value)
