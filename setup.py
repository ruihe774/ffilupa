from setuptools import setup
from ffilupa.lualibs.builder import create_extension, bundle_lua_buildoptions


with open('requirements.txt') as f:
    REQUIRES = [ln.rstrip() for ln in f]


setup(
    ext_modules=[create_extension('ffilupa._lua', bundle_lua_buildoptions), ],
    setup_requires=REQUIRES,
    install_requires=REQUIRES,
)
