from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.origination import OriginationIntegrationConfiguration
from integrations.cdas import CdasConfigurationError, CdasError
from integrations.cdas_compatible import CdasCompatibleClient as CdasClient
from integrations.cdas_session import CdasSessionBroker
from services.cdas_request_budget import consume_cdas_request_budget
from services.cdas_session_broker import RedisCdasSessionBroker
from services.platform_cdas_service import (
    decrypt_profile_password,
    get_profile,
    get_subscription,
    public_profile_state,
    require_approved_subscription,
    subscription_payload,
)


CDAS_PROVIDER = "cdas"
ALLOWED_ENVIRONMENTS = {"test", "live"}


@dataclass(frozen=True, slots=True)
class CdasCompanyCredentials:
    base_url: str
    username: str
    password: str
    item_code: str
    timeout_seconds: float
    environment: str


_client_cache: dict[str, tuple[str, CdasClient]] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _configuration_row(db: Session, company_id: UUID) -> OriginationIntegrationConfiguration | None:
    return db.query(OriginationIntegrationConfiguration).filter(
        OriginationIntegrationConfiguration.company_id == company_id,
        OriginationIntegrationConfiguration.provider == CDAS_PROVIDER,
    ).one_or_none()


def get_configuration(db: Session, company_id: UUID) -> OriginationIntegrationConfiguration | None:
    return _configuration_row(db, company_id)


def selected_environment(row: OriginationIntegrationConfiguration | None) -> str:
    if not row:
        return "test"
    environment = str(row.environment or "test").strip().lower()
    return environment if environment in ALLOWED_ENVIRONMENTS else "test"


def selected_profile(db: Session, company_id: UUID):
    row = _configuration_row(db, company_id)
    return get_profile(db, company_id=company_id, environment=selected_environment(row))


def configuration_summary(
    row: OriginationIntegrationConfiguration | None,
    *,
    db: Session | None = None,
    company_id: UUID | None = None,
) -> dict[str, Any]:
    environment = selected_environment(row)
    result = {
        "provider": CDAS_PROVIDER,
        "environment": environment,
        "enabled": bool(row.is_enabled) if row else False,
        "configured": False,
        "last_test_status": None,
        "last_tested_at": None,
        "shared_session_enabled": bool(settings.REDIS_URL),
        "reintegration_phase": "manual_documented_operations",
        "profiles": {
            "test": {"configured": False, "last_test_status": None, "last_tested_at": None},
            "live": {"configured": False, "last_test_status": None, "last_tested_at": None},
        },
    }
    if db is None or company_id is None:
        return result
    profiles = {
        env: public_profile_state(get_profile(db, company_id=company_id, environment=env))
        for env in ("test", "live")
    }
    current = profiles[environment]
    subscription = get_subscription(db, company_id=company_id)
    result.update(
        {
            "enabled": bool(subscription and subscription.status == "approved"),
            "configured": bool(current["configured"]),
            "last_test_status": current["last_test_status"],
            "last_tested_at": current["last_tested_at"],
            "profiles": profiles,
            "subscription": subscription_payload(subscription, db=db),
        }
    )
    return result


def update_selected_environment(
    db: Session,
    *,
    company_id: UUID,
    configured_by_user_id: UUID,
    environment: str,
) -> OriginationIntegrationConfiguration:
    environment = environment.strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise ValueError("CDAS environment must be either test or live")
    subscription = require_approved_subscription(db, company_id=company_id)
    profile = get_profile(db, company_id=company_id, environment=environment)
    if not profile:
        raise ValueError(f"The Platform Owner has not configured this company's CDAS {environment.title()} profile")
    if environment == "live" and profile.last_test_status != "connected":
        raise ValueError("The Platform Owner must successfully test this company's CDAS Live profile before Live can be selected")
    row = _configuration_row(db, company_id)
    if not row:
        row = OriginationIntegrationConfiguration(
            company_id=company_id,
            provider=CDAS_PROVIDER,
            configuration={},
        )
        db.add(row)
    row.environment = environment
    row.is_enabled = subscription.status == "approved"
    row.configuration = {"selected_environment": environment}
    row.encrypted_credentials = None
    row.configured_by_user_id = configured_by_user_id
    row.last_test_status = profile.last_test_status
    row.last_tested_at = profile.last_tested_at
    db.commit()
    db.refresh(row)
    invalidate_company_client(company_id)
    return row


def update_configuration(
    db: Session,
    *,
    company_id: UUID,
    configured_by_user_id: UUID,
    environment: str,
    enabled: bool,
    base_url: str,
    username: str,
    item_code: str | None,
    password: str | None,
    clear_password: bool,
    timeout_seconds: float,
) -> OriginationIntegrationConfiguration:
    raise ValueError(
        "CDAS credentials, Item Code and provider endpoints are controlled by the LoanHub Platform Owner. "
        "The Loan Company Owner may only switch the approved company between Test and Live."
    )


def invalidate_company_client(company_id: UUID) -> None:
    _client_cache.pop(str(company_id), None)


def _credentials_from_profile(db: Session, *, company_id: UUID, environment: str) -> CdasCompanyCredentials:
    profile = get_profile(db, company_id=company_id, environment=environment)
    if not profile:
        raise CdasConfigurationError(503, f"The Platform Owner has not configured this company's CDAS {environment.title()} profile")
    try:
        password = decrypt_profile_password(profile)
    except Exception as exc:
        raise CdasConfigurationError(503, "The stored CDAS credential could not be verified") from exc
    return CdasCompanyCredentials(
        base_url=profile.base_url,
        username=profile.username,
        password=password,
        item_code=str(profile.item_code or "").strip(),
        timeout_seconds=float(profile.timeout_seconds or settings.CDAS_TIMEOUT_SECONDS),
        environment=environment,
    )


def _client_signature(credentials: CdasCompanyCredentials) -> str:
    material = json.dumps(
        {
            "environment": credentials.environment,
            "base_url": credentials.base_url,
            "username": credentials.username,
            "item_code": credentials.item_code,
            "timeout_seconds": credentials.timeout_seconds,
            "password": credentials.password,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    return hashlib.sha256(material).hexdigest()


def _request_guard(company_id: UUID, environment: str):
    return lambda: consume_cdas_request_budget(company_id, environment)


def _shared_session_broker(
    credentials: CdasCompanyCredentials,
    *,
    generation: str,
) -> CdasSessionBroker | None:
    if not settings.REDIS_URL:
        return None
    return RedisCdasSessionBroker(
        username=credentials.username,
        environment=credentials.environment,
        generation=generation,
    )


def get_company_cdas_client(db: Session, company_id: UUID) -> CdasClient:
    require_approved_subscription(db, company_id=company_id)
    row = _configuration_row(db, company_id)
    environment = selected_environment(row)
    credentials = _credentials_from_profile(db, company_id=company_id, environment=environment)
    signature = _client_signature(credentials)
    key = str(company_id)
    cached = _client_cache.get(key)
    if cached is not None and cached[0] == signature:
        return cached[1]
    client = CdasClient(
        base_url=credentials.base_url,
        username=credentials.username,
        password=credentials.password,
        timeout_seconds=credentials.timeout_seconds,
        request_guard=_request_guard(company_id, environment),
        session_broker=_shared_session_broker(credentials, generation=signature),
    )
    _client_cache[key] = (signature, client)
    return client


def get_company_item_code(db: Session, company_id: UUID) -> str:
    row = _configuration_row(db, company_id)
    environment = selected_environment(row)
    profile = get_profile(db, company_id=company_id, environment=environment)
    if not profile:
        raise CdasConfigurationError(503, f"The Platform Owner has not configured this company's CDAS {environment.title()} profile")
    return str(profile.item_code or "").strip()


async def test_company_configuration(db: Session, *, company_id: UUID) -> dict[str, Any]:
    """Compatibility helper. Testing remains Platform Owner controlled at the HTTP boundary."""
    row = _configuration_row(db, company_id)
    environment = selected_environment(row)
    profile = get_profile(db, company_id=company_id, environment=environment)
    if not profile:
        raise CdasConfigurationError(503, "CDAS credential profile is not configured")
    credentials = _credentials_from_profile(db, company_id=company_id, environment=environment)
    signature = _client_signature(credentials)
    client = CdasClient(
        base_url=credentials.base_url,
        username=credentials.username,
        password=credentials.password,
        timeout_seconds=credentials.timeout_seconds,
        request_guard=_request_guard(company_id, environment),
        session_broker=_shared_session_broker(credentials, generation=signature),
    )
    try:
        await client.check_connection()
    except CdasError:
        profile.last_test_status = "failed"
        profile.last_tested_at = _utcnow()
        db.commit()
        raise
    profile.last_test_status = "connected"
    profile.last_tested_at = _utcnow()
    db.commit()
    db.refresh(profile)
    invalidate_company_client(company_id)
    return configuration_summary(row, db=db, company_id=company_id)
