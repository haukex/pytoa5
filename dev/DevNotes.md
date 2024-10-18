Development Notes
=================

Identical to <https://github.com/haukex/my-py-templ/blob/main/dev/DevNotes.md> except:
- Documentation:
  - Requires Python 3.13! (e.g. `. ~/.venvs/pytoa5/.venv3.13/bin/activate`)
  - Build deps: `( cd docs && make installdeps )`
  - The changelog is at `docs/index.rst`
  - Build: `( cd docs && make clean all )`,
    but the actual documentation is built on GitHub
  - Check <https://github.com/haukex/pytoa5/actions/workflows/pages.yml> to make sure docs are building there
  - `git clean -dxf docs/html`
