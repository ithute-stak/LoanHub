#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

./scripts/backup_db.sh

git pull --ff-only

docker compose build --pull api
docker compose up -d --remove-orphans

docker image prune -f

docker compose ps
