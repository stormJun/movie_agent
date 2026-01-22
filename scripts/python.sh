#!/usr/bin/env bash
set -euo pipefail

# Canonical runner for arbitrary Python commands that need backend imports.
#
# Usage:
#   bash scripts/python.sh -c "import ..."
#   bash scripts/python.sh path/to/script.py

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
exec env PYTHONPATH="${PYTHONPATH_VALUE}" "$PYTHON_BIN" "$@"

