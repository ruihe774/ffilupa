.. |ZWNBSP| unicode:: U+FEFF
   :trim:

Quick Start
===========

Introduction
------------

ffilupa is a cffi_ binding of lua_ for python. It's a re-implement
of lupa_. Unlike lupa, ffilupa is based on cffi rather than Cython.
That means it's JIT-friendly and has no dependency on python C API.

ffilupa is almost compatible with lupa but has some incompatible places.
See `Guide for Porting from lupa`_.

ffilupa provides the low-level lua C API for python.
See :doc:`lowlevel`.

.. _cffi: https://cffi.readthedocs.io
.. _lua: https://www.lua.org
.. _lupa: https://github.com/scoder/lupa

Installation
------------

Requirements
^^^^^^^^^^^^

* A C/C |ZWNBSP| + |ZWNBSP| + compiler that at least supports ANSI C to
  compile lua sources.
  On POSIX, it's commonly the gcc. On Windows, it's the `correct version
  of MSVC`_.

* Python 2.7, 3.3 |ZWNBSP| + with setuptools. ffilupa perfectly supports
  python 3.4 |ZWNBSP| + and fallbacks to support python 2.7 and 3.3.
  Not only support CPython.

.. _`correct version of MSVC`: https://wiki.python.org/moin/WindowsCompilers

Install from PyPI
^^^^^^^^^^^^^^^^^

.. code-block:: bash

    pip install ffilupa

Install from Source
^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    git submodule update --init     # sync the lua sources
    python setup.py install

A Brief Look
------------

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
    <ffilupa.py_from_lua.LuaFunction object at ...>
    >>> # it's a lua object wrapper. let's see if it's callable.
    >>> lua_func(5, 6)
    30
    >>> # great! what about lua table?
    >>> lua_table = runtime.eval('{5, 1, 7, awd="dwa", ffilupa="great"}')
    >>> lua_table   # doctest: +ELLIPSIS
    <ffilupa.py_from_lua.LuaTable object at ...>
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
    <ffilupa.py_from_lua.LuaTable object at ...>
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

Guide for Porting from lupa
---------------------------

* ``attribute_handlers`` and ``attribute_filter`` are not supported.
  You can inherit ``LuaObject`` and custom the method ``attr_filter``.

* There are not options ``register_builtins`` and ``register_eval`` --
  they are always registered. You can inherit ``LuaRuntime`` and register
  things by yourself in method ``init_pylib``.

* ``LuaTable.keys()/values()/items()`` returns mapping view, not iterator.

* ``None`` is not automatically wrapped in lua.

* ``encoding`` can't be None but you can specify ``autodecode`` to False
  then it will behavior like lupa with encoding setting to None.

* There are no ``python.iter()/iterex()/enumerate()`` in lua. The only way
  is builtin ``pairs()``.

* ``LuaRuntime.__init__()`` only accepts keyword-only arguments.

* ``unpack_returned_tuples`` is not supported -- it's always unpacked.

* For an instance ``x``, *you can't call its instance method by ``x.y()``
  in lua,* the only way is ``x:y()``. For a class ``X``, ``X:y()`` to call
  classmethod and ``X.z()`` to call staticmethod.

* ffilupa is slower than lupa :)
