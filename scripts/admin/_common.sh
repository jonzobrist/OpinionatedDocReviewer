#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$RUN_DIR/logs"
UV_CACHE_DIR="$RUN_DIR/uv-cache"

load_env_file() {
  local file="$1"
  if [ ! -f "$file" ]; then
    return 0
  fi
  # Load dotenv-style key/value pairs so start/restart scripts honor local runtime config.
  set -a
  set +u
  # shellcheck disable=SC1090
  source "$file"
  set -u
  set +a
}

# Load repo-level env first, then backend env for service-specific overrides.
if [ -f "$ROOT_DIR/.env" ]; then
  load_env_file "$ROOT_DIR/.env"
fi
if [ -f "$BACKEND_DIR/.env" ]; then
  load_env_file "$BACKEND_DIR/.env"
fi

PORT="${PORT:-}"
if [ -z "$PORT" ] && [ -f "$BACKEND_DIR/.env" ]; then
  PORT=$(grep -E '^PORT=' "$BACKEND_DIR/.env" | tail -n1 | cut -d= -f2 || true)
fi
PORT="${PORT:-8006}"

FRONTEND_PORT="${FRONTEND_PORT:-3000}"

backend_pid_file="$RUN_DIR/backend.pid"
frontend_pid_file="$RUN_DIR/frontend.pid"
worker_pid_file="$RUN_DIR/worker.pid"

is_pid_running() {
  local pid="$1"
  if [ -z "$pid" ]; then
    return 1
  fi
  if ps -p "$pid" > /dev/null 2>&1; then
    return 0
  fi
  return 1
}

listener_pids_for_port() {
  local port="$1"
  if [ -z "$port" ]; then
    return 0
  fi
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
    return 0
  fi
  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "sport = :$port" 2>/dev/null \
      | grep -o 'pid=[0-9]\+' \
      | cut -d= -f2 \
      | sort -u || true
    return 0
  fi
}

is_port_in_use() {
  local port="$1"
  if [ -z "$port" ]; then
    return 1
  fi
  if [ -n "$(listener_pids_for_port "$port")" ]; then
    return 0
  fi
  return 1
}

kill_pid_tree() {
  local pid="$1"
  if [ -z "$pid" ]; then
    return 0
  fi
  if ! is_pid_running "$pid"; then
    return 0
  fi
  local children
  children=$(pgrep -P "$pid" 2>/dev/null || true)
  if [ -n "$children" ]; then
    for child in $children; do
      kill_pid_tree "$child"
    done
  fi
  kill "$pid" 2>/dev/null || true
}

kill_port() {
  local port="$1"
  if [ -z "$port" ]; then
    return 1
  fi
  local pids
  pids=$(listener_pids_for_port "$port")
  if [ -n "$pids" ]; then
    echo "Stopping process(es) listening on port $port: $pids"
    for pid in $pids; do
      kill_pid_tree "$pid"
    done
  fi
}

ensure_dirs() {
  mkdir -p "$RUN_DIR" "$LOG_DIR" "$UV_CACHE_DIR"
}
