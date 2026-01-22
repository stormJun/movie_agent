#!/usr/bin/env bash
set -euo pipefail

# Standardized dev launcher for backend (uvicorn) and frontend (Vite).
# Logs stay under logs/ per repo convention.

ROOT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKEND_PORT="${BACKEND_PORT:-8324}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_LOG="${BACKEND_LOG:-"$ROOT_DIR/logs/backend-${BACKEND_PORT}.log"}"
BACKEND_PID_FILE="${BACKEND_PID_FILE:-"$ROOT_DIR/logs/backend-${BACKEND_PORT}.pid"}"

FRONTEND_PORT="${FRONTEND_PORT:-5174}"
FRONTEND_LOG="${FRONTEND_LOG:-"$ROOT_DIR/logs/frontend-react-vite.log"}"
FRONTEND_PID_FILE="${FRONTEND_PID_FILE:-"$ROOT_DIR/logs/frontend-react-${FRONTEND_PORT}.pid"}"

PYTHON_BIN="${PYTHON_BIN:-"$ROOT_DIR/.venv/bin/python3"}"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="$(command -v python3 || true)"
fi

NPM_BIN="${NPM_BIN:-$(command -v npm || true)}"

mkdir -p "$ROOT_DIR/logs"

_pid_alive() {
  local pid="$1"
  if [ -z "$pid" ]; then
    return 1
  fi
  kill -0 "$pid" >/dev/null 2>&1
}

start_backend() {
  if [ -z "$PYTHON_BIN" ]; then
    echo "python3 not found; set PYTHON_BIN to your interpreter" >&2
    return 1
  fi

  if pgrep -f "uvicorn server\\.main:app.*--port ${BACKEND_PORT}" >/dev/null 2>&1; then
    echo "backend already running on port ${BACKEND_PORT}" >&2
    return 0
  fi

  echo "starting backend on ${BACKEND_HOST}:${BACKEND_PORT} (log: ${BACKEND_LOG})"
  # Backend sources live under `backend/`, so set PYTHONPATH explicitly.
  local pythonpath="${ROOT_DIR}/backend${PYTHONPATH+:$PYTHONPATH}"
  nohup env PYTHONPATH="${pythonpath}" "$PYTHON_BIN" -m uvicorn server.main:app \
    --host "$BACKEND_HOST" \
    --port "$BACKEND_PORT" \
    --reload \
    --log-level info \
    >>"$BACKEND_LOG" 2>&1 &
  echo $! >"$BACKEND_PID_FILE"
}

stop_backend() {
  local pid=""
  if [ -f "$BACKEND_PID_FILE" ]; then
    pid="$(cat "$BACKEND_PID_FILE" || true)"
  fi

  local pids=""
  pids="$(pgrep -f "uvicorn server\\.main:app.*--port ${BACKEND_PORT}" || true)"
  local targets=""
  if [ -n "$pid" ]; then
    targets="$pid"
  fi
  if [ -n "$pids" ]; then
    targets="$targets $pids"
  fi
  targets="$(echo "$targets" | tr ' ' '\n' | rg -N '^[0-9]+$' | sort -u | tr '\n' ' ')"

  if [ -z "${targets// /}" ]; then
    rm -f "$BACKEND_PID_FILE"
    return 0
  fi

  echo "stopping backend pids: ${targets}"
  kill ${targets} >/dev/null 2>&1 || true

  for _ in {1..50}; do
    local still=""
    for p in $targets; do
      if _pid_alive "$p"; then
        still="$still $p"
      fi
    done
    if [ -z "${still// /}" ]; then
      break
    fi
    sleep 0.1
  done

  local remaining=""
  for p in $targets; do
    if _pid_alive "$p"; then
      remaining="$remaining $p"
    fi
  done
  if [ -n "${remaining// /}" ]; then
    echo "backend still running, sending SIGKILL to:${remaining}" >&2
    kill -9 ${remaining} >/dev/null 2>&1 || true
  fi

  rm -f "$BACKEND_PID_FILE"
}

start_frontend() {
  if [ -z "$NPM_BIN" ]; then
    echo "npm not found; set NPM_BIN or install Node.js" >&2
    return 1
  fi

  if pgrep -f "vite.*:${FRONTEND_PORT}" >/dev/null 2>&1 \
    || pgrep -f "npm run dev -- --host --port ${FRONTEND_PORT}" >/dev/null 2>&1; then
    echo "frontend already running on port ${FRONTEND_PORT}" >&2
    return 0
  fi

  echo "starting frontend (Vite) on port ${FRONTEND_PORT} (log: ${FRONTEND_LOG})"
  nohup "$NPM_BIN" --prefix "$ROOT_DIR/frontend-react" run dev -- --host --port "${FRONTEND_PORT}" \
    >>"$FRONTEND_LOG" 2>&1 &
  echo $! >"$FRONTEND_PID_FILE"
}

stop_frontend() {
  local pid=""
  if [ -f "$FRONTEND_PID_FILE" ]; then
    pid="$(cat "$FRONTEND_PID_FILE" || true)"
  fi

  if _pid_alive "$pid"; then
    echo "stopping frontend pid ${pid} (port ${FRONTEND_PORT})"
    pkill -TERM -P "$pid" >/dev/null 2>&1 || true
    kill "$pid" >/dev/null 2>&1 || true
    for _ in {1..30}; do
      if _pid_alive "$pid"; then
        sleep 0.1
      else
        break
      fi
    done
  fi

  local pids=""
  pids="$(pgrep -f "vite.*--port ${FRONTEND_PORT}" || true)"
  if [ -n "$pids" ]; then
    echo "stopping frontend (fallback) pids: ${pids}"
    kill $pids >/dev/null 2>&1 || true
    for _ in {1..50}; do
      if pgrep -f "vite.*--port ${FRONTEND_PORT}" >/dev/null 2>&1; then
        sleep 0.1
      else
        break
      fi
    done
    if pgrep -f "vite.*--port ${FRONTEND_PORT}" >/dev/null 2>&1; then
      echo "frontend still running on port ${FRONTEND_PORT}, sending SIGKILL" >&2
      pgrep -f "vite.*--port ${FRONTEND_PORT}" | xargs -I{} kill -9 {} >/dev/null 2>&1 || true
    fi
  fi

  rm -f "$FRONTEND_PID_FILE"
}

status() {
  local backend_pids=""
  local frontend_pids=""
  backend_pids="$(pgrep -f "uvicorn server\\.main:app.*--port ${BACKEND_PORT}" || true)"
  frontend_pids="$(pgrep -f "vite.*--port ${FRONTEND_PORT}" || true)"

  if [ -n "$backend_pids" ]; then
    echo "backend: running (port ${BACKEND_PORT}) pids: ${backend_pids}"
  else
    echo "backend: stopped (port ${BACKEND_PORT})"
  fi

  if [ -n "$frontend_pids" ]; then
    echo "frontend: running (port ${FRONTEND_PORT}) pids: ${frontend_pids}"
  else
    echo "frontend: stopped (port ${FRONTEND_PORT})"
  fi
}

usage() {
  cat <<EOF
Usage: $(basename "$0") [start|backend|frontend|stop|restart|status]

Targets:
  start      launch backend + frontend (default)
  backend    launch uvicorn only
  frontend   launch Vite dev server only
  stop       stop backend + frontend
  restart    restart backend + frontend
  status     show backend/frontend status

Environment knobs:
  BACKEND_PORT (default 8324)
  BACKEND_HOST (default 0.0.0.0)
  BACKEND_LOG (default logs/backend-<port>.log)
  BACKEND_PID_FILE (default logs/backend-<port>.pid)
  FRONTEND_PORT (default 5174)
  FRONTEND_LOG (default logs/frontend-react-vite.log)
  FRONTEND_PID_FILE (default logs/frontend-react-<port>.pid)
  PYTHON_BIN (default .venv/bin/python3 if present, else python3)
  NPM_BIN (default npm on PATH)
EOF
}

cmd="${1:-start}"
case "$cmd" in
  start)
    start_backend
    start_frontend
    ;;
  backend)
    start_backend
    ;;
  frontend)
    start_frontend
    ;;
  stop)
    stop_frontend
    stop_backend
    ;;
  restart)
    stop_frontend
    stop_backend
    start_backend
    start_frontend
    ;;
  status)
    status
    ;;
  *)
    usage
    exit 1
    ;;
esac
