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

For other Linux distribution, there's no distinguishing difference.
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
