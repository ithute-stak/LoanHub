#!/bin/sh
set -eu

cd /app/backend
python docker/wait_for_db.py

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    alembic upgrade head
fi

uvicorn main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers "${WEB_CONCURRENCY:-2}" \
    --proxy-headers \
    --forwarded-allow-ips="*" &
BACKEND_PID=$!

python docker/maintenance.py &
MAINTENANCE_PID=$!

cd /app/frontend
node server.js &
FRONTEND_PID=$!

terminate() {
    kill -TERM "$BACKEND_PID" "$MAINTENANCE_PID" "$FRONTEND_PID" 2>/dev/null || true
    wait "$BACKEND_PID" "$MAINTENANCE_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap terminate INT TERM EXIT

while kill -0 "$BACKEND_PID" 2>/dev/null \
   && kill -0 "$MAINTENANCE_PID" 2>/dev/null \
   && kill -0 "$FRONTEND_PID" 2>/dev/null; do
    sleep 2
done

exit 1
