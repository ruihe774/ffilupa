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
* Run multiple Lua runtime in one Python process.
* Link to multiple lua libraries installed in system and use their luarocks_
* Zero-copy data sharing between Python and Lua.
* Seamless operation on Lua objects.
* Hackable; customizable interacting behaviors.
* Parallel numerical calculation using Lua to break the limit of Python's GIL.
* Use Lua to write hot patch for Python application.

.. _CFFI: http://cffi.rtfd.io
.. _luarocks: http://www.luarocks.org

For Lua Users
`````````````

* Enrich Lua's abilities by using Python's modules.
* Link to CPython and PyPy.
* Seamless operation on Python objects.
