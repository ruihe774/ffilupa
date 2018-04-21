__all__ = ('LuaEmbeddingRuntime', 'init')

from .lualibs import get_lualibs
from .runtime import LuaRuntime


class LuaEmbeddingRuntime(LuaRuntime):
    def __init__(self, *args, **kwargs):
        self._temp_state = kwargs.pop('lua_state')
        super().__init__(*args, **kwargs)

    def _newstate(self):
        self._state = self.ffi.cast('lua_State*', self._temp_state)
        del self._temp_state


_runtimes = []


def init(L, libname):
    _runtimes.append(LuaEmbeddingRuntime(lualib=get_lualibs().select_name(libname), lua_state=L))
