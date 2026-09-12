from __future__ import annotations

import os
import sys
import time

from sqlalchemy import create_engine, text

from database.config.config import settings

max_attempts = int(os.getenv("DB_WAIT_ATTEMPTS", "45"))
delay_seconds = float(os.getenv("DB_WAIT_SECONDS", "2"))

engine = create_engine(settings.database_url, pool_pre_ping=True)

for attempt in range(1, max_attempts + 1):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        print("Database connection is ready.")
        sys.exit(0)
    except Exception as exc:  # readiness loop must tolerate every startup failure
        print(
            f"Database not ready ({attempt}/{max_attempts}): "
            f"{exc.__class__.__name__}"
        )
        time.sleep(delay_seconds)

print("Database did not become ready in time.", file=sys.stderr)
sys.exit(1)
