from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.lelefa_paygate_configuration import LelefaPayGateConfiguration
from services.crypto_service import decrypt_control_secret, encrypt_control_secret


PLATFORM_SCOPE = "platform"
DEFAULT_BASE_URL = "http://169.255.58.185:8081/api/v1"
API_KEY_PURPOSE = b"loanhub-lelefapaygate-api-key-v1"
WEBHOOK_SECRET_PURPOSE = b"loanhub-lelefapaygate-webhook-secret-v1"


def _apply_runtime_defaults() -> None:
    settings.LELEFAPAYGATE_ENABLED = False
    settings.LELEFAPAYGATE_BASE_URL = DEFAULT_BASE_URL
    settings.LELEFAPAYGATE_API_KEY = None
    settings.LELEFAPAYGATE_WEBHOOK_SECRET = None
    settings.LELEFAPAYGATE_REQUEST_SIGNING_ENABLED = True
    settings.LELEFAPAYGATE_TIMEOUT_SECONDS = 15.0
    settings.LELEFAPAYGATE_WEBHOOK_TOLERANCE_SECONDS = 300
    settings.LELEFAPAYGATE_COLLECTION_PROVIDER = "mpesa"
    settings.LELEFAPAYGATE_PAYOUT_PROVIDER = "mpesa"


def get_configuration(db: Session) -> LelefaPayGateConfiguration | None:
    return (
        db.query(LelefaPayGateConfiguration)
        .filter(LelefaPayGateConfiguration.scope == PLATFORM_SCOPE)
        .first()
    )


def _decrypt_api_key(configuration: LelefaPayGateConfiguration) -> str | None:
    if not configuration.encrypted_api_key:
        return None
    if not configuration.api_key_nonce or not configuration.api_key_encryption_version:
        raise RuntimeError("Stored LelefaPayGate API key encryption metadata is incomplete")
    return decrypt_control_secret(
        configuration.encrypted_api_key,
        configuration.api_key_nonce,
        configuration.api_key_encryption_version,
        API_KEY_PURPOSE,
    )


def _decrypt_webhook_secret(configuration: LelefaPayGateConfiguration) -> str | None:
    if not configuration.encrypted_webhook_secret:
        return None
    if not configuration.webhook_secret_nonce or not configuration.webhook_secret_encryption_version:
        raise RuntimeError("Stored LelefaPayGate webhook-secret encryption metadata is incomplete")
    return decrypt_control_secret(
        configuration.encrypted_webhook_secret,
        configuration.webhook_secret_nonce,
        configuration.webhook_secret_encryption_version,
        WEBHOOK_SECRET_PURPOSE,
    )


def _valid_api_key(value: str | None) -> bool:
    return bool(value and value.startswith(("ipb_test_", "ipb_live_")) and len(value) >= 16)


def synchronize_runtime_settings(db: Session) -> LelefaPayGateConfiguration | None:
    """Load the database configuration into the process-local runtime cache.

    The database is the source of truth. The Settings fields are retained only
    as a compatibility cache for existing payment code while the integration is
    progressively migrated away from process configuration.
    """
    try:
        configuration = get_configuration(db)
    except SQLAlchemyError:
        # Keep the application usable before the migration is applied. Any
        # LelefaPayGate operation remains fail-closed until the table exists.
        db.rollback()
        _apply_runtime_defaults()
        return None

    if configuration is None:
        _apply_runtime_defaults()
        return None

    try:
        api_key = _decrypt_api_key(configuration)
        webhook_secret = _decrypt_webhook_secret(configuration)
    except (RuntimeError, ValueError):
        # A damaged or undecryptable secret must never result in a partially
        # enabled payment boundary.
        _apply_runtime_defaults()
        settings.LELEFAPAYGATE_BASE_URL = configuration.base_url or DEFAULT_BASE_URL
        return configuration

    settings.LELEFAPAYGATE_ENABLED = bool(
        configuration.enabled and _valid_api_key(api_key) and webhook_secret
    )
    settings.LELEFAPAYGATE_BASE_URL = (configuration.base_url or DEFAULT_BASE_URL).rstrip("/")
    settings.LELEFAPAYGATE_API_KEY = api_key
    settings.LELEFAPAYGATE_WEBHOOK_SECRET = webhook_secret
    settings.LELEFAPAYGATE_REQUEST_SIGNING_ENABLED = bool(configuration.request_signing_enabled)
    settings.LELEFAPAYGATE_TIMEOUT_SECONDS = float(configuration.timeout_seconds)
    settings.LELEFAPAYGATE_WEBHOOK_TOLERANCE_SECONDS = int(configuration.webhook_tolerance_seconds)
    settings.LELEFAPAYGATE_COLLECTION_PROVIDER = configuration.collection_provider
    settings.LELEFAPAYGATE_PAYOUT_PROVIDER = configuration.payout_provider
    return configuration


def _validate_base_url(value: str) -> str:
    clean = value.strip().rstrip("/")
    parsed = urlparse(clean)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("LelefaPayGate base URL must be a valid HTTP or HTTPS URL")
    if parsed.username or parsed.password:
        raise ValueError("LelefaPayGate base URL must not contain credentials")
    return clean


def _validate_api_key(value: str) -> str:
    clean = value.strip()
    if not clean.startswith(("ipb_test_", "ipb_live_")):
        raise ValueError("LelefaPayGate API key must start with ipb_test_ or ipb_live_")
    if len(clean) < 16:
        raise ValueError("LelefaPayGate API key is too short")
    return clean


def _validate_provider(value: str, field_name: str) -> str:
    clean = value.strip().lower()
    if not clean or len(clean) > 50 or not all(character.isalnum() or character in {"_", "-"} for character in clean):
        raise ValueError(f"{field_name} must be a valid provider identifier")
    return clean


def _store_api_key(configuration: LelefaPayGateConfiguration, value: str | None) -> None:
    if value is None:
        configuration.encrypted_api_key = None
        configuration.api_key_nonce = None
        configuration.api_key_encryption_version = None
        return
    ciphertext, nonce, version = encrypt_control_secret(value, API_KEY_PURPOSE)
    configuration.encrypted_api_key = ciphertext
    configuration.api_key_nonce = nonce
    configuration.api_key_encryption_version = version


def _store_webhook_secret(configuration: LelefaPayGateConfiguration, value: str | None) -> None:
    if value is None:
        configuration.encrypted_webhook_secret = None
        configuration.webhook_secret_nonce = None
        configuration.webhook_secret_encryption_version = None
        return
    ciphertext, nonce, version = encrypt_control_secret(value, WEBHOOK_SECRET_PURPOSE)
    configuration.encrypted_webhook_secret = ciphertext
    configuration.webhook_secret_nonce = nonce
    configuration.webhook_secret_encryption_version = version


def update_configuration(
    db: Session,
    *,
    enabled: bool,
    base_url: str,
    request_signing_enabled: bool,
    timeout_seconds: float,
    webhook_tolerance_seconds: int,
    collection_provider: str,
    payout_provider: str,
    api_key: str | None = None,
    webhook_secret: str | None = None,
    clear_api_key: bool = False,
    clear_webhook_secret: bool = False,
) -> LelefaPayGateConfiguration:
    configuration = get_configuration(db)
    if configuration is None:
        configuration = LelefaPayGateConfiguration(
            scope=PLATFORM_SCOPE,
            enabled=False,
            base_url=DEFAULT_BASE_URL,
        )
        db.add(configuration)
        db.flush()

    configuration.base_url = _validate_base_url(base_url)
    configuration.request_signing_enabled = bool(request_signing_enabled)
    configuration.timeout_seconds = float(timeout_seconds)
    configuration.webhook_tolerance_seconds = int(webhook_tolerance_seconds)
    configuration.collection_provider = _validate_provider(collection_provider, "Collection provider")
    configuration.payout_provider = _validate_provider(payout_provider, "Payout provider")

    if clear_api_key:
        _store_api_key(configuration, None)
    elif api_key is not None and api_key.strip():
        _store_api_key(configuration, _validate_api_key(api_key))

    if clear_webhook_secret:
        _store_webhook_secret(configuration, None)
    elif webhook_secret is not None and webhook_secret.strip():
        clean_secret = webhook_secret.strip()
        if len(clean_secret) < 12:
            raise ValueError("LelefaPayGate webhook secret is too short")
        _store_webhook_secret(configuration, clean_secret)

    if enabled and not configuration.encrypted_api_key:
        raise ValueError("Save a LelefaPayGate API key before enabling the integration")
    if enabled and not configuration.encrypted_webhook_secret:
        raise ValueError("Save a LelefaPayGate webhook secret before enabling the integration")

    configuration.enabled = bool(enabled)
    db.add(configuration)
    db.flush()
    return configuration


def configuration_summary(configuration: LelefaPayGateConfiguration | None) -> dict[str, Any]:
    if configuration is None:
        return {
            "enabled": False,
            "effective_enabled": False,
            "environment": "unconfigured",
            "base_url": DEFAULT_BASE_URL,
            "api_key_configured": False,
            "api_key_hint": None,
            "webhook_secret_configured": False,
            "request_signing_enabled": True,
            "timeout_seconds": 15.0,
            "webhook_tolerance_seconds": 300,
            "collection_provider": "mpesa",
            "payout_provider": "mpesa",
            "updated_at": None,
        }

    api_key: str | None = None
    secret_error = False
    try:
        api_key = _decrypt_api_key(configuration)
        if configuration.encrypted_webhook_secret:
            _decrypt_webhook_secret(configuration)
    except (RuntimeError, ValueError):
        secret_error = True

    valid_api_key = _valid_api_key(api_key)
    environment = (
        "test"
        if api_key and api_key.startswith("ipb_test_")
        else "live"
        if api_key and api_key.startswith("ipb_live_")
        else "unconfigured"
    )
    hint = None
    if valid_api_key and api_key:
        prefix = "ipb_test_" if api_key.startswith("ipb_test_") else "ipb_live_"
        hint = f"{prefix}••••{api_key[-4:]}"

    api_configured = bool(configuration.encrypted_api_key) and not secret_error and valid_api_key
    webhook_configured = bool(configuration.encrypted_webhook_secret) and not secret_error
    return {
        "enabled": bool(configuration.enabled),
        "effective_enabled": bool(configuration.enabled and api_configured and webhook_configured),
        "environment": environment,
        "base_url": configuration.base_url,
        "api_key_configured": api_configured,
        "api_key_hint": hint,
        "webhook_secret_configured": webhook_configured,
        "request_signing_enabled": bool(configuration.request_signing_enabled),
        "timeout_seconds": float(configuration.timeout_seconds),
        "webhook_tolerance_seconds": int(configuration.webhook_tolerance_seconds),
        "collection_provider": configuration.collection_provider,
        "payout_provider": configuration.payout_provider,
        "updated_at": configuration.updated_at,
    }
