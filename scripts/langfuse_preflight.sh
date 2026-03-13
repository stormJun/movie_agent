#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${LANGFUSE_COMPOSE_FILE:-"$ROOT_DIR/docker/docker-compose.langfuse.yml"}"
LANGFUSE_HEALTH_URL="${LANGFUSE_HEALTH_URL:-http://127.0.0.1:3000/api/public/health}"
WAIT_SECONDS="${LANGFUSE_WAIT_SECONDS:-60}"

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "langfuse compose file not found: $COMPOSE_FILE" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl not found" >&2
  exit 1
fi

compose() {
  docker compose -f "$COMPOSE_FILE" "$@"
}

is_running() {
  local service="$1"
  local running_services
  running_services="$(compose ps --status running --services 2>/dev/null || true)"
  echo "$running_services" | grep -qx "$service"
}

ensure_running() {
  local services=("$@")
  local missing=()
  local svc

  for svc in "${services[@]}"; do
    if ! is_running "$svc"; then
      missing+=("$svc")
    fi
  done

  if [ "${#missing[@]}" -gt 0 ]; then
    echo "starting services: ${missing[*]}"
    compose up -d "${missing[@]}"
  fi
}

wait_for_health() {
  local deadline
  deadline=$((SECONDS + WAIT_SECONDS))

  while [ "$SECONDS" -lt "$deadline" ]; do
    local status_line
    status_line="$(docker ps --filter "name=^langfuse_server$" --format '{{.Status}}' || true)"
    if [ -n "$status_line" ] && echo "$status_line" | grep -qi "Restarting"; then
      echo "langfuse_server is restarting: $status_line"
      sleep 2
      continue
    fi

    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' "$LANGFUSE_HEALTH_URL" || true)"
    if [ "$code" = "200" ]; then
      echo "langfuse health check OK: $LANGFUSE_HEALTH_URL"
      return 0
    fi
    sleep 2
  done

  echo "langfuse health check failed after ${WAIT_SECONDS}s: $LANGFUSE_HEALTH_URL" >&2
  docker logs --tail 120 langfuse_server 2>&1 || true
  return 1
}

main() {
  # Ensure dependency services are available first, then boot app services.
  ensure_running clickhouse minio redis
  ensure_running zookeeper langfuse-worker langfuse
  wait_for_health
}

main "$@"
