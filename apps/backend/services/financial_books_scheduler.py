from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi.encoders import jsonable_encoder
from sqlalchemy import text

from database.models.branch import CompanyBranch
from database.models.company import LoanCompany
from database.models.company_operating_system import CompanyOperatingRecord
from database.session import SessionLocal
from routers.accounting import financial_books_pack_data


logger = logging.getLogger(__name__)

MASERU_TZ = ZoneInfo("Africa/Maseru")
DAILY_PREPARE_TIME = time(hour=3, minute=30)
_ADVISORY_LOCK_KEY = 604142347
_scheduler_task: asyncio.Task | None = None
_stop_event: asyncio.Event | None = None


def _snapshot_reference(business_date: date, branch_id=None) -> str:
    scope = "ALL" if branch_id is None else str(branch_id).replace("-", "")[:12].upper()
    return f"FINBOOK-{business_date:%Y%m%d}-{scope}"


def prepare_daily_financial_books(db, *, business_date: date | None = None) -> int:
    """Prepare one company-wide YTD financial-books snapshot per active company."""
    business_date = business_date or datetime.now(MASERU_TZ).date()
    from_date = date(business_date.year, 1, 1)
    prepared_at = datetime.now(MASERU_TZ)

    companies = (
        db.query(LoanCompany)
        .filter(LoanCompany.is_active.is_(True))
        .order_by(LoanCompany.id.asc())
        .all()
    )

    prepared = 0
    for company in companies:
        branches = (
            db.query(CompanyBranch)
            .filter(
                CompanyBranch.company_id == company.id,
                CompanyBranch.is_active.is_(True),
            )
            .order_by(CompanyBranch.id.asc())
            .all()
        )
        scopes = [(None, "All branches")] + [(item.id, item.name) for item in branches]

        for branch_id, scope_name in scopes:
            reference = _snapshot_reference(business_date, branch_id)
            existing_query = db.query(CompanyOperatingRecord).filter(
                CompanyOperatingRecord.company_id == company.id,
                CompanyOperatingRecord.module == "accounting",
                CompanyOperatingRecord.record_type == "financial_books_daily_snapshot",
                CompanyOperatingRecord.reference == reference,
            )
            if branch_id is None:
                existing_query = existing_query.filter(CompanyOperatingRecord.branch_id.is_(None))
            else:
                existing_query = existing_query.filter(CompanyOperatingRecord.branch_id == branch_id)
            if existing_query.first() is not None:
                continue

            try:
                pack = financial_books_pack_data(
                    db,
                    company_id=company.id,
                    from_date=from_date,
                    to_date=business_date,
                    branch_id=branch_id,
                    include_ledger_detail=False,
                )
                row = CompanyOperatingRecord(
                    company_id=company.id,
                    branch_id=branch_id,
                    module="accounting",
                    record_type="financial_books_daily_snapshot",
                    reference=reference,
                    title=f"Financial Books {business_date.isoformat()} · {scope_name}",
                    description="Automatically prepared daily Financial Books snapshot.",
                    status="prepared",
                    priority="normal",
                    data={
                        "prepared_at": prepared_at.isoformat(),
                        "timezone": "Africa/Maseru",
                        "schedule": "03:30",
                        "from_date": from_date.isoformat(),
                        "to_date": business_date.isoformat(),
                        "branch_id": str(branch_id) if branch_id else None,
                        "scope_name": scope_name,
                        "pack": jsonable_encoder(pack),
                    },
                    tags=["financial-books", "daily-snapshot", "automatic"],
                    is_archived=False,
                )
                db.add(row)
                db.commit()
                prepared += 1
            except Exception:
                db.rollback()
                logger.exception(
                    "Daily Financial Books preparation failed for company %s branch %s",
                    company.id,
                    branch_id or "all",
                )
    return prepared


def _seconds_until_next_run(now: datetime | None = None) -> float:
    now = now or datetime.now(MASERU_TZ)
    target = datetime.combine(now.date(), DAILY_PREPARE_TIME, tzinfo=MASERU_TZ)
    if now >= target:
        target += timedelta(days=1)
    return max(1.0, (target - now).total_seconds())


async def _run_cycle_with_lock(*, business_date: date | None = None) -> None:
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

        prepared = await asyncio.to_thread(
            prepare_daily_financial_books,
            db,
            business_date=business_date,
        )
        if prepared:
            logger.info("Prepared %s daily Financial Books snapshot(s)", prepared)
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


async def _scheduler_loop() -> None:
    assert _stop_event is not None

    # Catch up after a restart if today's 03:30 run was missed. Snapshot
    # references are date-idempotent, so multiple backend replicas remain safe.
    now = datetime.now(MASERU_TZ)
    if now.time() >= DAILY_PREPARE_TIME:
        try:
            await _run_cycle_with_lock(business_date=now.date())
        except Exception:
            logger.exception("Financial Books catch-up cycle failed")

    while not _stop_event.is_set():
        wait_seconds = _seconds_until_next_run()
        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=wait_seconds)
            continue
        except asyncio.TimeoutError:
            pass

        try:
            await _run_cycle_with_lock()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduled Financial Books preparation failed")


async def start_financial_books_scheduler() -> None:
    global _scheduler_task, _stop_event
    if _scheduler_task is not None and not _scheduler_task.done():
        return
    _stop_event = asyncio.Event()
    _scheduler_task = asyncio.create_task(
        _scheduler_loop(),
        name="loanhub-financial-books-0330",
    )


async def stop_financial_books_scheduler() -> None:
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
