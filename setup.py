from setuptools import setup
from ffilupa.lualibs.builder import extension_from_pkginfo
from ffilupa.lualibs._builder_data import bundle_lua_pkginfo


setup(
    ext_modules=[extension_from_pkginfo('ffilupa._lua', bundle_lua_pkginfo, 'build'),]
)
