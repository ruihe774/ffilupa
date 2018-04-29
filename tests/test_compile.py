import pytest
from ffilupa import *
from ffilupa.compile import *


calltimes = 0


class _TestCompile(CompileHub):
    @compile_lua_method('function(o) return o end')
    def m1(self):
        global calltimes; calltimes += 1

    @compile_lua_method('function(self, o) return o end')
    def m2(self, o):
        global calltimes; calltimes += 1

    @compile_lua_method('function(self, o) return o end')
    def m3(self):
        global calltimes; calltimes += 1

    @compile_lua_method('function(self) return self end', return_hook=lambda o: [o])
    def m4(self):
        global calltimes; calltimes += 1

    @compile_lua_method('function(self) return #1 end', except_hook=lambda tp, e, tb: tp)
    def m5(self):
        global calltimes; calltimes += 1

    @compile_lua_method('function(self, o) return o end', except_hook=lambda tp, e, tb: tp)
    def m6(self):
        global calltimes; calltimes += 1

def test_compile():
    tc = _TestCompile(LuaRuntime())
    assert tc.m1() is tc
    assert tc.m2(1) is 1
    with pytest.raises(TypeError):
        tc.m3(1)
    assert tc.m4() == [tc]
    assert issubclass(tc.m5(), LuaErr)
    with pytest.raises(TypeError):
        tc.m6(1)
    assert calltimes == 4
