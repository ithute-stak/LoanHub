from __future__ import annotations

import asyncio
import logging

from database.session import SessionLocal
from services.treasury_service import run_treasury_cycle


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
                opened, submitted = run_treasury_cycle(db)
                if opened:
                    logger.info("Auto-opened %s branch treasury day(s)", opened)
                if submitted:
                    logger.info("Auto-submitted %s branch treasury day(s) to headquarters", submitted)
            finally:
                db.close()
        except Exception:
            logger.exception("LoanHub treasury open/submit cycle failed")
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=max(30, interval_seconds))
        except asyncio.TimeoutError:
            continue


async def start_treasury_scheduler(interval_seconds: int = 60) -> None:
    global _task
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_runner(interval_seconds), name="loanhub-treasury-auto-submit")


async def stop_treasury_scheduler() -> None:
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
