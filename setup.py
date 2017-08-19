from setuptools import setup
import runpy

VERSION = runpy.run_path('ffilupa/version.py')['__version__']

setup(
    name='ffilupa',
    version=VERSION,
    author="TitanSnow",
    author_email="tttnns1024@gmail.com",
    url='https://github.com/TitanSnow/lupa/tree/ffi',
    description='cffi implement of lupa with lowlevel lua API',
    long_description=open('README.rst').read(),
    license='MIT style',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Other Scripting Engines',
        'Operating System :: OS Independent',
        'Topic :: Software Development',
    ],
    packages=['ffilupa'],
    setup_requires=["cffi>=1.10.0"],
    cffi_modules=["ffibuilder_lua.py:ffibuilder"],
    install_requires=["cffi>=1.10.0", "six>=1.9.0"],
    test_suite='ffilupa.tests.suite',
)
