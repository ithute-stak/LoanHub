from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.orm import Session

from database.config.config import settings
from services.collection_followup_service import (
    assert_or_claim_collection_case,
    claim_collection_case,
    process_collection_reminders,
    release_collection_case_claim,
)
from services.maturity_renewal_service import (
    effective_auto_renewal,
    ensure_collection_case_for_loan,
    get_or_create_maturity_policy,
    process_maturity_renewals,
    renew_matured_loan,
)

MATURITY_LOCK_ID = 62106420260807


def run_maturity_recovery_cycle(db: Session, *, now: datetime | None = None, company_id: UUID | None = None) -> dict[str, int]:
    acquired = db.execute(text("SELECT pg_try_advisory_xact_lock(:lock_id)"), {"lock_id": MATURITY_LOCK_ID}).scalar()
    if not acquired:
        return {"renewed": 0, "collections_started": 0, "skipped": 0, "reminders": 0, "locked": 1}
    zone = ZoneInfo(settings.APP_TIMEZONE)
    local_now = now.astimezone(zone) if now and now.tzinfo else (now.replace(tzinfo=zone) if now else datetime.now(zone))
    result = process_maturity_renewals(db, today=local_now.date(), company_id=company_id)
    reminders = process_collection_reminders(db, now=local_now, company_id=company_id)
    db.commit()
    return {**result, "reminders": reminders, "locked": 0}


__all__ = [
    "assert_or_claim_collection_case",
    "claim_collection_case",
    "effective_auto_renewal",
    "ensure_collection_case_for_loan",
    "get_or_create_maturity_policy",
    "process_collection_reminders",
    "process_maturity_renewals",
    "release_collection_case_claim",
    "renew_matured_loan",
    "run_maturity_recovery_cycle",
]
