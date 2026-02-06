#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-all}"

source "$(dirname "$0")/_common.sh"

take_down() {
  local name="$1"
  local pid_file="$2"

  if [ ! -f "$pid_file" ]; then
    echo "$name not running"
    return 0
  fi

  pid=$(cat "$pid_file")
  if is_pid_running "$pid"; then
    echo "Stopping $name (pid $pid)"
    kill "$pid" || true
    sleep 1
    if is_pid_running "$pid"; then
      echo "Force stopping $name (pid $pid)"
      kill -9 "$pid" || true
    fi
  fi
  rm -f "$pid_file"
}

case "$SERVICE" in
  backend)
    kill_port "$PORT" || true
    take_down "Backend" "$backend_pid_file"
    ;;
  frontend)
    kill_port "$FRONTEND_PORT" || true
    take_down "Frontend" "$frontend_pid_file"
    ;;
  worker)
    take_down "Worker" "$worker_pid_file"
    ;;
  all)
    kill_port "$PORT" || true
    kill_port "$FRONTEND_PORT" || true
    take_down "Backend" "$backend_pid_file"
    take_down "Frontend" "$frontend_pid_file"
    take_down "Worker" "$worker_pid_file"
    ;;
  *)
    echo "Usage: $0 [backend|frontend|worker|all]"
    exit 1
    ;;
esac
