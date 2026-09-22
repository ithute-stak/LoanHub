from __future__ import annotations

from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from database.models.cdas_official import CdasApiRequestBudget
from database.session import SessionLocal
from integrations.cdas import CdasError


CDAS_DAILY_REQUEST_LIMIT = 400
_CADAS_TIMEZONE = ZoneInfo("Africa/Maseru")


def _local_now() -> datetime:
    return datetime.now(_CADAS_TIMEZONE)


def _budget_coordinates() -> tuple[object, datetime]:
    local_now = _local_now()
    # LoanHub DateTime columns are timezone-naive; the date boundary is based on
    # Lesotho local time because this integration is operated against CDAS there.
    return local_now.date(), local_now.replace(tzinfo=None)


def consume_cdas_request_budget(company_id: UUID, environment: str) -> int:
    """Atomically reserve one outbound CDAS HTTP request.

    The reservation happens before the network call. A failed network attempt is
    still counted because CDAS may have received it, and because undercounting is
    more dangerous than conservatively consuming one local request slot.
    """
    request_date, now = _budget_coordinates()
    with SessionLocal() as db:
        statement = insert(CdasApiRequestBudget).values(
            company_id=company_id,
            environment=environment,
            request_date=request_date,
            request_count=1,
            last_request_at=now,
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_cdas_api_budget_company_env_date",
            set_={
                "request_count": CdasApiRequestBudget.request_count + 1,
                "last_request_at": now,
                "updated_at": now,
            },
            where=CdasApiRequestBudget.request_count < CDAS_DAILY_REQUEST_LIMIT,
        ).returning(CdasApiRequestBudget.request_count)

        count = db.execute(statement).scalar_one_or_none()
        if count is None:
            db.rollback()
            raise CdasError(
                status_code=429,
                message=(
                    "LoanHub has reached the local CDAS daily request limit for this company/environment. "
                    "No provider request was sent."
                ),
            )
        db.commit()
        return int(count)


def get_cdas_request_budget_status(
    db: Session,
    *,
    company_id: UUID,
    environment: str,
) -> dict[str, object]:
    request_date, _ = _budget_coordinates()
    row = (
        db.query(CdasApiRequestBudget)
        .filter(
            CdasApiRequestBudget.company_id == company_id,
            CdasApiRequestBudget.environment == environment,
            CdasApiRequestBudget.request_date == request_date,
        )
        .one_or_none()
    )
    used = int(row.request_count) if row else 0
    return {
        "environment": environment,
        "request_date": request_date.isoformat(),
        "limit": CDAS_DAILY_REQUEST_LIMIT,
        "used": used,
        "remaining": max(CDAS_DAILY_REQUEST_LIMIT - used, 0),
        "last_request_at": row.last_request_at.isoformat() if row and row.last_request_at else None,
    }
