|banner|
========

.. |banner| image:: docs/banner.svg
           :target: https://github.com/TitanSnow/ffilupa
           :alt: ffilupa

.. image:: https://img.shields.io/travis/TitanSnow/ffilupa.svg?style=for-the-badge
  :target: https://travis-ci.org/TitanSnow/ffilupa
  :alt: build

.. image:: https://img.shields.io/codecov/c/github/TitanSnow/ffilupa.svg?style=for-the-badge
  :target: https://codecov.io/gh/TitanSnow/ffilupa
  :alt: coverage

.. image:: https://img.shields.io/pypi/v/ffilupa.svg?style=for-the-badge
  :target: https://pypi.org/project/ffilupa
  :alt: version

.. image:: https://img.shields.io/pypi/l/ffilupa.svg?style=for-the-badge
  :target: https://pypi.org/project/ffilupa
  :alt: license

A modern two-way bridge between Python and Lua.

*Next generation of ffilupa — 3.0.0 — is coming soon.*

.. contents:: **Contents**
  :depth: 1

Major Features
--------------

For Python Users
````````````````

* Integrate Lua into Python using CFFI_ as backend, which runs fast on both CPython and PyPy.
* Run multiple Lua runtimes in one Python process.
* Link to multiple lua libraries installed in system and use their luarocks_.
* Zero-copy data sharing between Python and Lua.
* Seamless operations on Lua objects.
* Hackable and extendable; customizable interacting behaviors.
* Parallel numerical calculation using Lua to break the limit of Python’s GIL.

.. _CFFI: http://cffi.rtfd.io
.. _luarocks: http://www.luarocks.org

For Lua Users
`````````````

* Enrich Lua’s abilities by using Python’s modules.
* Link to CPython and PyPy.
* Seamless operations on Python objects.

Above all, ffilupa has plenty of fun!

Why ffilupa
-----------

Compare to lupa_
````````````````

* lupa uses Cython as it’s backend, which is less friendly to PyPy and not extendable.
* lupa doesn’t support Lua as the host language, which means you can’t use it in a Lua program.
* lupa doesn’t support seamless operations on Lua objects.
* lupa is not under actively development.
* lupa inspired ffilupa a lot.

.. _lupa: https://github.com/scoder/lupa

Compare to LunaticPython_
`````````````````````````

* Well, LunaticPython is too old and out of development for a long time.
* LunaticPython doesn’t support multiple Lua runtimes.
* LunaticPython leaks new features.

.. _LunaticPython: http://labix.org/lunatic-python

Installation
------------

Before installing ffilupa, please check whether you have installed the development library of lua.
On Ubuntu, you can install ``liblua5.3-dev`` or ``liblua5.2-dev``::

    $ sudo apt install [liblua5.3-dev|liblua5.2-dev]

On Mac OS X, you can use Homebrew_::

    $ brew install lua pkg-config

.. _Homebrew: https://brew.sh

During installation, ffilupa will automatically find lua libraries through ``pkg-config``.

Make sure you have installed Python 3.5+ in your system,
including it’s development files and the suitable C compiler.
On Ubuntu::

    $ sudo apt install python3-dev

On Mac OS X::

    $ brew install python

You’d better install the dependencies of ffilupa::

    $ pip install cffi semantic_version

It’s optional; ffilupa will install them if you haven’t installed before.

Install stable version
``````````````````````

Sorry, I’m working hard for a stable version.

Install development version from Git branch
```````````````````````````````````````````

For Python Users
::::::::::::::::

::

    $ pip install git+https://github.com/TitanSnow/ffilupa.git

For Lua Users
:::::::::::::

Make sure you have installed luarocks_.

::

    $ git clone https://github.com/TitanSnow/ffilupa.git
    $ cd ffilupa
    $ luarocks make

FAQ about installation
``````````````````````

How to deal with the exception ‘Required lua lib not found’?
::::::::::::::::::::::::::::::::::::::::::::::::::::::::::::

Please check the installation of Lua. ffilupa currently only supports Lua 5.2 and 5.3.
Then reinstall ffilupa in order to find the recently installed Lua libraries.

Does ffilupa support Windows?
:::::::::::::::::::::::::::::

ffilupa *can* support Windows, but not now. It might support Windows in next minor release.

Usage
-----

For Python Users
````````````````

A Brief Look
::::::::::::

.. code-block:: pycon

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

.. code-block:: pycon

    >>> def greeting(name='World'): # greeting someone
    ...     print('Hello, {}!'.format(name))
    >>> lua._G.greeting = greeting
    >>> lua.execute('greeting()')
    Hello, World!
    >>> lua.execute('greeting("John")')
    Hello, John!

Zero-copy Data Sharing
::::::::::::::::::::::

.. code-block:: pycon

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

.. code-block:: pycon

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

For Lua Users
`````````````

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

Acknowledgements
----------------

* CFFI_
* lupa_
