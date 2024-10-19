# pylint: disable=invalid-name
# Configuration file for the Sphinx documentation builder.
import sys
import tomllib
from pathlib import Path
from sphinx.application import Sphinx
sys.path.insert(0, str(Path(__file__).parent.parent.resolve(strict=True)))
sys.path.insert(0, str((Path(__file__).parent/'_ext').resolve(strict=True)))

assert sys.version_info >= (3,13), sys.version

def _get_props() -> tuple[str, str, str]:
    with (Path(__file__).parent.parent/'pyproject.toml').open('rb') as fh:
        data = tomllib.load(fh)
    proj = data['project']
    return proj['name'], proj['authors'][0]['name'], proj['version']

project, author, version = _get_props()

copyright = '2023-2024 Hauke Dämpfling at the IGB'  # pylint: disable=redefined-builtin

nitpicky = True

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx', 'toa5_cli_doc']

autodoc_member_order = 'bysource'

html_theme = 'furo'

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'more-itertools': ('https://more-itertools.readthedocs.io/en/stable/', None),
    'pandas': ('https://pandas.pydata.org/docs/', None),
}

def process_docstring(app, what, name, obj, options, lines :list[str]):  # pylint: disable=too-many-positional-arguments,unused-argument  # noqa: E501
    if what=='module':
        # strip Copyright from modules, since that's already contained in the main Readme
        lines[ lines.index('Author, Copyright, and License') : ] = []
    return True
def setup(app :Sphinx):
    app.connect('autodoc-process-docstring', process_docstring)
