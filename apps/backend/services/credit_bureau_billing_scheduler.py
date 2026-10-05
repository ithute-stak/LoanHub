from __future__ import annotations

import asyncio
import logging

from database.session import SessionLocal
from services.credit_bureau_payg_service import (
    run_monthly_invoice_cycle,
    suspend_overdue_accounts,
)


logger = logging.getLogger(__name__)
_task: asyncio.Task | None = None
_stop: asyncio.Event | None = None


async def _run(interval_seconds: int) -> None:
    assert _stop is not None
    while not _stop.is_set():
        db = SessionLocal()
        try:
            issued = await asyncio.to_thread(run_monthly_invoice_cycle, db)
            suspended = await asyncio.to_thread(suspend_overdue_accounts, db)
            if issued:
                logger.info("Issued %s automatic Credit Bureau invoice(s)", issued)
            if suspended:
                logger.warning("Suspended %s overdue Credit Bureau account(s)", suspended)
        except Exception:
            db.rollback()
            logger.exception("Credit Bureau billing cycle failed")
        finally:
            db.close()
        try:
            await asyncio.wait_for(_stop.wait(), timeout=max(3600, interval_seconds))
        except asyncio.TimeoutError:
            pass


async def start_credit_bureau_billing_scheduler(interval_seconds: int = 21600) -> None:
    global _task, _stop
    if _task and not _task.done():
        return
    _stop = asyncio.Event()
    _task = asyncio.create_task(
        _run(interval_seconds),
        name="loanhub-credit-bureau-billing",
    )


async def stop_credit_bureau_billing_scheduler() -> None:
    global _task, _stop
    if _stop:
        _stop.set()
    if _task:
        await _task
    _task = None
    _stop = None
