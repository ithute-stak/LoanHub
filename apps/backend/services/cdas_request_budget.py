from __future__ import annotations

import hashlib
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from database.models.cdas_official import CdasApiRequestBudget
from database.models.origination import OriginationIntegrationConfiguration
from database.session import SessionLocal
from integrations.cdas import CdasError


CDAS_DAILY_REQUEST_LIMIT = 400
_CDAS_TIMEZONE = ZoneInfo("Africa/Maseru")
_CDAS_PROVIDER = "cdas"


def _local_now() -> datetime:
    return datetime.now(_CDAS_TIMEZONE)


def _budget_coordinates() -> tuple[object, datetime]:
    local_now = _local_now()
    # LoanHub DateTime columns are timezone-naive; the request date is based on
    # the Lesotho calendar day because the CDAS allowance is operated there.
    return local_now.date(), local_now.replace(tzinfo=None)


def _account_key(username: str, environment: str) -> str:
    """Return a non-reversible stable key for one CDAS API user/environment."""
    normalized = f"{environment.strip().lower()}\0{username.strip().casefold()}".encode("utf-8")
    return hashlib.sha256(normalized).hexdigest()


def _configured_username(db: Session, company_id: UUID, environment: str) -> str | None:
    row = (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == company_id,
            OriginationIntegrationConfiguration.provider == _CDAS_PROVIDER,
            OriginationIntegrationConfiguration.environment == environment,
        )
        .one_or_none()
    )
    if row is None or not isinstance(row.configuration, dict):
        return None
    username = str(row.configuration.get("username") or "").strip()
    return username or None


def consume_cdas_request_budget(company_id: UUID, environment: str) -> int:
    """Atomically reserve one outbound CDAS HTTP request per API account.

    CDAS documents the allowance per active API user, not per LoanHub company.
    The reservation therefore keys on a one-way hash of username + environment.
    A failed network attempt is still counted because CDAS may have received it,
    and conservative accounting is safer than exceeding the provider allowance.
    """
    environment = environment.strip().lower()
    request_date, now = _budget_coordinates()
    with SessionLocal() as db:
        username = _configured_username(db, company_id, environment)
        if not username:
            raise CdasError(
                status_code=503,
                message="CDAS request budget could not resolve the configured API account",
            )
        account_key = _account_key(username, environment)

        statement = insert(CdasApiRequestBudget).values(
            company_id=company_id,
            account_key=account_key,
            environment=environment,
            request_date=request_date,
            request_count=1,
            last_request_at=now,
        )
        statement = statement.on_conflict_do_update(
            constraint="uq_cdas_api_budget_account_env_date",
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
                    "LoanHub has reached the local CDAS daily request limit for this API account. "
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
    environment = environment.strip().lower()
    request_date, _ = _budget_coordinates()
    username = _configured_username(db, company_id, environment)
    if not username:
        return {
            "environment": environment,
            "request_date": request_date.isoformat(),
            "limit": CDAS_DAILY_REQUEST_LIMIT,
            "used": 0,
            "remaining": CDAS_DAILY_REQUEST_LIMIT,
            "last_request_at": None,
        }

    account_key = _account_key(username, environment)
    row = (
        db.query(CdasApiRequestBudget)
        .filter(
            CdasApiRequestBudget.account_key == account_key,
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
