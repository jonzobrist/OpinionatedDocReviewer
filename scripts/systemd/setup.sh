#!/usr/bin/env bash
set -euo pipefail

APP_USER="${SUDO_USER:-${USER:-}}"
REPO_ROOT=""
ENV_FILE=""
ENABLE_NOW="false"

usage() {
  cat <<'EOF'
Usage:
  sudo ./scripts/systemd/setup.sh --user <linux-user> --repo-root <repo-path> [--env-file <path>] [--enable-now]

Example:
  sudo ./scripts/systemd/setup.sh \
    --user zob \
    --repo-root /home/zob/src/OpinionatedDocReviewer \
    --enable-now

Notes:
- This installs three units:
  - opdr-backend.service
  - opdr-worker.service
  - opdr-frontend.service
- It does not modify your env file. Ensure required values exist:
  REDIS_URL, REVIEW_QUEUE_NAME, REVIEW_INLINE, OPENAI_API_KEY (or Bedrock settings), FRONTEND_PORT, PORT.
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --user)
      APP_USER="${2:-}"
      shift 2
      ;;
    --repo-root)
      REPO_ROOT="${2:-}"
      shift 2
      ;;
    --env-file)
      ENV_FILE="${2:-}"
      shift 2
      ;;
    --enable-now)
      ENABLE_NOW="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (use sudo)." >&2
  exit 1
fi

if [ -z "$APP_USER" ]; then
  echo "--user is required." >&2
  usage
  exit 1
fi

if [ -z "$REPO_ROOT" ]; then
  REPO_ROOT="/home/$APP_USER/src/OpinionatedDocReviewer"
fi

if [ -z "$ENV_FILE" ]; then
  ENV_FILE="$REPO_ROOT/.env"
fi

if [ ! -d "$REPO_ROOT" ]; then
  echo "Repo root not found: $REPO_ROOT" >&2
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Env file not found: $ENV_FILE" >&2
  exit 1
fi

for required in "$REPO_ROOT/backend" "$REPO_ROOT/frontend"; do
  if [ ! -d "$required" ]; then
    echo "Missing expected directory: $required" >&2
    exit 1
  fi
done

BACKEND_UNIT="/etc/systemd/system/opdr-backend.service"
WORKER_UNIT="/etc/systemd/system/opdr-worker.service"
FRONTEND_UNIT="/etc/systemd/system/opdr-frontend.service"

PATH_PREFIX="/home/$APP_USER/.local/bin:/home/$APP_USER/.bun/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

cat > "$BACKEND_UNIT" <<EOF
[Unit]
Description=OpinionatedDocReviewer Backend API
After=network.target redis-server.service
Wants=redis-server.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$REPO_ROOT/backend
EnvironmentFile=$ENV_FILE
Environment=PATH=$PATH_PREFIX
ExecStart=/bin/bash -lc 'uv run uvicorn app.main:app --host 0.0.0.0 --port \${PORT:-8006}'
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

cat > "$WORKER_UNIT" <<EOF
[Unit]
Description=OpinionatedDocReviewer Review Worker
After=network.target redis-server.service opdr-backend.service
Wants=redis-server.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$REPO_ROOT/backend
EnvironmentFile=$ENV_FILE
Environment=PATH=$PATH_PREFIX
ExecStart=/bin/bash -lc 'uv run python -m app.worker'
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

cat > "$FRONTEND_UNIT" <<EOF
[Unit]
Description=OpinionatedDocReviewer Frontend
After=network.target opdr-backend.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$REPO_ROOT/frontend
EnvironmentFile=$ENV_FILE
Environment=PATH=$PATH_PREFIX
ExecStart=/bin/bash -lc 'PORT=\${FRONTEND_PORT:-3001} bun run start'
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

echo "Installed:"
echo "  $BACKEND_UNIT"
echo "  $WORKER_UNIT"
echo "  $FRONTEND_UNIT"

systemctl daemon-reload

if [ "$ENABLE_NOW" = "true" ]; then
  systemctl enable --now redis-server
  systemctl enable --now opdr-backend.service
  systemctl enable --now opdr-worker.service
  systemctl enable --now opdr-frontend.service
  echo "Enabled and started redis-server + opdr-* services."
else
  cat <<'EOF'
Next steps:
  sudo systemctl enable --now redis-server
  sudo systemctl enable --now opdr-backend.service
  sudo systemctl enable --now opdr-worker.service
  sudo systemctl enable --now opdr-frontend.service

Verification:
  systemctl status opdr-backend opdr-worker opdr-frontend --no-pager
  journalctl -u opdr-worker -n 120 --no-pager
EOF
fi
