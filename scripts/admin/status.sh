#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-all}"

source "$(dirname "$0")/_common.sh"

status_one() {
  local name="$1"
  local pid_file="$2"

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
    status_one "Backend" "$backend_pid_file"
    ;;
  frontend)
    status_one "Frontend" "$frontend_pid_file"
    ;;
  worker)
    status_one "Worker" "$worker_pid_file"
    ;;
  all)
    status_one "Backend" "$backend_pid_file"
    status_one "Frontend" "$frontend_pid_file"
    status_one "Worker" "$worker_pid_file"
    ;;
  *)
    echo "Usage: $0 [backend|frontend|worker|all]"
    exit 1
    ;;
esac
