# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import os
import sys
from importlib import metadata

sys.path.insert(0, os.path.abspath(".."))
sys.path.insert(0, os.path.abspath("../sphinxcontrib_screenshot"))

# -- General configuration ------------------------------------------------

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.graphviz",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.viewcode",
    "sphinxcontrib.screenshot",
    "myst_parser",
]

master_doc = "index"
project = "sphinxcontrib-screenshot"
year = datetime.datetime.now().strftime("%Y")
author = "Shuhei Iitsuka"
copyright = f"{year}, {author}"
source_suffix = {
    ".rst": "restructuredtext",
    ".txt": "markdown",
    ".md": "markdown",
}

version = metadata.version("sphinxcontrib-screenshot")
language = "en"
pygments_style = "sphinx"
todo_include_todos = True
toctree_collapse = False

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "sphinx": ("https://www.sphinx-doc.org/en/master/", None),
}

# -- Options for HTML output ----------------------------------------------

html_theme = "shibuya"
html_baseurl = "https://sphinxcontrib-screenshot.readthedocs.io"
html_theme_options = {
    "page_layout": "compact",
    "github_url": "https://github.com/tushuhei/sphinxcontrib-screenshot",
}
html_context = {
    "source_type": "github",
    "source_user": "tushuhei",
    "source_repo": "sphinxcontrib-screenshot",
    "source_version": "main",
    "source_docs_path": "/doc/",
}
