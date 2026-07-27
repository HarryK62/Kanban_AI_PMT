#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER_NAME="pm-app"

cd "$ROOT_DIR"
docker compose down
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
