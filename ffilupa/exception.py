"""module contains exception classes for lua errors"""


__all__ = (
    'LuaErr',
    'LuaOK',
    'LuaYield',
    'LuaErrRun',
    'LuaErrSyntax',
    'LuaErrMem',
    'LuaErrGCMM',
    'LuaErrErr',
)


class LuaErr(Exception):
    """
    Base exception class for error happened in lua.

    One instance of LuaErr has two attributes.

    * ``status``, the return value of failed lua API call.
    * ``err_msg``, the error message got from lua.
    """

    @staticmethod
    def new(runtime, status, err_msg, encoding=None):
        """
        Make an instance of one of the subclasses of LuaErr
        according to ``status``.

        ``err_msg`` is string type.

        ``encoding`` will be used to decode the ``err_msg``
        if it's binary type. ``err_msg`` will remain undecoded
        if ``encoding`` is None.
        """
        if isinstance(err_msg, bytes) and encoding is not None:
            err_msg = err_msg.decode(encoding)
        return {
            runtime.lib.LUA_OK: LuaOK,
            runtime.lib.LUA_YIELD: LuaYield,
            runtime.lib.LUA_ERRRUN: LuaErrRun,
            runtime.lib.LUA_ERRSYNTAX: LuaErrSyntax,
            runtime.lib.LUA_ERRMEM: LuaErrMem,
            runtime.lib.LUA_ERRGCMM: LuaErrGCMM,
            runtime.lib.LUA_ERRERR: LuaErrErr,
        }.get(status, LuaErr)(status, err_msg)

    def __init__(self, status, err_msg):
        """
        Init self with ``status`` and ``err_msg``.
        """
        super().__init__(status, err_msg)
        self.status, self.err_msg = status, err_msg

    def __repr__(self):
        return '{}: status {}\n{}'.format(self.__class__.__name__, self.status, self.err_msg)

    def __str__(self):
        return self.err_msg

class LuaOK(LuaErr):
    """Exception LuaOK"""
    pass
class LuaYield(LuaErr):
    """Exception LuaYield"""
    pass
class LuaErrRun(LuaErr):
    """Exception LuaErrRun"""
    pass
class LuaErrSyntax(LuaErr):
    """Exception LuaErrSyntax"""
    pass
class LuaErrMem(LuaErr):
    """Exception LuaErrMem"""
    pass
class LuaErrGCMM(LuaErr):
    """Exception LuaErrGCMM"""
    pass
class LuaErrErr(LuaErr):
    """Exception LuaErrErr"""
    pass
