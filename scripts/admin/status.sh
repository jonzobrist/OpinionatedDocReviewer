#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-all}"

source "$(dirname "$0")/_common.sh"

listener_pid_for_port() {
  local port="$1"
  if [ -z "$port" ]; then
    return 1
  fi
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n1 || true
}

status_one() {
  local name="$1"
  local pid_file="$2"
  local port="${3:-}"

  if [ -n "$port" ]; then
    local listener_pid
    listener_pid=$(listener_pid_for_port "$port")
    if [ -n "$listener_pid" ]; then
      echo "$name: running (pid $listener_pid)"
      return 0
    fi
  fi

  if [ ! -f "$pid_file" ]; then
    echo "$name: stopped"
    return 0
  fi

  pid=$(cat "$pid_file")
  if is_pid_running "$pid"; then
    echo "$name: running (pid $pid)"
  else
    echo "$name: stale pid file (pid $pid)"
  fi
}

case "$SERVICE" in
  backend)
    status_one "Backend" "$backend_pid_file" "$PORT"
    ;;
  frontend)
    status_one "Frontend" "$frontend_pid_file" "$FRONTEND_PORT"
    ;;
  worker)
    status_one "Worker" "$worker_pid_file"
    ;;
  all)
    status_one "Backend" "$backend_pid_file" "$PORT"
    status_one "Frontend" "$frontend_pid_file" "$FRONTEND_PORT"
    status_one "Worker" "$worker_pid_file"
    ;;
  *)
    echo "Usage: $0 [backend|frontend|worker|all]"
    exit 1
    ;;
esac
