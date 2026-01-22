#!/usr/bin/env bash
set -euo pipefail

# Canonical unittest runner (flexible).
#
# Examples:
#   bash scripts/ut.sh discover test -v
#   bash scripts/ut.sh test.test_layer_boundary_imports -v
#   bash scripts/ut.sh discover -s test -p 'test_backend_layout.py' -v

ROOT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-"$ROOT_DIR/.venv/bin/python3"}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi
if [ -z "${PYTHON_BIN:-}" ]; then
  echo "python3 not found; set PYTHON_BIN to your interpreter" >&2
  exit 1
fi

PYTHONPATH_VALUE="${ROOT_DIR}/backend${PYTHONPATH+:$PYTHONPATH}"
exec env PYTHONPATH="${PYTHONPATH_VALUE}" "$PYTHON_BIN" -m unittest "$@"

