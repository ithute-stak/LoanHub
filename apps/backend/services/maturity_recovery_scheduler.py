from __future__ import annotations

import asyncio
import logging

from database.session import SessionLocal
from services.maturity_recovery_service import run_maturity_recovery_cycle


logger = logging.getLogger(__name__)
_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


async def _runner(interval_seconds: int) -> None:
    global _stop_event
    _stop_event = asyncio.Event()
    while not _stop_event.is_set():
        try:
            db = SessionLocal()
            try:
                result = run_maturity_recovery_cycle(db)
                if any(result.get(key, 0) for key in ("renewed", "collections_started", "reminders")):
                    logger.info(
                        "Maturity/recovery cycle: renewed=%s collections_started=%s reminders=%s skipped=%s",
                        result.get("renewed", 0),
                        result.get("collections_started", 0),
                        result.get("reminders", 0),
                        result.get("skipped", 0),
                    )
            finally:
                db.close()
        except Exception:
            logger.exception("LoanHub maturity/recovery scheduler cycle failed")

        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=max(30, interval_seconds))
        except asyncio.TimeoutError:
            continue


async def start_maturity_recovery_scheduler(interval_seconds: int = 60) -> None:
    """Run maturity and collections reminder checks continuously.

    The underlying cycle uses a PostgreSQL advisory transaction lock and
    idempotent renewal/reminder keys, so multiple application workers cannot
    create duplicate renewal cycles or duplicate reminder notifications.
    """

    global _task
    if _task and not _task.done():
        return
    _task = asyncio.create_task(
        _runner(interval_seconds),
        name="loanhub-maturity-recovery",
    )


async def stop_maturity_recovery_scheduler() -> None:
    global _task, _stop_event
    if _stop_event:
        _stop_event.set()
    if _task:
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
    _stop_event = None
