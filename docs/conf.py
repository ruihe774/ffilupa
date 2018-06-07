extensions = ['sphinx.ext.autodoc', 'sphinx.ext.viewcode']
source_suffix = '.rst'
master_doc = 'index'
project = 'ffilupa'
copyright = '2017, 2018, TitanSnow'
author = 'TitanSnow'
version = '3.0.0'
release = '3.0.0'
exclude_patterns = ['_build']

def skip_members(app, what, name, obj, skip, options):
    if name in ('__init__', '_G', '__call__'):
        return False
    return skip

def setup(app):
    app.connect("autodoc-skip-member", skip_members)
