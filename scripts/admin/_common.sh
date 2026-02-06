#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
RUN_DIR="$ROOT_DIR/.run"
LOG_DIR="$RUN_DIR/logs"
UV_CACHE_DIR="$RUN_DIR/uv-cache"

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

is_port_in_use() {
  local port="$1"
  if [ -z "$port" ]; then
    return 1
  fi
  if lsof -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

kill_port() {
  local port="$1"
  if [ -z "$port" ]; then
    return 1
  fi
  local pids
  pids=$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pids" ]; then
    echo "Stopping process(es) listening on port $port: $pids"
    kill $pids || true
  fi
}

ensure_dirs() {
  mkdir -p "$RUN_DIR" "$LOG_DIR" "$UV_CACHE_DIR"
}
