from setuptools import setup
from pathlib import Path
import asyncio
import yaml
import findlua

VERSION = '2.3.0.dev1'


def gen_ext():
    findlua.init_loop()
    loop = asyncio.get_event_loop()
    mods = loop.run_until_complete(findlua.findlua())
    loop.close()
    ext_modules = [
        builder.distutils_extension()
        for builder in findlua.make_builders(mods)
    ]
    for tp, rp in findlua.yaml_representer().items():
        yaml.add_representer(tp, rp)
    with Path('ffilupa', 'lua.yml').open('w') as f:
        yaml.dump(mods, f)
    return ext_modules


setup(
    name='ffilupa',
    version=VERSION,
    author="TitanSnow",
    author_email="tttnns1024@gmail.com",
    url='https://github.com/TitanSnow/ffilupa',
    description='cffi binding of lua for python',
    long_description=open('README.rst').read(),
    license='LGPLv3',
    classifiers=(
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Other Scripting Engines',
        'Operating System :: OS Independent',
        'Topic :: Software Development',
    ),
    packages=('ffilupa', 'findlua'),
    package_data={
        'findlua': ('lua_cdef.h', 'caller_cdef.h', 'source.c'),
        'ffilupa': ('lua.yml',),
    },
    include_package_data=True,
    setup_requires=('cffi~=1.10', 'semantic_version~=2.2', 'PyYAML~=3.10'),
    install_requires=('cffi~=1.10', 'semantic_version~=2.2', 'PyYAML~=3.10'),
    ext_modules=gen_ext(),
)
