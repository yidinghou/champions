#!/usr/bin/env bash
# Gate check: run the full test suite. Exit non-zero on any failure.
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"
export PYTHONPATH="src${PYTHONPATH:+:$PYTHONPATH}"
"$PY" -m unittest discover -s tests -t . "$@"
