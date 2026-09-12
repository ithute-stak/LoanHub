#!/bin/sh
set -eu

cd /app/backend

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "Running LoanHub database migrations..."
    alembic upgrade head
fi

echo "Starting LoanHub frontend and backend..."

exec /usr/bin/supervisord \
    --nodaemon \
    --configuration /etc/supervisor/supervisord.conf