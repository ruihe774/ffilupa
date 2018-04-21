"""module contains lua compile helpers"""


__all__ = ('CompileHub', 'compile_lua_method')

import sys
import functools
from .util import reraise


def compile_lua_method(code, return_hook=lambda obj: obj, except_hook=reraise):
    """
    A decorator makes method become "lua method".

    A subclass of CompileHub can contains lua methods
    that not written in python but in lua. At call time
    of the method, it will be compiled by the certain
    lua runtime and just behavior like a python method.

    The compile result is cached.

    Arguments:

    * ``code``: the lua source code.

    Keyword-only arguments:

    * ``return_hook``: the function to call at return time
      of the lua function. The arguments are the return
      values of the lua function and final return value
      will be the return value of the return hook.
    * ``except_hook``: the function to call at the time
      it raises a exception. The arguments are the same
      as the return value of ``sys.exc_info()``. If it's
      set, the exception won't be pop up unless reraise
      it in the except hook.
    """
    def wrapper(func):
        @functools.wraps(func)
        def newfunc(self, *args, **kwargs):
            assert isinstance(self, CompileHub), 'only CompileHub and its subclasses can have "lua method"'
            func(self, *args, **kwargs) # for coverage
            cache = self._runtime.compile_cache
            try:
                luafunc = cache[code]
            except KeyError:
                luafunc = cache[code] = self._runtime.eval(code)
            try:
                result = luafunc(self, *args, **kwargs)
            except:
                return except_hook(*sys.exc_info())
            else:
                return return_hook(result)
        return newfunc
    return wrapper


class CompileHub:
    """
    Class CompileHub.
    """
    def __init__(self, runtime):
        """
        Init self.

        ``runtime`` is the lua runtime that lua methods
        compiled in.
        """
        super().__init__()
        self._runtime = runtime
