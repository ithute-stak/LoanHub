from __future__ import annotations

import asyncio

from sqlalchemy import text

from database.session import SessionLocal
from services.cdas_roster_intelligence import run_roster_sync_cycle


_ADVISORY_LOCK_KEY = 604142346
_scheduler_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


async def _run_cycle_with_lock() -> None:
    db = SessionLocal()
    acquired = False
    try:
        if db.get_bind().dialect.name == "postgresql":
            acquired = bool(
                db.execute(
                    text("SELECT pg_try_advisory_lock(:key)"),
                    {"key": _ADVISORY_LOCK_KEY},
                ).scalar()
            )
            if not acquired:
                return
        else:
            acquired = True
        await run_roster_sync_cycle(db)
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
        try:
            await _run_cycle_with_lock()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


async def start_cdas_roster_intelligence_scheduler(interval_seconds: int = 3600) -> None:
    global _scheduler_task, _stop_event
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(
        _scheduler_loop(max(300, int(interval_seconds))),
        name="cdas-roster-intelligence",
    )


async def stop_cdas_roster_intelligence_scheduler() -> None:
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
