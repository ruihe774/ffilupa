from __future__ import absolute_import, unicode_literals
__all__ = ('CompileHub', 'compile_lua_method')

from weakref import WeakKeyDictionary
import inspect
import six


class Compile(object):
    def __init__(self, code, method_wrap=six.create_bound_method, return_hook=lambda obj: obj):
        self.code = code
        self.method_wrap = method_wrap
        self.return_hook = return_hook

    def compile(self, runtime):
        luafunc = runtime.eval(self.code)
        return_hook = self.return_hook
        def pyfunc(*args):
            return return_hook(luafunc(*args))
        return pyfunc


compile_dict = WeakKeyDictionary()


def compile_lua_method(code, method_wrap=six.create_bound_method, return_hook=lambda obj: obj):
    def wrapper(func):
        @six.wraps(func)
        def newfunc(self, *args):
            func(self, *args) # for coverage
            return getattr(self, func.__name__)(*args)
        compile_dict[newfunc] = Compile(code, method_wrap, return_hook)
        return newfunc
    return wrapper


class CompileHub(object):
    def __init__(self, runtime):
        cls = self.__class__
        if not hasattr(cls, 'compile_cache'):
            cls.compile_cache = WeakKeyDictionary()

        cache = cls.compile_cache
        cache[runtime] = cache.get(runtime, WeakKeyDictionary())
        for attrname, attr in inspect.getmembers(self):
            if not inspect.ismethod(attr):
                continue
            attr = six.get_method_function(attr)
            try:
                isin = attr in compile_dict
            except TypeError:
                isin = False
            if isin:
                attr = compile_dict[attr]
                try:
                    setattr(self, attrname, attr.method_wrap(cache[runtime][attr], self))
                except KeyError:
                    result = attr.compile(runtime)
                    setattr(self, attrname, attr.method_wrap(result, self))
                    cache[runtime][attr] = result
