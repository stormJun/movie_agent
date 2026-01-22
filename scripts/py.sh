#!/usr/bin/env bash
set -euo pipefail

# Canonical runner for backend Python modules.
#
# Why this exists:
# - Backend code lives under `backend/`, so docs should not hand-write
#   `PYTHONPATH=backend ...` variants everywhere.
# - This script centralizes interpreter selection + PYTHONPATH wiring.
#
# Usage:
#   bash scripts/py.sh <python_module> [args...]
# Example:
#   bash scripts/py.sh infrastructure.integrations.build.main --help

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

if [ "${1:-}" = "" ] || [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  cat <<'EOF'
Usage:
  bash scripts/py.sh <python_module> [args...]

Notes:
  - This runner sets PYTHONPATH=backend (plus existing PYTHONPATH if present).
  - Prefer this in docs instead of writing `PYTHONPATH=backend python -m ...`.
EOF
  exit 0
fi

MODULE="$1"
shift

PYTHONPATH_VALUE="${ROOT_DIR}/backend${PYTHONPATH+:$PYTHONPATH}"
exec env PYTHONPATH="${PYTHONPATH_VALUE}" "$PYTHON_BIN" -m "$MODULE" "$@"

