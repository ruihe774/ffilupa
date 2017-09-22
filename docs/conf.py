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

release = open('../ffilupa/version.txt').read().rstrip()
version = '.'.join(release.split('.')[:2])

exclude_patterns = ['_build']

pygments_style = 'friendly'
html_theme = 'alabaster'
html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',
        'searchbox.html',
    ]
}
html_static_path = ['_static']
html_theme_options = {
    'font_family': '"Zilla Slab", serif',
    'code_font_family': '"Fira Mono", monospace',
    'head_font_family': '"Fira Sans", sans-serif',
    'description': 'cffi binding of lua for python',
    'github_user': 'TitanSnow',
    'github_repo': 'ffilupa',
    'github_type': 'star',
    'github_count': False,
    'travis_button': True,
    'codecov_button': True,
    'fixed_sidebar': True,
    'body_text_align': 'justify',
    'badge_branch': 'ffi',
}

def skip_members(app, what, name, obj, skip, options):
    if name in ('__init__', '_G', '__call__'):
        return False
    return skip

def setup(app):
    app.connect("autodoc-skip-member", skip_members)
