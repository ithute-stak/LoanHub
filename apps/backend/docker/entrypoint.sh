#!/usr/bin/env sh
set -eu

RUNTIME_SECRETS_DIR="/run/loanhub-secrets"
SOURCE_PRIVATE_KEY="${JWT_PRIVATE_KEY_PATH:-/app/secrets/jwt_private.pem}"
SOURCE_PUBLIC_KEY="${JWT_PUBLIC_KEY_PATH:-/app/secrets/jwt_public.pem}"

if [ ! -r "$SOURCE_PRIVATE_KEY" ] || [ ! -r "$SOURCE_PUBLIC_KEY" ]; then
    echo "JWT key files are missing. Run ./scripts/docker-init.sh first." >&2
    exit 1
fi

install -d -o app -g app -m 700 "$RUNTIME_SECRETS_DIR"
install -o app -g app -m 600 "$SOURCE_PRIVATE_KEY" "$RUNTIME_SECRETS_DIR/jwt_private.pem"
install -o app -g app -m 644 "$SOURCE_PUBLIC_KEY" "$RUNTIME_SECRETS_DIR/jwt_public.pem"

export JWT_PRIVATE_KEY_PATH="$RUNTIME_SECRETS_DIR/jwt_private.pem"
export JWT_PUBLIC_KEY_PATH="$RUNTIME_SECRETS_DIR/jwt_public.pem"

mkdir -p /app/media/uploads
chown -R app:app /app/media

gosu app python /app/docker/wait_for_db.py

# Compose commands such as Alembic and the maintenance worker are executed as-is.
if [ "$#" -gt 0 ]; then
    exec gosu app "$@"
fi

if [ "${RUN_MIGRATIONS:-false}" = "true" ]; then
    echo "Applying Alembic migrations..."
    gosu app alembic upgrade head
fi

exec gosu app uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${WEB_CONCURRENCY:-2}" \
    --proxy-headers \
    --forwarded-allow-ips="*"
