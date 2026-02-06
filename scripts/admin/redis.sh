#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-start}"

if ! command -v redis-server >/dev/null 2>&1; then
  echo "redis-server not found. Install with: brew install redis"
  exit 1
fi

case "$ACTION" in
  start)
    if command -v brew >/dev/null 2>&1; then
      brew services start redis
    else
      redis-server
    fi
    ;;
  stop)
    if command -v brew >/dev/null 2>&1; then
      brew services stop redis
    else
      pkill redis-server || true
    fi
    ;;
  status)
    if command -v redis-cli >/dev/null 2>&1; then
      redis-cli ping
    else
      echo "redis-cli not found"
    fi
    ;;
  *)
    echo "Usage: $0 [start|stop|status]"
    exit 1
    ;;
 esac
