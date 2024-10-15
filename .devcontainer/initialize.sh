#!/bin/bash
set -euxo pipefail
cd -- "$( dirname -- "${BASH_SOURCE[0]}" )"/..

# set up venv in $HOME (the /workspaces mount can be slow in some containers)
python_version="$( python -c 'import sys; print(".".join(map(str,sys.version_info[:2])))' )"
venv_dir="$HOME/.venvs/$( basename -- "$PWD" )/.venv$python_version"
python -m venv "$venv_dir"
# shellcheck source=/dev/null
source "$venv_dir/bin/activate"

make installdeps

# make sure all files are owned by us (but only if we already own this directory) - sometimes needed on e.g. DevPod
[[ "$(stat --printf="%u" .)" -eq "$(id -u)" ]] && sudo -n chown -Rc "$(id -u)" .
simple-perms -mr .
