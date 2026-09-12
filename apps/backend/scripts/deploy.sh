#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ ! -f .env ]]; then
    echo "Missing .env. Run ./scripts/generate_secrets.sh first." >&2
    exit 1
fi

if [[ ! -f secrets/jwt_private.pem || ! -f secrets/jwt_public.pem ]]; then
    echo "Missing JWT keys. Run ./scripts/generate_secrets.sh first." >&2
    exit 1
fi

docker compose config --quiet
docker compose build --pull api
docker compose up -d --remove-orphans

docker compose ps

echo
echo "Recent API logs:"
docker compose logs --tail=40 api
