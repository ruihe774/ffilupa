from __future__ import absolute_import, unicode_literals

from ffilupa import LuaRuntime
import gc

def _run_gc_test(run_test):
    gc.collect()
    old_count = len(gc.get_objects())
    i = None
    for i in range(100):
        run_test()
    del i
    gc.collect()
    new_count = len(gc.get_objects())
    assert old_count == new_count

def test_runtime_cleanup():
    def run_test():
        lua = LuaRuntime()
        lua_table = lua.eval('{1,2,3,4}')
        del lua
        assert 1 == lua_table[1]

    _run_gc_test(run_test)

def test_pyfunc_refcycle():
    def make_refcycle():
        def use_runtime():
            return lua.eval('1+1')

        lua = LuaRuntime()
        lua.globals()['use_runtime'] = use_runtime
        assert 2 == lua.eval('use_runtime()')

    _run_gc_test(make_refcycle)
