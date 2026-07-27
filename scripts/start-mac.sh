#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTAINER_NAME="pm-app"
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  echo "Create it from .env.example before starting the app."
  exit 1
fi

cd "$ROOT_DIR"
docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1 || true
docker compose up --build --detach

echo "App is starting at http://localhost:8000"
