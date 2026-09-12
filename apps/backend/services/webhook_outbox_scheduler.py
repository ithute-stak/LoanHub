from __future__ import annotations

import asyncio
import logging

from database.session import SessionLocal
from services.webhook_outbox_service import process_outbox_batch


logger = logging.getLogger(__name__)
_task: asyncio.Task | None = None
_stop: asyncio.Event | None = None


async def _run(interval_seconds: int) -> None:
    assert _stop is not None
    while not _stop.is_set():
        db = SessionLocal()
        try:
            await asyncio.to_thread(process_outbox_batch, db)
        except Exception:
            db.rollback()
            logger.exception("Webhook outbox delivery pass failed")
        finally:
            db.close()
        try:
            await asyncio.wait_for(_stop.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            pass


async def start_webhook_outbox_scheduler(interval_seconds: int = 10) -> None:
    global _task, _stop
    if _task and not _task.done():
        return
    _stop = asyncio.Event()
    _task = asyncio.create_task(_run(max(5, interval_seconds)), name="loanhub-webhook-outbox")


async def stop_webhook_outbox_scheduler() -> None:
    global _task, _stop
    if _stop:
        _stop.set()
    if _task:
        await _task
    _task = None
    _stop = None
