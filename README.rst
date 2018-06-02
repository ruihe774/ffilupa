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

During installation, ffilupa will automatically find lua libraries through ``pkg-config``.

Make sure you have installed Python 3.5+ in your system.
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
