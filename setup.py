from setuptools import setup
from ffilupa.lualibs.builder import extension_from_pkginfo, bundle_lua_pkginfo


REQUIRES = (
    'cffi~=1.10',
    'packaging~=19.0',
    'dataclasses~=0.6;python_version=="3.6"',
    'tomlkit~=0.5',
)


setup(
    ext_modules=[extension_from_pkginfo('ffilupa._lua', bundle_lua_pkginfo),],
    setup_requires=REQUIRES,
    install_requires=REQUIRES,
)
