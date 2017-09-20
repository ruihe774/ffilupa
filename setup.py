from setuptools import setup

def read_version():
    from os import path
    global VERSION
    with open(path.join('ffilupa', 'version.txt')) as f:
        VERSION = f.read().rstrip()
read_version(); del read_version

setup(
    name='ffilupa',
    version=VERSION,
    author="TitanSnow",
    author_email="tttnns1024@gmail.com",
    url='https://github.com/TitanSnow/ffilupa',
    description='cffi binding of lua for python',
    long_description=open('README.rst').read(),
    license='LGPLv3',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
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
    package_data={'ffilupa': ['version.txt']},
    include_package_data=True,
    setup_requires=["cffi~=1.10"],
    cffi_modules=["ffibuild/lua.py:ffibuilder"],
    install_requires=["cffi~=1.10", "six~=1.9", 'kwonly-args~=1.0.0', 'singledispatch~=3.4.0.3', 'zope.deprecation~=4.3'],
)
