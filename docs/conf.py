extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.todo',
    'sphinx.ext.viewcode',
    'sphinx.ext.githubpages',
]

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
html_static_path = ['_static']
html_theme_options = {
    'font_family': 'cmu_concrete, serif',
    'code_font_family': 'cmu_typewriter, monospace',
    'code_font_size': '1em',
    'head_font_family': 'cmu_sans, sans-serif',
    'description': 'cffi binding of lua for python',
    'github_user': 'TitanSnow',
    'github_repo': 'ffilupa',
    'github_type': 'star',
    'github_count': False,
    'travis_button': True,
    'codecov_button': True,
    'show_powered_by': False,
    'fixed_sidebar': True,
    'body_text_align': 'justify',
}

def skip_members(app, what, name, obj, skip, options):
    if name in ('__init__', '_G', '__call__'):
        return False
    return skip

def setup(app):
    app.connect("autodoc-skip-member", skip_members)
