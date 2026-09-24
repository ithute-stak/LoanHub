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


def _retry_delay_seconds(results: list[dict[str, Any]], interval_seconds: int) -> int:
    """Return a safe delay after one scheduler cycle.

    The scheduler normally wakes every minute only to check whether work is due.
    A failed provider/bootstrap cycle must not be retried every minute because a
    bootstrap can consume many CDAS requests in one pass. Back off for six hours
    after a failure while keeping the normal lightweight due-check cadence for
    successful/no-op cycles.
    """
    if any(str(result.get("status") or "").lower() == "failed" for result in results):
        return max(interval_seconds, _FAILURE_RETRY_SECONDS)
    return interval_seconds


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
            # cycle persists its own per-company retry boundary and budget reserve.
            results = await _run_cycle_with_lock()
            wait_seconds = _retry_delay_seconds(results, interval_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            # A scheduler-level/provider failure also receives the long backoff.
            # Retrying a potentially expensive bootstrap every minute can exhaust
            # the shared CDAS daily request allowance without any user activity.
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
