#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="pm-app"
CONTAINER_NAME="pm-app"
ENV_FILE="$ROOT_DIR/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE"
  echo "Create it from .env.example before starting the app."
  exit 1
fi

docker build -t "$IMAGE_NAME" "$ROOT_DIR"

if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

docker run \
  --detach \
  --name "$CONTAINER_NAME" \
  --env-file "$ENV_FILE" \
  --publish 8000:8000 \
  "$IMAGE_NAME"

echo "App is starting at http://localhost:8000"
