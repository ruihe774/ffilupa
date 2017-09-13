extensions = ['sphinx.ext.autodoc', 'sphinx.ext.githubpages']

source_suffix = '.rst'
master_doc = 'index'

project = 'ffilupa'
copyright = '2017, TitanSnow'
author = 'TitanSnow'

version = '2.0'
release = '2.0.0.dev1'

exclude_patterns = ['_build']

pygments_style = 'sphinx'
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
    (master_doc, 'ffilupa.tex', 'ffilupa Documentation', 'TitanSnow', 'manual'),
]
