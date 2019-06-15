Quick Start
===========

Start by Examples
-----------------

ffilupa in Python
^^^^^^^^^^^^^^^^^

A Brief Look
::::::::::::

::

    >>> import ffilupa
    >>> lua = ffilupa.LuaRuntime()
    >>> lua_func = lua.eval('''
    ...     function(a, b) -- a plus b
    ...         return a + b
    ...     end
    ... ''')
    >>> lua_func(22, 33)
    55

Access Globals of Lua
:::::::::::::::::::::

::

    >>> def greeting(name='World'): # greeting someone
    ...     print('Hello, {}!'.format(name))
    >>> lua._G.greeting = greeting
    >>> lua.execute('greeting()')
    Hello, World!
    >>> lua.execute('greeting("John")')
    Hello, John!

Zero-copy Data Sharing
::::::::::::::::::::::

::

    >>> poem = {
    ...     'the': 'quick',
    ...     'brown': 'fox',
    ...     'jumps': 'over',
    ... }
    >>> lua_func = lua.eval('''
    ...     function(poem) -- finish the poem
    ...         poem['lazy'] = 'doges'
    ...     end
    ... ''')
    >>> lua_func(poem)
    >>> poem['lazy']
    'doges'

Deal with Lua Table
:::::::::::::::::::

::

    >>> table = lua.table_from(poem)
    >>> lua_func = lua.eval('''
    ...     function(poem) -- shuffle the poem
    ...         local new_poem = {}
    ...         for k, v in pairs(poem) do
    ...             new_poem[v] = k
    ...         end
    ...         return new_poem
    ...     end
    ... ''')
    >>> new_poem = lua_func(table)
    >>> for k in sorted(new_poem):
    ...     print(k, new_poem[k], end=' ')
    doges lazy fox brown over jumps quick the

A More Detailed Example
:::::::::::::::::::::::

::

    >>> # we are here to have a look at how to
    >>> # make a "conversation" between python and lua
    >>>
    >>> # first we import ffilupa
    >>> from ffilupa import *
    >>> # let's open a lua runtime
    >>> runtime = LuaRuntime()
    >>>
    >>> # let's do some math work
    >>> runtime.eval('1 + 2')
    3
    >>> # more interesting: eval other lua expressions
    >>> runtime.eval('5')
    5
    >>> runtime.eval('5.17')
    5.17
    >>> runtime.eval('math.pi') # doctest: +ELLIPSIS
    3.14...
    >>> runtime.eval('"This is a string"')
    'This is a string'
    >>> runtime.eval('true')
    True
    >>> runtime.eval('nil') is None
    True
    >>> # what will happen if the result of the expression
    >>> # is not simple type?
    >>> lua_func = runtime.eval('''
    ...     function(a, b)
    ...         return a * b
    ...     end
    ... ''')
    >>> # let's see what we have got
    >>> lua_func    # doctest: +ELLIPSIS
    <ffilupa.LuaFunction object at ...>
    >>> # it's a lua object wrapper. let's see if it's callable.
    >>> lua_func(5, 6)
    30
    >>> # great! what about lua table?
    >>> lua_table = runtime.eval('{5, 1, 7, awd="dwa", ffilupa="great"}')
    >>> lua_table   # doctest: +ELLIPSIS
    <ffilupa.LuaTable object at ...>
    >>> # it's another lua object wrapper. let's see if it's indexable
    >>> lua_table[1]
    5
    >>> # the integer index behavior same in lua -- start from 1
    >>> # what about key index?
    >>> lua_table['awd']
    'dwa'
    >>> # works prefect. and indexing through attr is also supported
    >>> lua_table.awd
    'dwa'
    >>> # We can easily access the global table in lua
    >>> runtime._G  # doctest: +ELLIPSIS
    <ffilupa.LuaTable object at ...>
    >>> runtime._G.math.pi  # doctest: +ELLIPSIS
    3.14...
    >>> runtime._G.awd = 'dwa'
    >>> runtime.eval('awd')
    'dwa'
    >>> # What will happen when a python object goes into lua?
    >>> python_list = [1, 2]
    >>> lua_func(python_list, 3)
    [1, 2, 1, 2, 1, 2]
    >>> # the list multiply is done in lua, amazing
    >>> # what about a python function?
    >>> def python_func(a, b):
    ...     return a ** b
    ...
    >>> runtime.eval('''
    ...     function(x, a, b)
    ...         return x(a, b) + 1
    ...     end
    ... ''')(python_func, 5, 3)
    126
    >>> # the python function is still callable in lua
    >>>
    >>> # lua code can import python modules
    >>> runtime.execute('''
    ...     pathlib = python.import_module('pathlib')
    ...     path = pathlib.Path()
    ...     path = path / 'ffilupa' / 'version.txt'
    ...     return path:open():read()
    ... ''') # doctest: +ELLIPSIS
    '2...'
    >>> # the brief look is done. for more, please continue reading the doc!

ffilupa in Lua
^^^^^^^^^^^^^^

.. note::
    This section is for Lua users. To install ffilupa for Lua,
    see :ref:`install_ffilupa_for_lua`.


A Brief Look
::::::::::::

.. code-block:: lua

    ffilupa = require 'ffilupa'
    Fraction = ffilupa.import_module('fractions').Fraction
    a = Fraction(1, 2)
    b = Fraction(1, 3)
    c = a + b    -- c == 5/6

Extend Lua’s Abilities
::::::::::::::::::::::

.. code-block:: lua

    Path = ffilupa.import_module('pathlib').Path
    p = Path('.')
    p = p / 'ffilupa'
    for _, filename in pairs(p:iterdir()) do
        print(filename)    -- print all filename in ./ffilupa
    end
