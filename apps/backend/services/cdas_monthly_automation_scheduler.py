from __future__ import annotations

import asyncio
from datetime import date

from sqlalchemy import text

from database.session import SessionLocal
from services.cdas_lifecycle_automation import run_monthly_cdas_lifecycle_automation
from services.cdas_monthly_automation import is_monthly_automation_window, local_now, run_monthly_cdas_automation
from services.cdas_sub1000_auto_modification import run_sub1000_auto_modifications


_ADVISORY_LOCK_KEY = 604142006
_scheduler_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None
_last_run_date: date | None = None


async def _run_once_if_due() -> None:
    global _last_run_date
    now = local_now()
    if not is_monthly_automation_window(now):
        return
    if _last_run_date == now.date():
        return

    db = SessionLocal()
    acquired = False
    try:
        dialect = db.get_bind().dialect.name
        if dialect == "postgresql":
            acquired = bool(db.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": _ADVISORY_LOCK_KEY}).scalar())
            if not acquired:
                return
        else:
            acquired = True

        # The monthly 06:00 cycle is deliberately ordered:
        # 1) register/approve/activate new eligible deductions;
        # 2) increase eligible sub-M1,000 deductions;
        # 3) reconcile LoanHub with the provider and settle zero-balance loans.
        # Durable borrower/deduction/day markers plus the provider-write arming
        # layer make retries idempotent and prevent blind duplicate writes.
        await run_monthly_cdas_automation(db, now=now, enforce_window=True)
        await run_sub1000_auto_modifications(db, now=now, enforce_window=True)
        await run_monthly_cdas_lifecycle_automation(db, now=now, enforce_window=True)
        _last_run_date = now.date()
    finally:
        if acquired and db.get_bind().dialect.name == "postgresql":
            try:
                db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _ADVISORY_LOCK_KEY})
            except Exception:
                db.rollback()
        db.close()


async def _scheduler_loop(interval_seconds: int) -> None:
    assert _stop_event is not None
    while not _stop_event.is_set():
        try:
            await _run_once_if_due()
        except asyncio.CancelledError:
            raise
        except Exception:
            # The next scheduler tick retries. Individual borrower/provider
            # failures are already persisted by the automation services.
            pass
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue


async def start_cdas_monthly_automation_scheduler(interval_seconds: int = 60) -> None:
    global _scheduler_task, _stop_event
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(
        _scheduler_loop(max(30, int(interval_seconds))),
        name="cdas-monthly-automation",
    )


async def stop_cdas_monthly_automation_scheduler() -> None:
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
