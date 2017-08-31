from __future__ import absolute_import, unicode_literals
__all__ = ('Compile', 'CompileHub')

from weakref import WeakKeyDictionary
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


class CompileHub(object):
    def __init__(self, runtime):
        cls = self.__class__
        if not hasattr(cls, 'cache'):
            cls.cache = WeakKeyDictionary()

        cache = cls.cache
        cache[runtime] = cache.get(runtime, WeakKeyDictionary())
        for attrname in dir(self):
            attr = getattr(self, attrname, None)
            if isinstance(attr, Compile):
                try:
                    setattr(self, attrname, attr.method_wrap(cache[runtime][attr], self))
                except KeyError:
                    result = attr.compile(runtime)
                    setattr(self, attrname, attr.method_wrap(result, self))
                    cache[runtime][attr] = result
