# -*- coding: utf-8 -*-

from __future__ import absolute_import

import threading
import operator
import unittest
import time
import sys
import gc

import ffilupa as lupa

IS_PYTHON3 = sys.version_info[0] >= 3

try:
    _next = next
except NameError:
    def _next(o):
        return o.next()

unicode_type = type(IS_PYTHON3 and 'abc' or 'abc'.decode('ASCII'))


class SetupLuaRuntimeMixin(object):
    lua_runtime_kwargs = {}

    def setUp(self):
        self.lua = lupa.LuaRuntime(**self.lua_runtime_kwargs)

    def tearDown(self):
        self.lua = None
        gc.collect()


class TestLuaRuntimeRefcounting(unittest.TestCase):
    def _run_gc_test(self, run_test):
        run_test()
        gc.collect()
        old_count = len(gc.get_objects())
        i = None
        for i in range(100):
            run_test()
        del i
        gc.collect()
        new_count = len(gc.get_objects())
        self.assertEqual(old_count, new_count)

    def test_runtime_cleanup(self):
        def run_test():
            lua = lupa.LuaRuntime()
            lua_table = lua.eval('{1,2,3,4}')
            del lua
            self.assertEqual(1, lua_table[1])

        self._run_gc_test(run_test)

    def test_pyfunc_refcycle(self):
        def make_refcycle():
            def use_runtime():
                return lua.eval('1+1')

            lua = lupa.LuaRuntime()
            lua._G['use_runtime'] = use_runtime
            self.assertEqual(2, lua.eval('use_runtime()'))

        self._run_gc_test(make_refcycle)


class TestLuaRuntime(SetupLuaRuntimeMixin, unittest.TestCase):
    def test_eval(self):
        self.assertEqual(2, self.lua.eval('1+1'))

    def test_eval_multi(self):
        self.assertEqual((1,2,3), self.lua.eval('1,2,3'))

    def test_eval_args(self):
        self.assertEqual(2, self.lua.eval('...', 2))

    def test_eval_args_multi(self):
        self.assertEqual((1, 2, 3), self.lua.eval('...', 1, 2, 3))

    def test_eval_error(self):
        self.assertRaises(lupa.LuaError, self.lua.eval, '<INVALIDCODE>')

    def test_eval_error_cleanup(self):
        self.assertEqual(2, self.lua.eval('1+1'))
        self.assertRaises(lupa.LuaError, self.lua.eval, '<INVALIDCODE>')
        self.assertEqual(2, self.lua.eval('1+1'))
        self.assertRaises(lupa.LuaError, self.lua.eval, '<INVALIDCODE>')
        self.assertEqual(2, self.lua.eval('1+1'))
        self.assertEqual(2, self.lua.eval('1+1'))

    def test_eval_error_message_decoding(self):
        try:
            self.lua.eval('require "UNKNOWNöMODULEäNAME"')
        except lupa.LuaError:
            error = (IS_PYTHON3 and '%s' or '%s'.decode('ASCII')) % sys.exc_info()[1]
        else:
            self.fail('expected error not raised')
        expected_message = 'module \'UNKNOWNöMODULEäNAME\' not found'
        if not IS_PYTHON3:
            expected_message = expected_message.decode('UTF-8')
        self.assertTrue(expected_message in error,
                        '"%s" not found in "%s"' % (expected_message, error))

    def test_execute(self):
        self.assertEqual(2, self.lua.execute('return 1+1'))

    def test_execute_function(self):
        self.assertEqual(3, self.lua.execute('f = function(i) return i+1 end; return f(2)'))

    def test_execute_tostring_function(self):
        self.assertEqual('function', self.lua.execute('f = function(i) return i+1 end; return tostring(f)')[:8])

    def test_execute_args(self):
        self.assertEqual(2, self.lua.execute('return ...', 2))

    def test_execute_args_multi(self):
        self.assertEqual((1, 2, 3), self.lua.execute('return ...', 1, 2, 3))

    def test_function(self):
        function = self.lua.eval('function() return 1+1 end')
        self.assertNotEqual(None, function)
        self.assertEqual(2, function())

    def test_multiple_functions(self):
        function1 = self.lua.eval('function() return 0+1 end')
        function2 = self.lua.eval('function() return 1+1 end')
        self.assertEqual(1, function1())
        self.assertEqual(2, function2())
        function3 = self.lua.eval('function() return 1+2 end')
        self.assertEqual(3, function3())
        self.assertEqual(2, function2())
        self.assertEqual(1, function1())

    def test_recursive_function(self):
        fac = self.lua.execute('''\
        function fac(i)
            if i <= 1
                then return 1
                else return i * fac(i-1)
            end
        end
        return fac
        ''')
        self.assertNotEqual(None, fac)
        self.assertEqual(6,       fac(3))
        self.assertEqual(3628800, fac(10))

    def test_double_recursive_function(self):
        func_code = '''\
        function calc(i)
            if i > 2
                then return calc(i-1) + calc(i-2) + 1
                else return 1
            end
        end
        return calc
        '''
        calc = self.lua.execute(func_code)
        self.assertNotEqual(None, calc)
        self.assertEqual(3,     calc(3))
        self.assertEqual(109,   calc(10))
        self.assertEqual(13529, calc(20))

    def test_double_recursive_function_pycallback(self):
        func_code = '''\
        function calc(pyfunc, i)
            if i > 2
                then return pyfunc(i) + calc(pyfunc, i-1) + calc(pyfunc, i-2) + 1
                else return 1
            end
        end
        return calc
        '''
        def pycallback(i):
            return i**2

        calc = self.lua.execute(func_code)

        self.assertNotEqual(None, calc)
        self.assertEqual(12,     calc(pycallback, 3))
        self.assertEqual(1342,   calc(pycallback, 10))
        self.assertEqual(185925, calc(pycallback, 20))

    def test_none(self):
        function = self.lua.eval('function() return python.none end')
        self.assertEqual(None, function())

    def test_pybuiltins(self):
        function = self.lua.eval('function() return python.builtins end')
        try:
            import __builtin__ as builtins
        except ImportError:
            import builtins
        self.assertEqual(builtins, function())

    def test_call_none(self):
        self.assertRaises(TypeError, self.lua.eval, 'python.none()')

    def test_call_non_callable(self):
        func = self.lua.eval('function(x) CALLED = 99; return x() end')
        self.assertRaises(TypeError, func, object())
        self.assertEqual(99, self.lua.eval('CALLED'))

    def test_call_str(self):
        self.assertEqual("test-None", self.lua.eval('"test-" .. tostring(python.none)'))

    def test_call_str_py(self):
        function = self.lua.eval('function(x) return "test-" .. tostring(x) end')
        self.assertEqual("test-nil", function(None))
        self.assertEqual("test-1.5", function(1.5))

    def test_call_str_class(self):
        called = [False]
        class test(object):
            def __str__(self):
                called[0] = True
                return 'STR!!'

        function = self.lua.eval('function(x) return "test-" .. tostring(x) end')
        self.assertEqual("test-STR!!", function(test()))
        self.assertEqual(True, called[0])

    def test_python_eval(self):
        eval = self.lua.eval('function() return python.eval end')()
        self.assertEqual(2, eval('1+1'))
        self.assertEqual(2, self.lua.eval('python.eval("1+1")'))

    def test_len_table_array(self):
        table = self.lua.eval('{1,2,3,4,5}')
        self.assertEqual(5, len(table))

    def test_len_table_dict(self):
        table = self.lua.eval('{a=1, b=2, c=3}')
        self.assertEqual(0, len(table)) # as returned by Lua's "#" operator

    def test_table_delattr(self):
        table = self.lua.eval('{a=1, b=2, c=3}')
        self.assertTrue('a' in table)
        del table.a
        self.assertFalse('a' in table)

    def test_table_delitem(self):
        table = self.lua.eval('{a=1, b=2, c=3}')
        self.assertTrue('c' in table)
        del table['c']
        self.assertFalse('c' in table)

    def test_table_delitem_special(self):
        table = self.lua.eval('{a=1, b=2, c=3, __attr__=4}')
        self.assertTrue('__attr__' in table)
        del table['__attr__']
        self.assertFalse('__attr__' in table)

    def test_len_table(self):
        table = self.lua.eval('{1,2,3,4, a=1, b=2, c=3}')
        self.assertEqual(4, len(table))  # as returned by Lua's "#" operator

    def test_iter_table(self):
        table = self.lua.eval('{2,3,4,5,6}')
        self.assertEqual([1,2,3,4,5], list(table))

    def test_iter_table_list_repeat(self):
        table = self.lua.eval('{2,3,4,5,6}')
        self.assertEqual([1,2,3,4,5], list(table))  # 1
        self.assertEqual([1,2,3,4,5], list(table))  # 2
        self.assertEqual([1,2,3,4,5], list(table))  # 3

    def test_iter_array_table_values(self):
        table = self.lua.eval('{2,3,4,5,6}')
        self.assertEqual([2,3,4,5,6], list(table.values()))

    def test_iter_array_table_repeat(self):
        table = self.lua.eval('{2,3,4,5,6}')
        self.assertEqual([2,3,4,5,6], list(table.values()))  # 1
        self.assertEqual([2,3,4,5,6], list(table.values()))  # 2
        self.assertEqual([2,3,4,5,6], list(table.values()))  # 3

    def test_iter_multiple_tables(self):
        count = 10
        table_values = [iter(self.lua.eval('{%s}' % ','.join(map(str, range(2, count+2)))).values())
                        for _ in range(4)]

        # round robin
        l = [[] for _ in range(count)]
        for sublist in l:
            for table in table_values:
                sublist.append(_next(table))

        self.assertEqual([[i]*len(table_values) for i in range(2, count+2)], l)

    def test_iter_table_repeat(self):
        count = 10
        table_values = [iter(self.lua.eval('{%s}' % ','.join(map(str, range(2, count+2)))).values())
                        for _ in range(4)]

        # one table after the other
        l = [[] for _ in range(count)]
        for table in table_values:
            for sublist in l:
                sublist.append(_next(table))

        self.assertEqual([[i]*len(table_values) for i in range(2,count+2)], l)

    def test_iter_table_refcounting(self):
        lua_func = self.lua.eval('''
            function ()
              local t = {}
              t.foo = 'bar'
              t.hello = 'world'
              return t
            end
        ''')
        table = lua_func()
        for _ in range(10000):
            list(table.items())

    def test_iter_table_mapping(self):
        keys = list('abcdefg')
        table = self.lua.eval('{%s}' % ','.join('%s=%d' % (c, i) for i, c in enumerate(keys)))
        l = list(table)
        l.sort()
        self.assertEqual(keys, l)

    def test_iter_table_mapping_int_keys(self):
        table = self.lua.eval('{%s}' % ','.join('[%d]=%d' % (i, -i) for i in range(10)))
        l = list(table)
        l.sort()
        self.assertEqual(list(range(10)), l)

    def test_iter_table_keys(self):
        keys = list('abcdefg')
        table = self.lua.eval('{%s}' % ','.join('%s=%d' % (c, i) for i, c in enumerate(keys)))
        l = list(table.keys())
        l.sort()
        self.assertEqual(keys, l)

    def test_iter_table_keys_int_keys(self):
        table = self.lua.eval('{%s}' % ','.join('[%d]=%d' % (i, -i) for i in range(10)))
        l = list(table.keys())
        l.sort()
        self.assertEqual(list(range(10)), l)

    def test_iter_table_values(self):
        keys = list('abcdefg')
        table = self.lua.eval('{%s}' % ','.join('%s=%d' % (c, i) for i, c in enumerate(keys)))
        l = list(table.values())
        l.sort()
        self.assertEqual(list(range(len(keys))), l)

    def test_iter_table_values_int_keys(self):
        table = self.lua.eval('{%s}' % ','.join('[%d]=%d' % (i, -i) for i in range(10)))
        l = list(table.values())
        l.sort()
        self.assertEqual(list(range(-9,1)), l)

    def test_iter_table_items(self):
        keys = list('abcdefg')
        table = self.lua.eval('{%s}' % ','.join('%s=%d' % (c, i) for i, c in enumerate(keys)))
        l = list(table.items())
        l.sort()
        self.assertEqual(list(zip(keys,range(len(keys)))), l)

    def test_iter_table_items_int_keys(self):
        table = self.lua.eval('{%s}' % ','.join('[%d]=%d' % (i, -i) for i in range(10)))
        l = list(table.items())
        l.sort()
        self.assertEqual(list(zip(range(10), range(0,-10,-1))), l)

    def test_iter_table_values_mixed(self):
        keys = list('abcdefg')
        table = self.lua.eval('{98, 99; %s}' % ','.join('%s=%d' % (c, i) for i, c in enumerate(keys)))
        l = list(table.values())
        l.sort()
        self.assertEqual(list(range(len(keys))) + [98, 99], l)

    def test_error_iter_number(self):
        func = self.lua.eval('1')
        self.assertRaises(TypeError, list, func)

    def test_error_iter_function(self):
        func = self.lua.eval('function() return 1 end')
        self.assertRaises(TypeError, list, func)

    def test_string_values(self):
        function = self.lua.eval('function(s) return s .. "abc" end')
        self.assertEqual('ABCabc', function('ABC'))

    def test_int_values(self):
        function = self.lua.eval('function(i) return i + 5 end')
        self.assertEqual(3+5, function(3))

    def test_long_values(self):
        try:
            _long = long
        except NameError:
            _long = int
        function = self.lua.eval('function(i) return i + 5 end')
        self.assertEqual(3+5, function(_long(3)))

    def test_float_values(self):
        function = self.lua.eval('function(i) return i + 5 end')
        self.assertEqual(float(3)+5, function(float(3)))

    def test_str_function(self):
        func = self.lua.eval('function() return 1 end')
        self.assertEqual('<ffilupa.py_from_lua.LuaFunction object at', repr(func)[:42])

    def test_str_table(self):
        table = self.lua.eval('{}')
        self.assertEqual('<ffilupa.py_from_lua.LuaTable object at', repr(table)[:39])

    def test_create_table_args(self):
        table = self.lua.table(1,2,3,4,5,6)
        self.assertEqual(1, table[1])
        self.assertEqual(3, table[3])
        self.assertEqual(6, table[6])

        self.assertEqual(6, len(table))

    def test_create_table_kwargs(self):
        table = self.lua.table(a=1, b=20, c=300)
        self.assertEqual(  1, table['a'])
        self.assertEqual( 20, table['b'])
        self.assertEqual(300, table['c'])

        self.assertEqual(0, len(table))

    def test_create_table_args_kwargs(self):
        table = self.lua.table(1,2,3,4,5,6, a=100, b=200, c=300)
        self.assertEqual(1, table[1])
        self.assertEqual(3, table[3])
        self.assertEqual(6, table[6])

        self.assertEqual(100, table['a'])
        self.assertEqual(200, table['b'])
        self.assertEqual(300, table['c'])

        self.assertEqual(6, len(table))

    def test_table_from_dict(self):
        table = self.lua.table_from({"foo": 1, "bar": 20, "baz": "spam"})
        self.assertEqual(     1, table['foo'])
        self.assertEqual(    20, table['bar'])
        self.assertEqual("spam", table['baz'])

        self.assertEqual(0, len(table))

    def test_table_from_int_keys(self):
        table = self.lua.table_from({1: 5, 2: 10, "foo": "bar"})
        self.assertEqual(5, table[1])
        self.assertEqual(10, table[2])
        self.assertEqual("bar", table["foo"])

        self.assertEqual(2, len(table))

    # def test_table_from_obj_keys(self):
    #     key = object()
    #     table = self.lua.table_from({key: "foo"})
    #     self.assertEqual("foo", table[key])
    #
    #     self.assertEqual(0, len(table))

    def test_table_from_list(self):
        table = self.lua.table_from([1,2,5,6])
        self.assertEqual(1, table[1])
        self.assertEqual(2, table[2])
        self.assertEqual(5, table[3])
        self.assertEqual(6, table[4])

        self.assertEqual(4, len(table))

    def test_table_from_iterable(self):
        it = (x for x in range(3))
        table = self.lua.table_from(it)
        self.assertEqual(0, table[1])
        self.assertEqual(1, table[2])
        self.assertEqual(2, table[3])

        self.assertEqual(3, len(table))

    def test_table_from_multiple_dicts(self):
        table = self.lua.table_from({"a": 1, "b": 2}, {"c": 3, "b": 4})
        self.assertEqual(1, table["a"])
        self.assertEqual(4, table["b"])
        self.assertEqual(3, table["c"])

        self.assertEqual(0, len(table))

    def test_table_from_dicts_and_lists(self):
        dct, lst = {"a": 1, "b": 2}, ["foo", "bar"]
        for args in [[dct, lst], [lst, dct]]:
            table = self.lua.table_from(*args)
            self.assertEqual(1, table["a"])
            self.assertEqual(2, table["b"])
            self.assertEqual("foo", table[1])
            self.assertEqual("bar", table[2])

            self.assertEqual(2, len(table))

    def test_table_from_multiple_lists(self):
        table = self.lua.table_from(["foo", "bar"], ["egg", "spam"])
        self.assertEqual("foo", table[1])
        self.assertEqual("bar", table[2])
        self.assertEqual("egg", table[3])
        self.assertEqual("spam", table[4])

        self.assertEqual(4, len(table))

    def test_table_from_bad(self):
        self.assertRaises(TypeError, self.lua.table_from, 5)
        self.assertRaises(TypeError, self.lua.table_from, None)
        self.assertRaises(TypeError, self.lua.table_from, {"a": 5}, 123)

    # def test_table_from_nested(self):
    #     table = self.lua.table_from({"obj": {"foo": "bar"}})
    #     lua_type = self.lua.eval("type")
    #     self.assertEqual(lua_type(table["obj"]), "table")

    def test_table_from_table(self):
        table1 = self.lua.eval("{3, 4, foo='bar'}")
        table2 = self.lua.table_from(table1)

        self.assertEqual(3, table2[1])
        self.assertEqual(4, table2[2])
        self.assertEqual("bar", table2["foo"])

        # data should be copied
        table2["foo"] = "spam"
        self.assertEqual("spam", table2["foo"])
        self.assertEqual("bar", table1["foo"])

    def test_table_from_table_iter(self):
        table1 = self.lua.eval("{3, 4, foo='bar'}")
        table2 = self.lua.table_from(table1.keys())

        self.assertEqual(len(table2), 3)
        self.assertEqual(list(table2.keys()), [1, 2, 3])
        self.assertEqual(set(table2.values()), set([1, 2, "foo"]))

    def test_table_from_table_iter_indirect(self):
        table1 = self.lua.eval("{3, 4, foo='bar'}")
        table2 = self.lua.table_from(k for k in table1.keys())

        self.assertEqual(len(table2), 3)
        self.assertEqual(list(table2.keys()), [1, 2, 3])
        self.assertEqual(set(table2.values()), set([1, 2, "foo"]))

    def test_table_from_generator_calling_lua_functions(self):
        func = self.lua.eval("function (obj) return obj end")
        table = self.lua.table_from(func(obj) for obj in ["foo", "bar"])

        self.assertEqual(len(table), 2)
        self.assertEqual(set(table.values()), set(["foo", "bar"]))

    def test_table_contains(self):
        table = self.lua.eval("{foo=5}")
        self.assertTrue("foo" in table)
        self.assertFalse("bar" in table)
        self.assertFalse(5 in table)

    def test_getattr(self):
        stringlib = self.lua.eval('string')
        self.assertEqual('abc', stringlib.lower('ABC'))

    def test_getitem(self):
        stringlib = self.lua.eval('string')
        self.assertEqual('abc', stringlib['lower']('ABC'))

    def test_getattr_table(self):
        table = self.lua.eval('{ const={ name="Pi", value=3.1415927 }, const2={ name="light speed", value=3e8 }, val=1 }')
        self.assertEqual(1, table.val)
        self.assertEqual('Pi', table.const.name)
        self.assertEqual('light speed', table.const2.name)
        self.assertEqual(3e8, table.const2.value)

    def test_getitem_table(self):
        table = self.lua.eval('{ const={ name="Pi", value=3.1415927 }, const2={ name="light speed", value=3e8 }, val=1 }')
        self.assertEqual(1, table['val'])
        self.assertEqual('Pi', table['const']['name'])
        self.assertEqual('light speed', table['const2']['name'])
        self.assertEqual(3e8, table['const2']['value'])

    def test_getitem_array(self):
        table = self.lua.eval('{1,2,3,4,5,6,7,8,9}')
        self.assertEqual(1, table[1])
        self.assertEqual(5, table[5])
        self.assertEqual(9, len(table))

    def test_setitem_array(self):
        table = self.lua.eval('{1,2,3,4,5,6,7,8,9}')
        self.assertEqual(1, table[1])
        table[1] = 0
        self.assertEqual(0, table[1])
        self.assertEqual(2, table[2])
        self.assertEqual(9, len(table))

    def test_setattr_table(self):
        table = self.lua.eval('{ const={ name="Pi", value=3.1415927 }, const2={ name="light speed", value=3e8 }, val=1 }')

        self.assertEqual(1, table.val)
        table.val = 2
        self.assertEqual(2, table.val)

        self.assertEqual('Pi', table.const.name)
        table.const.name = 'POW'
        self.assertEqual('POW', table.const.name)

        table_const_name = self.lua.eval('function(t) return t.const.name end')
        self.assertEqual('POW', table_const_name(table))

    def test_setitem_table(self):
        table = self.lua.eval('{ const={ name="Pi", value=3.1415927 }, const2={ name="light speed", value=3e8 }, val=1 }')

        self.assertEqual(1, table.val)
        table['val'] = 2
        self.assertEqual(2, table.val)

        get_val = self.lua.eval('function(t) return t.val end')
        self.assertEqual(2, get_val(table))

        self.assertEqual('Pi', table.const.name)
        table['const']['name'] = 'POW'
        self.assertEqual('POW', table.const.name)

        get_table_const_name = self.lua.eval('function(t) return t.const.name end')
        self.assertEqual('POW', get_table_const_name(table))

    def test_pygetitem(self):
        lua_func = self.lua.eval('function(x) return x.ATTR end')
        self.assertEqual(123, lua_func({'ATTR': 123}))

    def test_pysetitem(self):
        lua_func = self.lua.eval('function(x) x.ATTR = 123 end')
        d = {'ATTR': 321}
        self.assertEqual(321, d['ATTR'])
        lua_func(d)
        self.assertEqual(123, d['ATTR'])

    def test_pygetattr(self):
        lua_func = self.lua.eval('function(x) return x.ATTR end')
        class test(object):
            def __init__(self):
                self.ATTR = 5
        self.assertEqual(test().ATTR, lua_func(test()))

    def test_pysetattr(self):
        lua_func = self.lua.eval('function(x) x.ATTR = 123 end')
        class test(object):
            def __init__(self):
                self.ATTR = 5
        t = test()
        self.assertEqual(5, t.ATTR)
        lua_func(t)
        self.assertEqual(123, t.ATTR)

    def test_pygetattr_function(self):
        lua_func = self.lua.eval('function(x) x.ATTR = 123 end')
        def test(): pass
        lua_func(test)
        self.assertEqual(123, test.ATTR)

    def test_pysetattr_function(self):
        lua_func = self.lua.eval('function(x) x.ATTR = 123 end')
        def test(): pass
        lua_func(test)
        self.assertEqual(123, test.ATTR)

    def test_globals(self):
        lua_globals = self.lua.globals()
        self.assertNotEqual(None, lua_globals.table.unpack)

    def test_globals_attrs_call(self):
        lua_globals = self.lua.globals()
        self.assertNotEqual(None, lua_globals.string)
        self.assertEqual('test', lua_globals.string.lower("TEST"))

    def test_require(self):
        stringlib = self.lua.require('string')
        self.assertNotEqual(None, stringlib)
        self.assertNotEqual(None, stringlib.char)

    def test_libraries(self):
        libraries = self.lua.eval('{require, table, io, os, math, string, debug}')
        self.assertEqual(7, len(libraries))
        self.assertTrue(None not in libraries)

    def test_callable_values(self):
        function = self.lua.eval('function(f) return f() + 5 end')
        def test():
            return 3
        self.assertEqual(3+5, function(test))

    def test_callable_values_pass_through(self):
        function = self.lua.eval('function(f, n) return f(n) + 5 end')
        def test(n):
            return n
        self.assertEqual(2+5, function(test, 2))

    def test_callable_passthrough(self):
        passthrough = self.lua.eval('function(f) f(); return f end')
        called = [False]
        def test():
            called[0] = True
        self.assertEqual(test, passthrough(test))
        self.assertEqual([True], called)

    def test_reraise(self):
        function = self.lua.eval('function(f) return f() + 5 end')
        def test():
            raise ValueError("huhu")
        self.assertRaises(ValueError, function, test)

    def test_reraise_pcall(self):
        exception = Exception('test')
        def py_function():
            raise exception
        function = self.lua.eval(
            'function(p) local r, err = pcall(p); return r, err end'
        )
        self.assertEqual(
            function(py_function),
            (False, exception)
        )

    def test_lua_error_after_intercepted_python_exception(self):
        function = self.lua.eval('''
            function(p)
                pcall(p)
                print(a.b);
            end
        ''')
        self.assertRaises(
            lupa.LuaError,
            function,
            lambda: 5/0,
        )

    def test_lua_type(self):
        x = self.lua.eval('{}')
        self.assertEqual('table', lupa.lua_type(x))

        x = self.lua.eval('function() return 1 end')
        self.assertEqual('function', lupa.lua_type(x))

        x = self.lua.eval('function() coroutine.yield(1) end')
        self.assertEqual('function', lupa.lua_type(x))
        self.assertEqual('thread', lupa.lua_type(x.coroutine()))

        self.assertEqual(None, lupa.lua_type(1))
        self.assertEqual(None, lupa.lua_type(1.1))
        self.assertEqual(None, lupa.lua_type('abc'))
        self.assertEqual(None, lupa.lua_type({}))
        self.assertEqual(None, lupa.lua_type([]))
        self.assertEqual(None, lupa.lua_type(lupa))
        self.assertEqual(None, lupa.lua_type(lupa.lua_type))

    def test_call_from_coroutine(self):
        lua = self.lua
        def f(*args, **kwargs):
            return lua.eval('tostring(...)', args)

        create_thread = lua.eval('''
        function(func)
           local thread = coroutine.create(function()
               coroutine.yield(func());
           end);
           return thread;
        end''')
        t = create_thread(f)()
        self.assertEqual(lua.eval('coroutine.resume(...)', t), (True, '()'))

    def test_call_from_coroutine2(self):
        lua = self.lua
        def f(*args, **kwargs):
            return lua.eval('tostring(...)', args)

        t = lua.eval('''
           function(f)
             coroutine.yield(f());
           end
        ''').coroutine(f)
        self.assertEqual(lua.eval('coroutine.resume(...)', t, f), (True, '()'))

    def test_compile(self):
        lua_func = self.lua.compile('return 1 + 2')
        self.assertEqual(lua_func(), 3)
        with self.assertRaises(lupa.LuaSyntaxError) as cm:
            self.lua.compile('function awd()')
        self.assertTrue(cm.exception.err_msg == 'python:1: \'end\' expected near <eof>' or
                        cm.exception.err_msg == 'python:1: \'end\' expected near \'<eof>\'')


class TestAttributesNoAutoEncoding(SetupLuaRuntimeMixin, unittest.TestCase):
    lua_runtime_kwargs = {'autodecode': False}

    def test_pygetitem(self):
        lua_func = self.lua.eval('function(x) return x.ATTR end')
        self.assertEqual(123, lua_func({b'ATTR': 123}))

    def test_pysetitem(self):
        lua_func = self.lua.eval('function(x) x.ATTR = 123 end')
        d = {b'ATTR': 321}
        self.assertEqual(321, d[b'ATTR'])
        lua_func(d)
        self.assertEqual(123, d[b'ATTR'])

    def test_pygetattr(self):
        lua_func = self.lua.eval('function(x) return x.ATTR end')
        class test(object):
            def __init__(self):
                self.ATTR = 5
        self.assertEqual(test().ATTR, lua_func(test()))

    def test_pysetattr(self):
        lua_func = self.lua.eval('function(x) x.ATTR = 123 end')
        class test(object):
            def __init__(self):
                self.ATTR = 5
        t = test()
        self.assertEqual(5, t.ATTR)
        lua_func(t)
        self.assertEqual(123, t.ATTR)


class TestStrNoAutoEncoding(SetupLuaRuntimeMixin, unittest.TestCase):
    lua_runtime_kwargs = {'autodecode': False}

    def test_call_str(self):
        self.assertEqual(b"test-None", self.lua.eval('"test-" .. tostring(python.none)'))

    def test_call_str_py(self):
        function = self.lua.eval('function(x) return "test-" .. tostring(x) end')
        self.assertEqual(b"test-nil", function(None))
        self.assertEqual(b"test-1.5", function(1.5))

    def test_call_str_class(self):
        called = [False]
        class test(object):
            def __str__(self):
                called[0] = True
                return 'STR!!'

        function = self.lua.eval('function(x) return "test-" .. tostring(x) end')
        self.assertEqual(b"test-STR!!", function(test()))
        self.assertEqual(True, called[0])


class TestPythonObjectsInLua(SetupLuaRuntimeMixin, unittest.TestCase):
    def test_explicit_python_function(self):
        lua_func = self.lua.eval(
            'function(func)'
            ' t = {1, 5, 2, 4, 3};'
            ' table.sort(t, python.as_function(func));'
            ' return t end')

        def compare(a, b):
            return a < b
        self.assertEqual([1, 2, 3, 4, 5], list(lua_func(compare)))

    def test_type_conversion(self):
        lua_type = self.lua.eval('type')
        self.assertEqual('number', lua_type(1))
        self.assertEqual('string', lua_type("test"))

    def test_pyobject_wrapping_callable(self):
        lua_type = self.lua.eval('type')
        lua_get_call = self.lua.eval('function(obj) return getmetatable(obj).__call end')

        class Callable(object):
            def __call__(self): pass
            def __getitem__(self, item): pass

        self.assertEqual('userdata', lua_type(Callable()))
        self.assertNotEqual(None, lua_get_call(Callable()))

    def test_pyobject_wrapping_getitem(self):
        lua_type = self.lua.eval('type')
        lua_get_index = self.lua.eval('function(obj) return getmetatable(obj).__index end')

        class GetItem(object):
            def __getitem__(self, item): pass

        self.assertEqual('userdata', lua_type(GetItem()))
        self.assertNotEqual(None, lua_get_index(GetItem()))

    def test_pyobject_wrapping_getattr(self):
        lua_type = self.lua.eval('type')
        lua_get_index = self.lua.eval('function(obj) return getmetatable(obj).__index end')

        class GetAttr(object):
            pass

        self.assertEqual('userdata', lua_type(GetAttr()))
        self.assertNotEqual(None, lua_get_index(GetAttr()))

    def test_pylist(self):
        getitem = self.lua.eval('function(L, i) return L[i] end')
        self.assertEqual(3, getitem([1,2,3], 2))

    def test_python_enumerate_list(self):
        values = self.lua.eval('''
            function(L)
                local t = {}
                for index, value in pairs(L) do
                    t[ index+1 ] = value
                end
                return t
            end
        ''')
        self.assertEqual([1,2,3], list(values([1,2,3]).values()))

    def test_python_iter_dict_items(self):
        values = self.lua.eval('''
            function(d)
                local t = {}
                for key, value in pairs(d) do
                    t[key] = value
                end
                return t
            end
        ''')
        table = values(lupa.as_attrgetter(dict(a=1, b=2, c=3)))
        self.assertEqual(1, table['a'])
        self.assertEqual(2, table['b'])
        self.assertEqual(3, table['c'])

    def test_python_iter_iterator(self):
        values = self.lua.eval('''
            function(L)
                local t = {}
                local i = 1
                for _, value in pairs(L) do
                    t[i] = value
                    i = i+1
                end
                return t
            end
        ''')
        self.assertEqual([3, 2, 1], list(values(reversed([1, 2, 3])).values()))


class TestLuaCoroutines(SetupLuaRuntimeMixin, unittest.TestCase):
    def test_coroutine_object(self):
        f = self.lua.eval("function(N) coroutine.yield(N) end")
        gen = f.coroutine(5)
        self.assertRaises(AttributeError, getattr, gen, '__setitem__')
        self.assertRaises(AttributeError, getattr, gen, 'no_such_attribute')

        self.assertTrue(hasattr(gen.send, '__call__'))

        self.assertRaises(TypeError, operator.itemgetter(1), gen)

    def test_coroutine_iter(self):
        lua_code = '''\
            function(N)
                for i=0,N do
                    if i%2 == 0 then coroutine.yield(0) else coroutine.yield(1) end
                end
            end
        '''
        f = self.lua.eval(lua_code)
        gen = f.coroutine(5)
        self.assertEqual([0,1,0,1,0,1], list(gen))

    def test_coroutine_iter_repeat(self):
        lua_code = '''\
            function(N)
                for i=0,N do
                    if i%2 == 0 then coroutine.yield(0) else coroutine.yield(1) end
                end
            end
        '''
        f = self.lua.eval(lua_code)
        gen = f.coroutine(5)
        self.assertEqual([0,1,0,1,0,1], list(gen))

        gen = f.coroutine(5)
        self.assertEqual([0,1,0,1,0,1], list(gen))

        gen = f.coroutine(5)
        self.assertEqual([0,1,0,1,0,1], list(gen))

    def test_coroutine_create_iter(self):
        lua_code = '''\
        coroutine.create(
            function(N)
                for i=0,N do
                    if i%2 == 0 then coroutine.yield(0) else coroutine.yield(1) end
                end
            end
            )
        '''
        co = self.lua.eval(lua_code)
        gen = co(5)
        self.assertEqual([0,1,0,1,0,1], list(gen))

    def test_coroutine_create_iter_repeat(self):
        lua_code = '''\
        coroutine.create(
            function(N)
                for i=0,N do
                    if i%2 == 0 then coroutine.yield(0) else coroutine.yield(1) end
                end
            end
            )
        '''
        co = self.lua.eval(lua_code)

        gen = co(5)
        self.assertEqual([0,1,0,1,0,1], list(gen))

        gen = co(5)
        self.assertEqual([0,1,0,1,0,1], list(gen))

        gen = co(5)
        self.assertEqual([0,1,0,1,0,1], list(gen))

    def test_coroutine_lua_iter(self):
        lua_code = '''\
        co = coroutine.create(
            function(N)
                for i=0,N do
                    if i%2 == 0 then coroutine.yield(0) else coroutine.yield(1) end
                end
            end
            )
        status, first_value = coroutine.resume(co, 5)
        return co, status, first_value
        '''
        gen, status, first_value = self.lua.execute(lua_code)
        self.assertTrue(status)
        self.assertEqual([0,1,0,1,0,1], [first_value] + list(gen))

    def test_coroutine_lua_iter_independent(self):
        lua_code = '''\
            function f(N)
              for i=0,N do
                  coroutine.yield( i%2 )
              end
            end ;
            co1 = coroutine.create(f) ;
            co2 = coroutine.create(f) ;

            status, first_value = coroutine.resume(co2, 5) ;   -- starting!

            return f, co1, co2, status, first_value
        '''
        f, co, lua_gen, status, first_value = self.lua.execute(lua_code)

        # f
        gen = f.coroutine(5)
        self.assertEqual([0,1,0,1,0,1], list(gen))

        # co
        gen = co(5)
        self.assertEqual([0,1,0,1,0,1], list(gen))
        gen = co(5)
        self.assertEqual([0,1,0,1,0,1], list(gen))

        # lua_gen
        self.assertTrue(status)
        self.assertEqual([0,1,0,1,0,1], [first_value] + list(lua_gen))
        self.assertEqual([], list(lua_gen))

    def test_coroutine_iter_pycall(self):
        lua_code = '''\
        coroutine.create(
            function(pyfunc, N)
                for i=0,N do
                    if pyfunc(i) then coroutine.yield(0) else coroutine.yield(1) end
                end
            end
            )
        '''
        co = self.lua.eval(lua_code)

        def pyfunc(i):
            return i%2 == 0
        gen = co(pyfunc, 5)
        self.assertEqual([0,1,0,1,0,1], list(gen))

    def test_coroutine_send(self):
        lua_code = '''\
            function()
                local i = 0
                while coroutine.yield(i) do i = i+1 end
                return i   -- not i+1 !
            end
        '''
        count = self.lua.eval(lua_code).coroutine()
        result = [count.send(value) for value in ([None] + [True] * 9 + [False])]
        self.assertEqual(list(range(10)) + [9], result)
        self.assertRaises(StopIteration, count.send, True)

    def test_coroutine_send_with_arguments(self):
        lua_code = '''\
            function(N)
                local i = 0
                while coroutine.yield(i) < N do i = i+1 end
                return i   -- not i+1 !
            end
        '''
        count = self.lua.eval(lua_code).coroutine(5)
        result = []
        try:
            result.append(_next(count))
            for value in list(range(10)):
                result.append(count.send(value))
        except StopIteration:
            pass
        else:
            self.assertTrue(False)
        self.assertEqual(list(range(6)) + [5], result)
        self.assertRaises(StopIteration, count.send, True)

    def test_coroutine_status(self):
        lua_code = '''\
        coroutine.create(
            function(N)
                for i=0,N do
                    if i%2 == 0 then coroutine.yield(0) else coroutine.yield(1) end
                end
            end
            )
        '''
        co = self.lua.eval(lua_code)
        self.assertTrue(bool(co)) # 1
        gen = co(1)
        self.assertTrue(bool(gen)) # 2
        self.assertEqual(0, _next(gen))
        self.assertTrue(bool(gen)) # 3
        self.assertEqual(1, _next(gen))
        self.assertTrue(bool(gen)) # 4
        self.assertRaises(StopIteration, _next, gen)
        self.assertFalse(bool(gen)) # 5
        self.assertRaises(StopIteration, _next, gen)
        self.assertRaises(StopIteration, _next, gen)
        self.assertRaises(StopIteration, _next, gen)

    def test_coroutine_terminate_return(self):
        lua_code = '''\
        coroutine.create(
            function(N)
                for i=0,N do
                    if i%2 == 0 then coroutine.yield(0) else coroutine.yield(1) end
                end
                return 99
            end
            )
        '''
        co = self.lua.eval(lua_code)

        self.assertTrue(bool(co)) # 1
        gen = co(1)
        self.assertTrue(bool(gen)) # 2
        self.assertEqual(0, _next(gen))
        self.assertTrue(bool(gen)) # 3
        self.assertEqual(1, _next(gen))
        self.assertTrue(bool(gen)) # 4
        self.assertEqual(99, _next(gen))
        self.assertFalse(bool(gen)) # 5
        self.assertRaises(StopIteration, _next, gen)
        self.assertRaises(StopIteration, _next, gen)
        self.assertRaises(StopIteration, _next, gen)

    def test_coroutine_while_status(self):
        lua_code = '''\
            function(N)
                for i=0,N-1 do
                    if i%2 == 0 then coroutine.yield(0) else coroutine.yield(1) end
                end
                if N < 0 then return nil end
                if N%2 == 0 then return 0 else return 1 end
            end
        '''
        f = self.lua.eval(lua_code)
        gen = f.coroutine(5)
        result = []
        # note: this only works because the generator returns a result
        # after the last yield - otherwise, it would throw
        # StopIteration in the last call
        while gen:
            result.append(_next(gen))
        self.assertEqual([0,1,0,1,0,1], result)


class TestLuaCoroutinesWithDebugHooks(SetupLuaRuntimeMixin, unittest.TestCase):

    def _enable_hook(self):
        self.lua.execute('''
            steps = 0
            debug.sethook(function () steps = steps + 1 end, '', 1)
        ''')

    def test_coroutine_yields_callback_debug_hook(self):
        self.lua.execute('''
            func = function()
                coroutine.yield(function() return 123 end)
            end
        ''')
        def _check():
            coro = self.lua.eval('func').coroutine()
            cb = next(coro)
            self.assertEqual(cb(), 123)

        # yielding a callback should work without a debug hook
        _check()

        # it should keep working after a debug hook is added
        self._enable_hook()
        _check()

    def test_coroutine_yields_callback_debug_hook_nowrap(self):
        resume = self.lua.eval("coroutine.resume")
        self.lua.execute('''
            func = function()
                coroutine.yield(function() return 123 end)
            end
        ''')
        def _check():
            coro = self.lua.eval('func').coroutine()
            ok, cb = resume(coro)
            self.assertEqual(ok, True)
            self.assertEqual(cb(), 123)

        # yielding a callback should work without a debug hook
        _check()

        # it should keep working after a debug hook is added
        self._enable_hook()
        _check()

    def test_coroutine_sets_callback_debug_hook(self):
        self.lua.execute('''
            func = function(dct)
                dct['cb'] = function() return 123 end
                coroutine.yield()
            end
        ''')
        def _check(dct):
            coro = self.lua.eval('func').coroutine(dct)
            next(coro)
            cb = dct['cb']
            self.assertEqual(cb(), 123)

        # sending a callback should work without a debug hook
        _check({})

        # enable debug hook and try again
        self._enable_hook()

        # it works with a Lua table wrapper
        _check(self.lua.table_from({}))

        # FIXME: but it fails with a regular dict
        # _check({})

    def test_coroutine_sets_callback_debug_hook_nowrap(self):
        resume = self.lua.eval("coroutine.resume")
        self.lua.execute('''
            func = function(dct)
                dct['cb'] = function() return 123 end
                coroutine.yield()
            end
        ''')
        def _check():
            dct = {}
            coro = self.lua.eval('func').coroutine()
            resume(coro, dct)  # send initial value
            resume(coro)
            cb = dct['cb']
            self.assertEqual(cb(), 123)

        # sending a callback should work without a debug hook
        _check()

        # enable debug hook and try again
        self._enable_hook()
        _check()


class TestLuaApplications(unittest.TestCase):
    def tearDown(self):
        gc.collect()

    def test_mandelbrot(self):
        # copied from Computer Language Benchmarks Game
        code = '''\
function(N)
    local char, unpack = string.char, table.unpack
    local result = ""
    local M, ba, bb, buf = 2/N, 2^(N%8+1)-1, 2^(8-N%8), {}
    for y=0,N-1 do
        local Ci, b, p = y*M-1, 1, 0
        for x=0,N-1 do
            local Cr = x*M-1.5
            local Zr, Zi, Zrq, Ziq = Cr, Ci, Cr*Cr, Ci*Ci
            b = b + b
            for i=1,49 do
                Zi = Zr*Zi*2 + Ci
                Zr = Zrq-Ziq + Cr
                Ziq = Zi*Zi
                Zrq = Zr*Zr
                if Zrq+Ziq > 4.0 then b = b + 1; break; end
            end
            if b >= 256 then p = p + 1; buf[p] = 511 - b; b = 1; end
        end
        if b ~= 1 then p = p + 1; buf[p] = (ba-b)*bb; end
        result = result .. char(unpack(buf, 1, p))
    end
    return result
end
'''

        lua = lupa.LuaRuntime(autodecode=False)
        lua_mandelbrot = lua.eval(code)

        image_size = 128
        result_bytes = lua_mandelbrot(image_size)
        self.assertEqual(type(result_bytes), type(''.encode('ASCII')))
        self.assertEqual(image_size*image_size//8, len(result_bytes))

        # if we have PIL, check that it can read the image
        ## try:
        ##     import Image
        ## except ImportError:
        ##     pass
        ## else:
        ##     image = Image.fromstring('1', (image_size, image_size), result_bytes)
        ##     image.show()


class TestLuaRuntimeEncoding(unittest.TestCase):
    def tearDown(self):
        gc.collect()

    test_string = '"abcüöä"'
    if not IS_PYTHON3:
        test_string = test_string.decode('UTF-8')

    def _encoding_test(self, encoding, expected_length):
        lua = lupa.LuaRuntime(encoding=encoding)

        self.assertEqual(unicode_type,
                         type(lua.eval(self.test_string)))

        self.assertEqual(self.test_string[1:-1],
                         lua.eval(self.test_string))

        self.assertEqual(expected_length,
                         lua.eval('string.len(%s)' % self.test_string))

    def test_utf8(self):
        self._encoding_test('UTF-8', 9)

    def test_latin9(self):
        self._encoding_test('ISO-8859-15', 6)

    def test_stringlib_utf8(self):
        lua = lupa.LuaRuntime(encoding='UTF-8')
        stringlib = lua.eval('string')
        self.assertEqual('abc', stringlib.lower('ABC'))

    def test_stringlib_no_encoding(self):
        lua = lupa.LuaRuntime(autodecode=False)
        stringlib = lua.eval('string')
        self.assertEqual('abc'.encode('ASCII'), stringlib.lower('ABC'.encode('ASCII')))


class TestMultipleLuaRuntimes(unittest.TestCase):
    def tearDown(self):
        gc.collect()

    def test_multiple_runtimes(self):
        lua1 = lupa.LuaRuntime()

        function1 = lua1.eval('function() return 1 end')
        self.assertNotEqual(None, function1)
        self.assertEqual(1, function1())

        lua2 = lupa.LuaRuntime()

        function2 = lua2.eval('function() return 1+1 end')
        self.assertNotEqual(None, function2)
        self.assertEqual(1, function1())
        self.assertEqual(2, function2())

        lua3 = lupa.LuaRuntime()

        self.assertEqual(1, function1())
        self.assertEqual(2, function2())

        function3 = lua3.eval('function() return 1+1+1 end')
        self.assertNotEqual(None, function3)

        del lua1, lua2, lua3

        self.assertEqual(1, function1())
        self.assertEqual(2, function2())
        self.assertEqual(3, function3())


class TestThreading(unittest.TestCase):
    def tearDown(self):
        gc.collect()

    def _run_threads(self, threads, starter=None):
        for thread in threads:
            thread.start()
        if starter is not None:
            time.sleep(0.1) # give some time to start up
            starter.set()
        for thread in threads:
            thread.join()

    def test_sequential_threading(self):
        func_code = '''\
        function calc(i)
            if i > 2
                then return calc(i-1) + calc(i-2) + 1
                else return 1
            end
        end
        return calc
        '''
        lua = lupa.LuaRuntime()
        functions = [ lua.execute(func_code) for _ in range(10) ]
        results = [None] * len(functions)

        starter = threading.Event()
        def test(i, func, *args):
            starter.wait()
            results[i] = func(*args)

        threads = [ threading.Thread(target=test, args=(i, func, 25))
                    for i, func in enumerate(functions) ]

        self._run_threads(threads, starter)

        self.assertEqual(1, len(set(results)))
        self.assertEqual(150049, results[0])

    def test_threading(self):
        func_code = '''\
        function calc(i)
            if i > 2
                then return calc(i-1) + calc(i-2) + 1
                else return 1
            end
        end
        return calc
        '''
        runtimes  = [ lupa.LuaRuntime() for _ in range(10) ]
        functions = [ lua.execute(func_code) for lua in runtimes ]

        results = [None] * len(runtimes)

        def test(i, func, *args):
            results[i] = func(*args)

        threads = [ threading.Thread(target=test, args=(i, func, 20))
                    for i, func in enumerate(functions) ]

        self._run_threads(threads)

        self.assertEqual(1, len(set(results)))
        self.assertEqual(13529, results[0])

    def test_threading_pycallback(self):
        func_code = '''\
        function calc(pyfunc, i)
            if i > 2
                then return pyfunc(i) + calc(pyfunc, i-1) + calc(pyfunc, i-2) + 1
                else return 1
            end
        end
        return calc
        '''
        runtimes  = [ lupa.LuaRuntime() for _ in range(10) ]
        functions = [ lua.execute(func_code) for lua in runtimes ]

        results = [None] * len(runtimes)

        def pycallback(i):
            return i**2

        def test(i, func, *args):
            results[i] = func(*args)

        threads = [ threading.Thread(target=test, args=(i, luafunc, pycallback, 20))
                    for i, luafunc in enumerate(functions) ]

        self._run_threads(threads)

        self.assertEqual(1, len(set(results)))
        self.assertEqual(185925, results[0])

    def test_threading_iter(self):
        values = list(range(1,100))
        lua = lupa.LuaRuntime()
        table = lua.eval('{%s}' % ','.join(map(str, values)))
        self.assertEqual(values, list(table))

        lua_iter = iter(table)

        state_lock = threading.Lock()
        running = []
        iterations_done = {}
        def sync(i):
            state_lock.acquire()
            try:
                status = iterations_done[i]
            except KeyError:
                status = iterations_done[i] = [0, threading.Event()]
            status[0] += 1
            state_lock.release()
            event = status[1]
            while status[0] < len(running):
                event.wait(0.1)
            event.set()

        l = []
        start_event = threading.Event()
        def extract(n, append = l.append):
            running.append(n)
            if len(running) < len(threads):
                start_event.wait()
            else:
                start_event.set()
            # all running, let's go
            for i, item in enumerate(lua_iter):
                append(item)
                sync(i)
            running.remove(n)

        threads = [ threading.Thread(target=extract, args=(i,))
                    for i in range(6) ]
        self._run_threads(threads)

        orig = l[:]
        l.sort()
        self.assertEqual(values, l)

    def test_threading_mandelbrot(self):
        # copied from Computer Language Benchmarks Game
        code = '''\
            function(N, i, total)
                local char, unpack = string.char, table.unpack
                local result = ""
                local M, ba, bb, buf = 2/N, 2^(N%8+1)-1, 2^(8-N%8), {}
                local start_line, end_line = N/total * (i-1), N/total * i - 1
                for y=start_line,end_line do
                    local Ci, b, p = y*M-1, 1, 0
                    for x=0,N-1 do
                        local Cr = x*M-1.5
                        local Zr, Zi, Zrq, Ziq = Cr, Ci, Cr*Cr, Ci*Ci
                        b = b + b
                        for i=1,49 do
                            Zi = Zr*Zi*2 + Ci
                            Zr = Zrq-Ziq + Cr
                            Ziq = Zi*Zi
                            Zrq = Zr*Zr
                            if Zrq+Ziq > 4.0 then b = b + 1; break; end
                        end
                        if b >= 256 then p = p + 1; buf[p] = 511 - b; b = 1; end
                    end
                    if b ~= 1 then p = p + 1; buf[p] = (ba-b)*bb; end
                    result = result .. char(unpack(buf, 1, p))
                end
                return result
            end
            '''

        empty_bytes_string = ''.encode('ASCII')

        image_size = 128
        thread_count = 4

        lua_funcs = [ lupa.LuaRuntime(autodecode=False).eval(code)
                      for _ in range(thread_count) ]

        results = [None] * thread_count
        def mandelbrot(i, lua_func):
            results[i] = lua_func(image_size, i+1, thread_count)

        threads = [ threading.Thread(target=mandelbrot, args=(i, lua_func))
                    for i, lua_func in enumerate(lua_funcs) ]
        self._run_threads(threads)

        result_bytes = empty_bytes_string.join(results)

        self.assertEqual(type(result_bytes), type(empty_bytes_string))
        self.assertEqual(image_size*image_size//8, len(result_bytes))

        # plausability checks - make sure it's not all white or all black
        self.assertEqual('\0'.encode('ASCII')*(image_size//8//2),
                         result_bytes[:image_size//8//2])
        if IS_PYTHON3:
            self.assertTrue('\xFF'.encode('ISO-8859-1') in result_bytes)
        else:
            self.assertTrue('\xFF' in result_bytes)

        # if we have PIL, check that it can read the image
        ## try:
        ##     import Image
        ## except ImportError:
        ##     pass
        ## else:
        ##     image = Image.fromstring('1', (image_size, image_size), result_bytes)
        ##     image.show()


class TestUnpackTuples(unittest.TestCase):
    def setUp(self):
        self.lua = lupa.LuaRuntime()

        # Define a Python function which returns a tuple
        # and is accessible from Lua as fun().
        def tuple_fun():
            return "one", "two", "three", "four"
        self.lua.globals()['fun'] = tuple_fun

    def tearDown(self):
        self.lua = None
        gc.collect()

    def test_python_function_tuple_expansion_exact(self):
        self.lua.execute("a, b, c, d = fun()")
        self.assertEqual("one", self.lua.eval("a"))
        self.assertEqual("two", self.lua.eval("b"))
        self.assertEqual("three", self.lua.eval("c"))
        self.assertEqual("four", self.lua.eval("d"))

    def test_python_function_tuple_expansion_extra_args(self):
        self.lua.execute("a, b, c, d, e, f = fun()")
        self.assertTrue(self.lua.eval("a == 'one'"))
        self.assertTrue(self.lua.eval("b == 'two'"))
        self.assertTrue(self.lua.eval("c == 'three'"))
        self.assertTrue(self.lua.eval("d == 'four'"))
        self.assertTrue(self.lua.eval("e == nil"))
        self.assertTrue(self.lua.eval("f == nil"))
        self.assertEqual("one", self.lua.eval("a"))
        self.assertEqual("two", self.lua.eval("b"))
        self.assertEqual("three", self.lua.eval("c"))
        self.assertEqual("four", self.lua.eval("d"))
        self.assertEqual(None, self.lua.eval("e"))
        self.assertEqual(None, self.lua.eval("f"))

    def test_python_function_tuple_expansion_missing_args(self):
        self.lua.execute("a, b = fun()")
        self.assertEqual("one", self.lua.eval("a"))
        self.assertEqual("two", self.lua.eval("b"))

    def test_translate_None(self):
        """Lua does not understand None.  Should (almost) never see it."""
        self.lua.globals()['f'] = lambda: (None, None)

        self.lua.execute("x, y = f()")

        self.assertEqual(None, self.lua.eval("x"))
        self.assertEqual(self.lua.eval("x"), self.lua.eval("y"))
        self.assertEqual(self.lua.eval("x"), self.lua.eval("z"))
        self.assertTrue(self.lua.eval("x == y"))
        self.assertTrue(self.lua.eval("x == z"))
        self.assertTrue(self.lua.eval("x == nil"))
        self.assertTrue(self.lua.eval("nil == z"))


class TestMethodCall(unittest.TestCase):
    def setUp(self):

        self.lua = lupa.LuaRuntime()

        class C(object):
            def __init__(self, x):
                self.x = int(x)

            def getx(self):
                return self.x

            def getx1(self, n):
                return int(n) + self.x

            def setx(self, v):
                self.x = int(v)

            @classmethod
            def classmeth(cls, v):
                return v

            @staticmethod
            def staticmeth(v):
                return v

        class D(C):
            pass

        def f():
            return 100

        def g(n):
            return int(n) + 100

        x = C(1)
        self.lua.globals()['C'] = C
        self.lua.globals()['D'] = D
        self.lua.globals()['x'] = x
        self.lua.globals()['f'] = f
        self.lua.globals()['g'] = g
        self.lua.globals()['d'] = { 'F': f, "G": g }
        self.lua.globals()['bound0'] = x.getx
        self.lua.globals()['bound1'] = x.getx1

    def tearDown(self):
        self.lua = None
        gc.collect()

    def test_method_call_as_method(self):
        self.assertEqual(self.lua.eval("x:getx()"), 1)
        self.assertEqual(self.lua.eval("x:getx1(2)"), 3)
        self.lua.execute("x:setx(4)")
        self.assertEqual(self.lua.eval("x:getx()"), 4)
        self.assertEqual(self.lua.eval("x:getx1(2)"), 6)

    def test_method_call_function_lookup(self):
        self.assertEqual(self.lua.eval("f()"), 100)
        self.assertEqual(self.lua.eval("g(10)"), 110)
        self.assertEqual(self.lua.eval("d.F()"), 100)
        self.assertEqual(self.lua.eval("d.G(9)"), 109)

    def test_method_call_class_hierarchy(self):
        self.assertEqual(self.lua.eval("C(5):getx()"), 5)
        self.assertEqual(self.lua.eval("D(5):getx()"), 5)

    def test_method_call_class_methods(self):
        # unbound methods
        self.assertEqual(self.lua.eval("C.getx(C(5))"), 5)
        self.assertEqual(self.lua.eval("C.getx(D(5))"), 5)

        # class/static methods
        self.assertEqual(self.lua.eval("C:classmeth(5)"), 5)
        self.assertEqual(self.lua.eval("C.staticmeth(5)"), 5)

    def test_method_call_bound(self):
        self.assertEqual(self.lua.eval("bound0()"), 1)
        self.assertEqual(self.lua.eval("bound1(3)"), 4)
        self.assertEqual(self.lua.eval("python.eval('1 .__add__')(1)"), 2)
        self.assertEqual(self.lua.eval("python.eval('1 .__add__')(2)"), 3)

        # the following is an unfortunate side effect of the "self" removal
        # on bound method calls:
        self.assertRaises(TypeError, self.lua.eval, "bound1(x)")


################################################################################
# tests for the lupa.unpacks_lua_table and lupa.unpacks_lua_table_method
# decorators

@lupa.unpacks_lua_table
def func_1(x):
    return ("x=%s" % (x, ))


@lupa.unpacks_lua_table
def func_2(x, y):
    return ("x=%s, y=%s" % (x, y))


@lupa.unpacks_lua_table
def func_3(x, y, z='default'):
    return ("x=%s, y=%s, z=%s" % (x, y, z))


class MyCls_1(object):
    @lupa.unpacks_lua_table_method
    def meth(self, x):
        return ("x=%s" % (x,))


class MyCls_2(object):
    @lupa.unpacks_lua_table_method
    def meth(self, x, y):
        return ("x=%s, y=%s" % (x, y))


class MyCls_3(object):
    @lupa.unpacks_lua_table_method
    def meth(self, x, y, z='default'):
        return ("x=%s, y=%s, z=%s" % (x, y, z))


class KwargsDecoratorTest(SetupLuaRuntimeMixin, unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super(KwargsDecoratorTest, self).__init__(*args, **kwargs)
        self.arg1 = func_1
        self.arg2 = func_2
        self.arg3 = func_3

    def assertResult(self, f, call_txt, res_txt):
        lua_func = self.lua.eval("function (f) return f%s end" % call_txt)
        self.assertEqual(lua_func(f), res_txt)

    def assertIncorrect(self, f, call_txt):
        lua_func = self.lua.eval("function (f) return f%s end" % call_txt)
        self.assertRaises(TypeError, lua_func, f)

    def test_many_args(self):
        self.assertResult(self.arg2, "{x=1, y=2}", "x=1, y=2")
        self.assertResult(self.arg2, "{x=2, y=1}", "x=2, y=1")
        self.assertResult(self.arg2, "{y=1, x=2}", "x=2, y=1")
        self.assertResult(self.arg2, "(1, 2)",     "x=1, y=2")

    def test_single_arg(self):
        self.assertResult(self.arg1, "{x=1}", "x=1")
        self.assertResult(self.arg1, "(1)", "x=1")
        self.assertResult(self.arg1, "(nil)", "x=None")

    def test_defaults(self):
        self.assertResult(self.arg3, "{x=1, y=2}", "x=1, y=2, z=default")
        self.assertResult(self.arg3, "{x=1, y=2, z=3}", "x=1, y=2, z=3")

    def test_defaults_incorrect(self):
        self.assertIncorrect(self.arg3, "{x=1, z=3}")

    def test_kwargs_unknown(self):
        self.assertIncorrect(self.arg2, "{x=1, y=2, z=3}")
        self.assertIncorrect(self.arg2, "{y=2, z=3}")
        self.assertIncorrect(self.arg1, "{x=1, y=2}")

    def test_posargs_bad(self):
        self.assertIncorrect(self.arg1, "(1,2)")
        self.assertIncorrect(self.arg1, "()")

    def test_posargs_kwargs(self):
        self.assertResult(self.arg2, "{5, y=6}", "x=5, y=6")
        self.assertResult(self.arg2, "{y=6, 5}", "x=5, y=6")
        self.assertResult(self.arg2, "{5, [2]=6}", "x=5, y=6")
        self.assertResult(self.arg2, "{[1]=5, [2]=6}", "x=5, y=6")
        self.assertResult(self.arg2, "{[1]=5, y=6}", "x=5, y=6")

        self.assertResult(self.arg3, "{x=5, y=6, z=8}", "x=5, y=6, z=8")
        self.assertResult(self.arg3, "{5, y=6, z=8}", "x=5, y=6, z=8")
        self.assertResult(self.arg3, "{5, y=6}", "x=5, y=6, z=default")
        self.assertResult(self.arg3, "{5, 6}", "x=5, y=6, z=default")
        self.assertResult(self.arg3, "{5, 6, 7}", "x=5, y=6, z=7")
        self.assertResult(self.arg3, "{z=7, 5, 6}", "x=5, y=6, z=7")

    def test_posargs_kwargs_bad(self):
        self.assertIncorrect(self.arg2, "{5, y=6, z=7}")
        self.assertIncorrect(self.arg2, "{5, [3]=6}")
        self.assertIncorrect(self.arg2, "{x=5, [2]=6}")  # I guess it's ok to reject this

        self.assertIncorrect(self.arg3, "{5, z=7}")
        self.assertIncorrect(self.arg3, "{5}")

    def test_posargs_nil(self):
        self.assertResult(self.arg3, "(5, nil, 6)", "x=5, y=None, z=6")

    def test_posargs_nil_first(self):
        self.assertResult(self.arg3, "(nil, nil, 6)", "x=None, y=None, z=6")

    def test_posargs_nil_last(self):
        self.assertResult(self.arg3, "(5, nil, nil)", "x=5, y=None, z=None")

    def test_posargs_kwargs_python_none_last(self):
        self.assertResult(self.arg3, "{5, python.none, python.none}", "x=5, y=None, z=None")

    def test_posargs_python_none_last(self):
        self.assertResult(self.arg3, "(5, python.none, python.none)", "x=5, y=None, z=None")

    def test_posargs_kwargs_python_none_some(self):
        self.assertResult(self.arg3, "{python.none, y=python.none, z=6}", "x=None, y=None, z=6")

    def test_posargs_kwargs_python_none_all(self):
        self.assertResult(self.arg3, "{x=python.none, y=python.none}", "x=None, y=None, z=default")

    # -------------------------------------------------------------------------
    # The following examples don't work as a Python programmer would expect
    # them to:

    # def test_posargs_kwargs_nil_last(self):
    #     self.assertResult(self.arg3, "{5, nil, nil}", "x=5, y=None, z=None")
    #
    # def test_posargs_kwargs_nil_some(self):
    #     self.assertResult(self.arg3, "{nil, y=nil, z=6}", "x=None, y=None, z=6")
    #
    # def test_posargs_kwargs_nil_all(self):
    #     self.assertResult(self.arg3, "{x=nil, y=nil}", "x=None, y=None, z=default")

    # -------------------------------------------------------------------------
    # These tests pass in Lua 5.2 but fail in LuaJIT:

    # def test_posargs_kwargs_nil(self):
    #     self.assertResult(self.arg3, "{5, nil, 6}", "x=5, y=None, z=6")
    #
    # def test_posargs_kwargs_nil_first(self):
    #     self.assertResult(self.arg3, "{nil, nil, 6}", "x=None, y=None, z=6")



class MethodKwargsDecoratorTest(KwargsDecoratorTest):

    def __init__(self, *args, **kwargs):
        super(MethodKwargsDecoratorTest, self).__init__(*args, **kwargs)
        self.arg1 = MyCls_1()
        self.arg2 = MyCls_2()
        self.arg3 = MyCls_3()

    def assertResult(self, f, call_txt, res_txt):
        lua_func = self.lua.eval("function (obj) return obj:meth%s end" % call_txt)
        self.assertEqual(lua_func(f), res_txt)

    def assertIncorrect(self, f, call_txt):
        lua_func = self.lua.eval("function (obj) return obj:meth%s end" % call_txt)
        self.assertRaises(TypeError, lua_func, f)


################################################################################
# tests for error stacktrace

class TestErrorStackTrace(unittest.TestCase):
    if not hasattr(unittest.TestCase, 'assertIn'):
        def assertIn(self, member, container, msg=None):
            self.assertTrue(member in container, msg)

    if not hasattr(unittest.TestCase, 'assertNotIn'):
        def assertNotIn(self, member, container, msg=None):
            self.assertFalse(member in container, msg)

    def test_stacktrace(self):
        lua = lupa.LuaRuntime()
        try:
            lua.execute("error('abc')")
            raise RuntimeError("LuaError was not raised")
        except lupa.LuaError as e:
            self.assertIn("stack traceback:", e.err_msg)

    def test_nil_debug(self):
        lua = lupa.LuaRuntime()
        try:
            lua.execute("debug = nil")
            lua.execute("error('abc')")
            raise RuntimeError("LuaError was not raised")
        except lupa.LuaError as e:
            self.assertNotIn("stack traceback:", e.err_msg)

    def test_nil_debug_traceback(self):
        lua = lupa.LuaRuntime()
        try:
            lua.execute("debug = nil")
            lua.execute("error('abc')")
            raise RuntimeError("LuaError was not raised")
        except lupa.LuaError as e:
            self.assertNotIn("stack traceback:", e.err_msg)
