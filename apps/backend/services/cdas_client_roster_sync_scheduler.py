from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import text

from database.session import SessionLocal
from services.cdas_client_roster_sync_guard import run_guarded_cdas_client_roster_sync_cycle


_ADVISORY_LOCK_KEY = 604142345
_FAILURE_RETRY_SECONDS = 6 * 60 * 60
_scheduler_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


async def _run_cycle_with_lock() -> list[dict[str, Any]]:
    db = SessionLocal()
    acquired = False
    try:
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            acquired = bool(
                db.execute(
                    text("SELECT pg_try_advisory_lock(:key)"),
                    {"key": _ADVISORY_LOCK_KEY},
                ).scalar()
            )
            if not acquired:
                return []
        else:
            acquired = True

        return await run_guarded_cdas_client_roster_sync_cycle(db)
    finally:
        if acquired and db.get_bind().dialect.name == "postgresql":
            try:
                db.execute(
                    text("SELECT pg_advisory_unlock(:key)"),
                    {"key": _ADVISORY_LOCK_KEY},
                )
            except Exception:
                db.rollback()
        db.close()


async def _scheduler_loop(interval_seconds: int) -> None:
    assert _stop_event is not None
    while not _stop_event.is_set():
        wait_seconds = interval_seconds
        try:
            # The first pass runs immediately after deployment. Companies that
            # have never bootstrapped are imported at once; completed companies
            # are touched only when the 03:45 daily boundary is due. The guarded
            # cycle persists per-company retry boundaries and the request reserve,
            # so a failed tenant cannot block other tenants or hammer CDAS.
            await _run_cycle_with_lock()
        except asyncio.CancelledError:
            raise
        except Exception:
            # Only a scheduler-level failure backs off the whole worker. Normal
            # company/provider failures are isolated by the guarded cycle above.
            wait_seconds = max(interval_seconds, _FAILURE_RETRY_SECONDS)
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=wait_seconds)
        except asyncio.TimeoutError:
            continue


async def start_cdas_client_roster_sync_scheduler(interval_seconds: int = 60) -> None:
    global _scheduler_task, _stop_event
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(
        _scheduler_loop(max(30, int(interval_seconds))),
        name="cdas-client-roster-sync",
    )


async def stop_cdas_client_roster_sync_scheduler() -> None:
    global _scheduler_task, _stop_event
    if _scheduler_task is None:
        return
    if _stop_event is not None:
        _stop_event.set()
    try:
        await _scheduler_task
    except asyncio.CancelledError:
        pass
    _scheduler_task = None
    _stop_event = None
