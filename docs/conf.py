# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os


extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.coverage',
    'sphinx.ext.doctest',
    'sphinx.ext.extlinks',
    'sphinx.ext.ifconfig',
    'sphinx.ext.napoleon',
    'sphinx.ext.todo',
    'sphinx.ext.viewcode',
]
if os.getenv('SPELLCHECK'):
    extensions += 'sphinxcontrib.spelling',
    spelling_show_suggestions = True
    spelling_lang = 'en_US'

source_suffix = '.rst'
master_doc = 'index'
project = u'travis2docker'
year = '2016'
author = u'Vauxoo'
copyright = '{0}, {1}'.format(year, author)
version = release = u'6.4.21'

pygments_style = 'trac'
templates_path = ['.']
extlinks = {
    'issue': ('https://github.com/vauxoo/travis2docker/issues/%s', '#'),
    'pr': ('https://github.com/vauxoo/travis2docker/pull/%s', 'PR #'),
}

html_theme = 'sphinx_rtd_theme'
html_use_smartypants = True
html_last_updated_fmt = '%b %d, %Y'
html_split_index = False
html_sidebars = {
   '**': ['searchbox.html', 'globaltoc.html', 'sourcelink.html'],
}
html_short_title = '%s-%s' % (project, version)

napoleon_use_ivar = True
napoleon_use_rtype = False
napoleon_use_param = False
