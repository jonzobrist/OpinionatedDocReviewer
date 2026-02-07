#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-all}"

source "$(dirname "$0")/_common.sh"
ensure_dirs

start_backend() {
  if [ -f "$backend_pid_file" ]; then
    pid=$(cat "$backend_pid_file")
    if is_pid_running "$pid"; then
      echo "Backend already running (pid $pid). Restarting."
      "$(dirname "$0")/stop.sh" backend
    fi
    rm -f "$backend_pid_file"
  fi
  if is_port_in_use "$PORT"; then
    echo "Port $PORT already in use. Stop the existing process or change PORT."
    return 1
  fi

  if [ ! -d "$BACKEND_DIR" ]; then
    echo "Backend directory not found: $BACKEND_DIR"
    return 1
  fi

  local venv_python="$BACKEND_DIR/.venv/bin/python"
  local venv_uvicorn="$BACKEND_DIR/.venv/bin/uvicorn"
  echo "Starting backend on port $PORT"
  if [ -x "$venv_python" ]; then
    (cd "$BACKEND_DIR" && nohup "$venv_python" -m uvicorn app.main:app --host 0.0.0.0 --port "$PORT" > "$LOG_DIR/backend.log" 2>&1 & echo $! > "$backend_pid_file")
  elif [ -x "$venv_uvicorn" ]; then
    (cd "$BACKEND_DIR" && nohup "$venv_uvicorn" app.main:app --host 0.0.0.0 --port "$PORT" > "$LOG_DIR/backend.log" 2>&1 & echo $! > "$backend_pid_file")
  else
    (cd "$BACKEND_DIR" && UV_CACHE_DIR="$UV_CACHE_DIR" nohup uv run uvicorn app.main:app --host 0.0.0.0 --port "$PORT" > "$LOG_DIR/backend.log" 2>&1 & echo $! > "$backend_pid_file")
  fi
}

start_frontend() {
  if [ -f "$frontend_pid_file" ]; then
    pid=$(cat "$frontend_pid_file")
    if is_pid_running "$pid"; then
      echo "Frontend already running (pid $pid). Restarting."
      "$(dirname "$0")/stop.sh" frontend
    fi
    rm -f "$frontend_pid_file"
  fi

  if [ ! -d "$FRONTEND_DIR" ]; then
    echo "Frontend directory not found: $FRONTEND_DIR"
    return 1
  fi

  if [ ! -f "$FRONTEND_DIR/package.json" ]; then
    echo "Frontend not initialized (no package.json). Skipping."
    return 0
  fi

  echo "Starting frontend on port $FRONTEND_PORT"
  if ! command -v bun > /dev/null 2>&1; then
    echo "Bun is required to run the frontend. Please install bun first."
    return 1
  fi
  (cd "$FRONTEND_DIR" && PORT="$FRONTEND_PORT" UV_CACHE_DIR="$UV_CACHE_DIR" nohup bun run dev > "$LOG_DIR/frontend.log" 2>&1 & echo $! > "$frontend_pid_file")
}

start_worker() {
  if [ -f "$worker_pid_file" ]; then
    pid=$(cat "$worker_pid_file")
    if is_pid_running "$pid"; then
      echo "Worker already running (pid $pid). Restarting."
      "$(dirname "$0")/stop.sh" worker
    fi
    rm -f "$worker_pid_file"
  fi

  if [ ! -d "$BACKEND_DIR" ]; then
    echo "Backend directory not found: $BACKEND_DIR"
    return 1
  fi

  echo "Starting review worker"
  local venv_python="$BACKEND_DIR/.venv/bin/python"
  if [ -x "$venv_python" ]; then
    (cd "$BACKEND_DIR" && nohup "$venv_python" -m app.worker > "$LOG_DIR/worker.log" 2>&1 & echo $! > "$worker_pid_file")
    return 0
  fi
  if command -v uv > /dev/null 2>&1; then
    (cd "$BACKEND_DIR" && UV_CACHE_DIR="$UV_CACHE_DIR" nohup uv run python -m app.worker > "$LOG_DIR/worker.log" 2>&1 & echo $! > "$worker_pid_file")
    return 0
  else
    echo "Worker not started: uv not found and venv missing."
    return 1
  fi
}

case "$SERVICE" in
  backend)
    start_backend
    ;;
  frontend)
    start_frontend
    ;;
  worker)
    start_worker
    ;;
  all)
    start_backend
    start_frontend
    start_worker
    ;;
  *)
    echo "Usage: $0 [backend|frontend|worker|all]"
    exit 1
    ;;
esac
