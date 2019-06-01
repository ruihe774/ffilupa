from setuptools import setup
from ffilupa.lualibs.builder import extension_from_pkginfo, bundle_lua_pkginfo


with open('requirements.txt') as f:
    REQUIRES = [ln.rstrip() for ln in f]


setup(
    ext_modules=[extension_from_pkginfo(None, bundle_lua_pkginfo),],
    setup_requires=REQUIRES,
    install_requires=REQUIRES,
)
