#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-all}"

"$(dirname "$0")/stop.sh" "$SERVICE"
"$(dirname "$0")/start.sh" "$SERVICE"
