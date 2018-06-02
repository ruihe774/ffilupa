setup_requires=('cffi~=1.10', 'semantic_version~=2.2',)
try:
    import cffi, semantic_version
except ImportError:
    try:
        from pip import main as pip
    except ImportError:
        # pip >=10.0
        from pip._internal import main as pip
    pip(['install'] + list(setup_requires))


from setuptools import setup
from pathlib import Path
import asyncio
import json
import semantic_version as sv
import findlua


def gen_ext():
    findlua.init_loop()
    loop = asyncio.get_event_loop()
    mods = loop.run_until_complete(findlua.findlua())
    loop.close()
    ext_modules = [
        builder.distutils_extension()
        for builder in findlua.make_builders(mods)
    ]
    class MyJSONEncoder(json.JSONEncoder):
        def default(self, o):
            if isinstance(o, sv.Version):
                return str(o)
            else:
                return super().default(o)
    with Path('ffilupa', 'lua.json').open('w', encoding='ascii') as f:
        json.dump({k: v._asdict() for k, v in mods.items()}, f, cls=MyJSONEncoder, indent=4)
    return ext_modules

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
        'ffilupa': ('lua.json', 'version.txt'),
    },
    include_package_data=True,
    setup_requires=setup_requires,
    install_requires=('cffi~=1.10', 'semantic_version~=2.2',),
    ext_modules=gen_ext(),
)
