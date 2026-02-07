#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "Running backend tests..."
(cd "$BACKEND_DIR" && uv sync --extra test && uv run pytest)

echo "Running frontend tests..."
if ! command -v bun > /dev/null 2>&1; then
  echo "Bun is required to run frontend tests."
  exit 1
fi
(cd "$FRONTEND_DIR" && bun test)
