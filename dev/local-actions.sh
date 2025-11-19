#!/bin/bash
set -euo pipefail
cd -- "$( dirname -- "${BASH_SOURCE[0]}" )"/..

##### Run tests locally
# The intention of this script is to allow the user to run the same actions as are run by the
# GitHub Actions in the local environment, i.e. across multiple Python versions.
#
# WARNING: This script requires that you've set up `python3.X` aliases to the various Python versions!
# See also: https://github.com/haukex/toolshed/blob/main/notes/Python.md
###
# Reminder: Keep these checks in sync with `.github/workflows/tests.yml`.

usage() { echo "Usage: $0 VENV_PATH" 1>&2; exit 1; }
[[ $# -eq 1 ]] || usage
venv_path="$1"
test -d "$venv_path" || usage

activate_venv () {  # argument: python version (X.Y)
    echo "+ . $venv_path/.venv$1/{Scripts,bin}/activate"
    # Remember venv may only set up the `python` alias, not necessarily `python3`
    if [ -e "$venv_path/.venv$1/Scripts" ]; then
        # shellcheck source=/dev/null
        . "$venv_path/.venv$1/Scripts/activate"
    else
        # shellcheck source=/dev/null
        . "$venv_path/.venv$1/bin/activate"
    fi
    # Double-check:
    python_version="$( python -c 'import sys; print(".".join(map(str,sys.version_info[:2])))' )"
    if [[ "$python_version" == "$1" ]]; then
        echo "# Python $python_version at $( python -c 'import sys; print(sys.executable)' )"
    else
        echo "ERROR: Expected python $1, got $python_version"
        exit 1
    fi
}

# Reminder: Keep version list in sync with `.github/workflows/tests.yml`.
for py_ver in 3.10 3.11 3.12 3.13 3.14; do
    echo -e "\e[1;33m====================================================> Python $py_ver <====================================================\e[0m"

    if [ -e "$venv_path/.venv$py_ver" ]; then
        activate_venv $py_ver
    else
        python$py_ver -m venv "$venv_path/.venv$py_ver"
        activate_venv $py_ver
        make installdeps
    fi

    make test

    echo -e "\e[1;32m*** Done with Python $py_ver\e[0m"
done
echo -e "\n=====> \e[1;32mALL GOOD\e[0m <====="
