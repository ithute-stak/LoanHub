from __future__ import annotations

import asyncio
import logging

from database.session import SessionLocal
from services.cdas_autopilot_worker import run_cdas_autopilot_cycle


logger = logging.getLogger(__name__)
_task: asyncio.Task | None = None
_stop: asyncio.Event | None = None


async def _run(interval_seconds: int) -> None:
    assert _stop is not None
    while not _stop.is_set():
        db = SessionLocal()
        try:
            result = await run_cdas_autopilot_cycle(db)
            payments = result["payments"]
            affordability = result["affordability"]
            if payments["processed"] or affordability["checked"]:
                logger.info(
                    "CDAS Autopilot: payment_processed=%s settled=%s shortened=%s "
                    "affordability_checked=%s opportunities=%s topups=%s",
                    payments["processed"],
                    payments["settled"],
                    payments["shortened"],
                    affordability["checked"],
                    affordability["opportunities"],
                    affordability["topups"],
                )
        except Exception:
            db.rollback()
            logger.exception("CDAS Autopilot cycle failed")
        finally:
            db.close()

        try:
            await asyncio.wait_for(_stop.wait(), timeout=max(300, interval_seconds))
        except asyncio.TimeoutError:
            pass


async def start_cdas_autopilot_scheduler(interval_seconds: int = 3600) -> None:
    global _task, _stop
    if _task and not _task.done():
        return
    _stop = asyncio.Event()
    _task = asyncio.create_task(_run(interval_seconds), name="loanhub-cdas-autopilot")


async def stop_cdas_autopilot_scheduler() -> None:
    global _task, _stop
    if _stop:
        _stop.set()
    if _task:
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
    _stop = None
