Installation
============

.. todo:: Modify when 4.0 releases.

Requirements
------------

ffilupa only supports Python>=3.6 and Lua>=5.2 (no LuaJIT).
ffilupa is packed with a bundle Lua,
so it's fine to have no Lua installed in the system.
And ffilupa will not attempt to link against Lua libraries
installed in the system *during the installation*.
See `Integrate with Other Lua Libraries`_.

Use pip or pipenv
-----------------

::

    $ pip install ffilupa
    # or pipenv if you prefer
    $ pipenv install ffilupa

.. note::
    This documentation is about ffilupa 4.0, which is not yet released.
    So you need to add option ``--pre`` to command line, e.g.
    ``pip install ffilupa --pre``.

.. note::
    If there comes a installation error saying that some modules are missing,
    maybe you are installing the source distribution rather than pre-built wheels_.
    (ffilupa releases wheels covering almost all common environments.
    So this situation is rare.) In this case, it's necessary to install
    the dependencies of ffilupa in advance::

        $ pip install -r https://github.com/TitanSnow/ffilupa/raw/next/requirements.txt

.. _wheels: https://pythonwheels.com


Get the Source Code
-------------------

::

    $ git clone https://github.com/TitanSnow/ffilupa.git --recurse-submodules

.. note::
    This documentation is about ffilupa 4.0, which is not in the default branch.
    So you need to checkout the branch ``next`` or add ``-b next`` to clone command line.


Integrate with Other Lua Libraries
----------------------------------

.. note:: You can skip this section.

.. note::
    To do things described in this section and the next section requires the C compiler.
    Windows users can refer to WindowsCompiler_.

.. _WindowsCompiler: https://wiki.python.org/moin/WindowsCompilers

By default the bundle Lua is used, the version of which is 5.3.
If you want ffilupa to use other Lua libraries installed in the system
or built by yourself, you can manually add them after installation.

For example, Bob hates Lua 5.3 and sticks to Lua 5.2.
Bob uses Ubuntu, and he has already installed the package ``liblua5.2-dev``
by apt. (Only ``liblua5.2-0`` or ``lua5.2`` is not enough.
ffilupa needs the development files.) Then open the Python REPL:
(There's no CLI to do this stuff because I don't think it'll simplify anything.)

::

    >>> from ffilupa.lualibs.builder import *       # import the builder API
    >>> p = pkginfo_from_pkgconfig("lua52")         # just like ``pkg-config lua52``
    >>>                                             # you can get pkg names from ``pkg-config --list-all``
    >>> add_lua_pkg(p)                              # build "bridge" and add lua52 to ffilupa

See also the reference of builder API.

.. todo:: Add link to the reference.

For other Linux distribution, there's no big difference.
For macOS, you can use Homebrew_ to install Lua and pkg-config.
For Windows, unfortunately there's no such thing like pkg-config.

.. _Homebrew: https://brew.sh

After adding lua libraries to ffilupa, you can select one to use::

    >>> from ffilupa import *
    >>> lualib = get_lualibs()[1]       # index 0 is the bundle lua
    >>> lua = LuaRuntime(lualib=lualib)

See also the reference of lualibs API.

.. todo:: Add link to the reference.

Another situation is to use a Lua library built by yourself.
For example, John uses a Linux distribution that has no pre-built lua package.
John built Lua by himself, (well I don't want to talk about how to build Lua,)
and casually put it in the home directory::

    /home/john/lua
    ├── include
    │   ├── lauxlib.h
    │   ├── lua.h
    │   ├── lua.hpp
    │   ├── luaconf.h
    │   └── lualib.h
    ├── lib
    │   └── liblua.so
    └── bin
        ├── lua
        └── luac

Then open the Python REPL::

    >>> from ffilupa.lualibs.builder import *
    >>> from packaging.version import Version
    >>> p = PkgInfo(                                    # construct PkgInfo manually
    ...     version=Version('5.3.5'),                   # John built Lua 5.3.5, e.g.
    ...     include_dirs=('/home/john/lua/include',),   # must be tuple, not list, and do not forget the comma in brackets!
    ...     library_dirs=('/home/john/lua/lib',),
    ...     runtime_library_dirs=('/home/john/lua/lib',),
    ...     libraries=('lua',),
    ... )
    >>> add_lua_pkg(p)

Finished. You can even do this on Windows.

For Python Library Authors
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. note::
    "Python library authors" refers to those who write Python modules
    rather than applications. Well, commonly, they probably:

    * write ``setup.py`` by themselves and do not use pipenv;
    * publish their works to PyPI.

For example, Bob is writing a module named "alup".
(Yes, the same Bob who sticks to Lua 5.2.)
alup depends on ffilupa and Bob wants to use Lua 5.2
to write his module. Obviously it's impossible to teach the users of alup
how to add Lua 5.2 to ffilupa. So ffilupa provides a way
for Python library authors to use customized Lua.

In ``setup.py``, add this:

.. code-block:: diff

      from setuptools import setup
    + from ffilupa.lualibs.builder import *

    + pkg = pkginfo_from_pkgconfig('lua52')
    + ext = extension_from_pkginfo('alup._lua52', pkg)
    + REQUIRES = ['ffilupa']

      setup(
          ...,
    +     ext_modules=[ext],
    +     setup_requires=REQUIRES,
    +     install_requires=REQUIRES,
      )

Then in ``__init__.py``, add this::

    from ffilupa import *
    from packaging.version import Version

    pkg = PkgInfo(
        version=Version('5.2.4'),
        module_location='alup._lua52',
    )
    lualib = LuaLib(pkg)
    set_default_lualib(lualib)

Then run::

    $ python setup.py develop

The project is using Lua 5.2 now.

As for packaging, unlike pure Python modules, you need to do it in manylinux_,
and the built wheels need to be repaired by auditwheel_ to include the Lua library.
ffilupa supports `Python ABI3`_ (aka "stable ABI" or "Python limited API").
If you need to support Windows that has no pkg-config, you may bundle Lua into the project
just like what ffilupa does.

.. _manylinux: https://github.com/pypa/manylinux
.. _auditwheel: https://github.com/pypa/auditwheel
.. _`Python ABI3`: https://www.python.org/dev/peps/pep-0384


Install ffilupa for Lua
-----------------------

.. note:: This section is for Lua users.

Lua can be the host language to use ffilupa as well as Python.
To install and use ffilupa for Lua, it's necessary to install
ffilupa for Python first. And `Integrate with Other Lua Libraries`_
should be read before this section.

Open the Lua REPL::

    Lua 5.3.3  Copyright (C) 1994-2016 Lua.org, PUC-Rio
    > package.path
    /usr/local/share/lua/5.3/?.lua;/usr/local/share/lua/5.3/?/init.lua;/usr/local/lib/lua/5.3/?.lua;/usr/local/lib/lua/5.3/?/init.lua;/usr/share/lua/5.3/?.lua;/usr/share/lua/5.3/?/init.lua;./?.lua;./?/init.lua
    > package.cpath
    /usr/local/lib/lua/5.3/?.so;/usr/lib/x86_64-linux-gnu/lua/5.3/?.so;/usr/lib/lua/5.3/?.so;/usr/local/lib/lua/5.3/loadall.so;./?.so

Remember the path ``/usr/local/share/lua/5.3`` and cpath ``/usr/local/lib/lua/5.3``.
Then open the Python REPL::

    >>> from ffilupa.lualibs.builder import *
    >>> # the PkgInfo should correspond to the Lua that is to install ffilupa
    >>> p = pkginfo_from_pkgconfig('lua53')
    >>> install_embedding(
    ...     p,
    ...     '/usr/local/share/lua/5.3',     # path
    ...     '/usr/local/lib/lua/5.3',       # cpath
    ... )

Finished. Now you can use ffilupa in Lua::

    > ffilupa = require 'ffilupa'

See also the "ffilupa in Lua" API.

.. todo:: Add link to the reference.
