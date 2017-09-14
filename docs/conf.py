extensions = ['sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.todo',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages']

source_suffix = '.rst'
master_doc = 'index'

project = 'ffilupa'
copyright = '2017, TitanSnow'
author = 'TitanSnow'

version = '2.0'
release = '2.0.0.dev1'

language = 'en'

exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

pygments_style = 'sphinx'

todo_include_todos = True

html_theme = 'alabaster'

html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',
        'searchbox.html',
        'donate.html',
    ]
}

htmlhelp_basename = 'ffilupadoc'

latex_documents = [
    (master_doc, 'ffilupa.tex', 'ffilupa Documentation',
     'TitanSnow', 'manual'),
]

man_pages = [
    (master_doc, 'ffilupa', 'ffilupa Documentation',
     [author], 1)
]

texinfo_documents = [
    (master_doc, 'ffilupa', 'ffilupa Documentation',
     author, 'ffilupa', 'One line description of project.',
     'Miscellaneous'),
]

def skip_members(app, what, name, obj, skip, options):
    if name in ('__init__', '_G'):
        return False
    return skip

def setup(app):
    app.connect("autodoc-skip-member", skip_members)
