#!/usr/bin/env sh
set -eu
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

test -f .env || {
    echo "Missing .env. Run ./scripts/docker-init.sh first." >&2
    exit 1
}

docker compose up -d --build
docker compose ps
