#!/bin/bash
# Run the test suite. Creates .venv on first use.
#
# The codebase needs Python 3.10+ (the system python3 here is 3.9), so we
# look for the newest available interpreter. Tests run against a throwaway
# SQLite database — they never touch Postgres.
set -e
cd "$(dirname "$0")"

PY=""
for cand in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$cand" >/dev/null 2>&1; then PY="$cand"; break; fi
done
if [ -z "$PY" ]; then
    echo "No Python 3.10+ found (codebase uses modern type hints)." >&2
    exit 1
fi

if [ ! -x .venv/bin/python ]; then
    echo "Creating .venv with $PY ..."
    if ! "$PY" -m venv .venv 2>/dev/null; then
        # No ensurepip on this system (e.g. missing python3.12-venv package):
        # bootstrap pip manually.
        "$PY" -m venv --without-pip .venv
        curl -sS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python
    fi
    .venv/bin/pip -q install -r requirements-dev.txt
fi

exec .venv/bin/python -m pytest "$@"
