#!/usr/bin/env bash
set -euo pipefail

# Standardized production launcher for backend (gunicorn).
# Logs stay under logs/ per repo convention.

ROOT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

mkdir -p "$ROOT_DIR/logs"

GUNICORN_BIN="${GUNICORN_BIN:-$(command -v gunicorn || true)}"
if [ -z "${GUNICORN_BIN:-}" ]; then
  echo "gunicorn not found; install it (pip install gunicorn) or set GUNICORN_BIN" >&2
  exit 1
fi

HOST="${SERVER_HOST:-0.0.0.0}"
PORT="${SERVER_PORT:-8000}"
WORKERS="${SERVER_WORKERS:-${FASTAPI_WORKERS:-2}}"
LOG_LEVEL="${SERVER_LOG_LEVEL:-info}"
WORKER_CLASS="${GUNICORN_WORKER_CLASS:-uvicorn.workers.UvicornWorker}"
TIMEOUT="${GUNICORN_TIMEOUT:-300}"
KEEPALIVE="${GUNICORN_KEEPALIVE:-5}"

ACCESS_LOG="${GUNICORN_ACCESS_LOG:-$ROOT_DIR/logs/gunicorn-access.log}"
ERROR_LOG="${GUNICORN_ERROR_LOG:-$ROOT_DIR/logs/gunicorn-error.log}"

PYTHONPATH_VALUE="${ROOT_DIR}/backend${PYTHONPATH+:$PYTHONPATH}"

exec env PYTHONPATH="${PYTHONPATH_VALUE}" \
  "$GUNICORN_BIN" server.main:app \
  --bind "${HOST}:${PORT}" \
  --workers "${WORKERS}" \
  --worker-class "${WORKER_CLASS}" \
  --log-level "${LOG_LEVEL}" \
  --timeout "${TIMEOUT}" \
  --keepalive "${KEEPALIVE}" \
  --access-logfile "${ACCESS_LOG}" \
  --error-logfile "${ERROR_LOG}" \
  "$@"
