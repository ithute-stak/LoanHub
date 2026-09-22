from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.origination import OriginationIntegrationConfiguration
from integrations.cdas import CdasClient, CdasConfigurationError, CdasError
from services.cdas_request_budget import consume_cdas_request_budget
from services.crypto_service import decrypt_control_secret, encrypt_control_secret


CDAS_PROVIDER = "cdas"
DEFAULT_TEST_BASE_URL = "https://test-cdas-thirdpartyapi.sentraptt.com"
DEFAULT_TEST_HOST = (urlparse(DEFAULT_TEST_BASE_URL).hostname or "").lower()
PASSWORD_PURPOSE = b"loanhub-cdas-password-v1"
ALLOWED_ENVIRONMENTS = {"test", "live"}


@dataclass(frozen=True, slots=True)
class CdasCompanyCredentials:
    base_url: str
    username: str
    password: str
    timeout_seconds: float
    environment: str


_client_cache: dict[str, tuple[str, CdasClient]] = {}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _configuration_row(db: Session, company_id: UUID) -> OriginationIntegrationConfiguration | None:
    return (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == company_id,
            OriginationIntegrationConfiguration.provider == CDAS_PROVIDER,
        )
        .one_or_none()
    )


def get_configuration(db: Session, company_id: UUID) -> OriginationIntegrationConfiguration | None:
    return _configuration_row(db, company_id)


def _validate_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("CDAS base URL must be a valid HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("CDAS base URL must not contain embedded credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("CDAS base URL must not contain a query string or fragment")
    return normalized


def _validate_environment_base_url(environment: str, base_url: str) -> None:
    """Prevent the environment badge from disagreeing with the actual CDAS target."""
    if environment == "test" and base_url != DEFAULT_TEST_BASE_URL:
        raise ValueError(
            f"CDAS Test environment must use the official test URL {DEFAULT_TEST_BASE_URL}"
        )

    # A URL string can vary while still reaching the same host (hostname case,
    # explicit port, or a path). Live must never target the known Test host in
    # any of those forms.
    base_host = (urlparse(base_url).hostname or "").lower()
    if environment == "live" and base_host == DEFAULT_TEST_HOST:
        raise ValueError("CDAS Live environment cannot use the CDAS test host")


def _configuration_username(row: OriginationIntegrationConfiguration) -> str:
    configuration = row.configuration if isinstance(row.configuration, dict) else {}
    return str(configuration.get("username") or "").strip()


def _username_conflicts(
    rows: Iterable[OriginationIntegrationConfiguration],
    *,
    company_id: UUID,
    environment: str,
    username: str,
) -> bool:
    candidate = username.strip().casefold()
    for row in rows:
        if row.company_id == company_id:
            continue
        if str(row.environment or "").strip().lower() != environment:
            continue
        if _configuration_username(row).casefold() == candidate:
            return True
    return False


def _assert_username_isolated(
    db: Session,
    *,
    company_id: UUID,
    environment: str,
    username: str,
) -> None:
    rows = (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.provider == CDAS_PROVIDER,
            OriginationIntegrationConfiguration.environment == environment,
            OriginationIntegrationConfiguration.company_id != company_id,
        )
        .all()
    )
    if _username_conflicts(
        rows,
        company_id=company_id,
        environment=environment,
        username=username,
    ):
        raise ValueError(
            "This CDAS API username is already assigned to another LoanHub company in the selected environment"
        )


def _serialize_password(password: str) -> str:
    ciphertext, nonce, version = encrypt_control_secret(password, PASSWORD_PURPOSE)
    return json.dumps(
        {
            "ciphertext": ciphertext,
            "nonce": nonce,
            "version": version,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _deserialize_password(value: str | None) -> str | None:
    if not value:
        return None
    try:
        payload = json.loads(value)
        ciphertext = str(payload["ciphertext"])
        nonce = str(payload["nonce"])
        version = str(payload["version"])
        return decrypt_control_secret(ciphertext, nonce, version, PASSWORD_PURPOSE)
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise CdasConfigurationError(
            status_code=503,
            message="The stored CDAS credential could not be verified",
        ) from exc


def _configuration_values(row: OriginationIntegrationConfiguration) -> dict[str, Any]:
    value = row.configuration if isinstance(row.configuration, dict) else {}
    return value


def configuration_summary(row: OriginationIntegrationConfiguration | None) -> dict[str, Any]:
    if row is None:
        return {
            "provider": CDAS_PROVIDER,
            "environment": "test",
            "enabled": False,
            "base_url": DEFAULT_TEST_BASE_URL,
            "username": "",
            "timeout_seconds": float(settings.CDAS_TIMEOUT_SECONDS),
            "password_configured": False,
            "configured": False,
            "last_test_status": None,
            "last_tested_at": None,
        }

    configuration = _configuration_values(row)
    base_url = str(configuration.get("base_url") or "").strip()
    username = str(configuration.get("username") or "").strip()
    timeout_seconds = float(configuration.get("timeout_seconds") or settings.CDAS_TIMEOUT_SECONDS)
    password_configured = bool(row.encrypted_credentials)
    return {
        "provider": CDAS_PROVIDER,
        "environment": row.environment or "test",
        "enabled": bool(row.is_enabled),
        "base_url": base_url,
        "username": username,
        "timeout_seconds": timeout_seconds,
        "password_configured": password_configured,
        "configured": bool(base_url and username and password_configured),
        "last_test_status": row.last_test_status,
        "last_tested_at": row.last_tested_at.isoformat() if row.last_tested_at else None,
    }


def invalidate_company_client(company_id: UUID) -> None:
    _client_cache.pop(str(company_id), None)


def update_configuration(
    db: Session,
    *,
    company_id: UUID,
    configured_by_user_id: UUID,
    environment: str,
    enabled: bool,
    base_url: str,
    username: str,
    password: str | None,
    clear_password: bool,
    timeout_seconds: float,
) -> OriginationIntegrationConfiguration:
    environment = environment.strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise ValueError("CDAS environment must be either test or live")

    base_url = _validate_base_url(base_url)
    _validate_environment_base_url(environment, base_url)
    username = username.strip()
    if not username:
        raise ValueError("CDAS username is required")
    if timeout_seconds < 1 or timeout_seconds > 120:
        raise ValueError("CDAS timeout must be between 1 and 120 seconds")
    if clear_password and password:
        raise ValueError("Provide a new password or clear the existing password, not both")

    _assert_username_isolated(
        db,
        company_id=company_id,
        environment=environment,
        username=username,
    )

    row = _configuration_row(db, company_id)
    previous_environment = (
        str(row.environment or "test").strip().lower()
        if row is not None
        else None
    )
    environment_changed = row is not None and previous_environment != environment
    if row is None:
        row = OriginationIntegrationConfiguration(
            company_id=company_id,
            provider=CDAS_PROVIDER,
        )
        db.add(row)

    # Never carry an encrypted credential from Test into Live or vice versa.
    # A new environment must either receive a new password explicitly or remain
    # disabled with no stored password until one is supplied.
    encrypted_credentials = None if environment_changed else row.encrypted_credentials
    if clear_password:
        encrypted_credentials = None
    elif password is not None and password != "":
        encrypted_credentials = _serialize_password(password)

    if enabled and not encrypted_credentials:
        if environment_changed:
            raise ValueError(
                "Enter the CDAS password for the selected environment before enabling it"
            )
        raise ValueError("A CDAS password must be configured before the integration can be enabled")

    row.environment = environment
    row.is_enabled = enabled
    row.configuration = {
        "base_url": base_url,
        "username": username,
        "timeout_seconds": float(timeout_seconds),
    }
    row.encrypted_credentials = encrypted_credentials
    row.configured_by_user_id = configured_by_user_id
    # A credential/configuration change invalidates the previous connectivity result.
    row.last_test_status = None
    row.last_tested_at = None

    db.commit()
    db.refresh(row)
    invalidate_company_client(company_id)
    return row


def _credentials_from_row(
    row: OriginationIntegrationConfiguration | None,
    *,
    require_enabled: bool,
) -> CdasCompanyCredentials:
    if row is None:
        raise CdasConfigurationError(
            status_code=503,
            message="CDAS is not configured for this company",
        )
    if require_enabled and not row.is_enabled:
        raise CdasConfigurationError(
            status_code=503,
            message="CDAS is disabled for this company",
        )

    configuration = _configuration_values(row)
    try:
        base_url = _validate_base_url(str(configuration.get("base_url") or ""))
    except ValueError as exc:
        raise CdasConfigurationError(503, "This company's CDAS base URL is invalid") from exc
    username = str(configuration.get("username") or "").strip()
    if not username:
        raise CdasConfigurationError(503, "This company's CDAS username is not configured")
    password = _deserialize_password(row.encrypted_credentials)
    if not password:
        raise CdasConfigurationError(503, "This company's CDAS password is not configured")
    try:
        timeout_seconds = float(configuration.get("timeout_seconds") or settings.CDAS_TIMEOUT_SECONDS)
    except (TypeError, ValueError) as exc:
        raise CdasConfigurationError(503, "This company's CDAS timeout is invalid") from exc

    environment = str(row.environment or "test").strip().lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise CdasConfigurationError(503, "This company's CDAS environment is invalid")
    try:
        _validate_environment_base_url(environment, base_url)
    except ValueError as exc:
        raise CdasConfigurationError(
            503,
            "This company's CDAS environment and base URL do not match",
        ) from exc
    return CdasCompanyCredentials(
        base_url=base_url,
        username=username,
        password=password,
        timeout_seconds=timeout_seconds,
        environment=environment,
    )


def _client_signature(row: OriginationIntegrationConfiguration) -> str:
    configuration = _configuration_values(row)
    material = json.dumps(
        {
            "environment": row.environment,
            "enabled": bool(row.is_enabled),
            "configuration": configuration,
            "encrypted_credentials": row.encrypted_credentials or "",
        },
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()


def _request_guard(company_id: UUID, environment: str):
    def reserve() -> None:
        consume_cdas_request_budget(company_id, environment)

    return reserve


def get_company_cdas_client(db: Session, company_id: UUID) -> CdasClient:
    row = _configuration_row(db, company_id)
    credentials = _credentials_from_row(row, require_enabled=True)
    assert row is not None
    signature = _client_signature(row)
    cache_key = str(company_id)
    cached = _client_cache.get(cache_key)
    if cached is not None and cached[0] == signature:
        return cached[1]

    client = CdasClient(
        base_url=credentials.base_url,
        username=credentials.username,
        password=credentials.password,
        timeout_seconds=credentials.timeout_seconds,
        request_guard=_request_guard(company_id, credentials.environment),
    )
    _client_cache[cache_key] = (signature, client)
    return client


async def test_company_configuration(
    db: Session,
    *,
    company_id: UUID,
) -> dict[str, Any]:
    row = _configuration_row(db, company_id)
    credentials = _credentials_from_row(row, require_enabled=False)
    assert row is not None
    client = CdasClient(
        base_url=credentials.base_url,
        username=credentials.username,
        password=credentials.password,
        timeout_seconds=credentials.timeout_seconds,
        request_guard=_request_guard(company_id, credentials.environment),
    )
    try:
        await client.check_connection()
    except CdasError:
        row.last_test_status = "failed"
        row.last_tested_at = _utcnow()
        db.commit()
        invalidate_company_client(company_id)
        raise

    row.last_test_status = "connected"
    row.last_tested_at = _utcnow()
    db.commit()
    db.refresh(row)
    invalidate_company_client(company_id)
    return configuration_summary(row)
