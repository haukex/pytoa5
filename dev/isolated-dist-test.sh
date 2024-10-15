#!/bin/bash
set -euxo pipefail

##### Test distribution in an isolated environment
# This test takes a built .tar.gz distribution (must be passed as first argument)
# and runs the test suite on it in an isolated venv.
###

python3bin="${PYTHON3BIN:-python}"

usage() { echo "Usage: $0 DIST_FILE" 1>&2; exit 1; }
[[ $# -eq 1 ]] || usage
dist_file="$(realpath "$1")"
test -f "$dist_file" || usage

cd -- "$( dirname -- "${BASH_SOURCE[0]}" )"/..

temp_dir="$( mktemp --directory )"
trap 'set +e; popd; rm -rf "$temp_dir"' EXIT

rsync -a tests "$temp_dir" --exclude=__pycache__

pushd "$temp_dir"
$python3bin -m venv .venv
.venv/bin/python -m pip -q install --upgrade pip
.venv/bin/python -m pip install "$dist_file"
.venv/bin/python -Im unittest -v
