from setuptools import setup
from ffilupa import __version__

setup(
    name='ffilupa',
    version=__version__,
    packages=['ffilupa'],
    setup_requires=["cffi>=1.10.0"],
    cffi_modules=["ffibuilder_lua.py:ffibuilder"],
    install_requires=["cffi>=1.10.0", "six>=1.9.0"],
    test_suite='ffilupa.tests.suite',
    zip_safe=True,
)
