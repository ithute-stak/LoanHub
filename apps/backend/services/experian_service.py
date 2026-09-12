from __future__ import annotations

import json
import threading
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from database.models.origination import OriginationIntegrationConfiguration
from services.credential_service import decrypt_credential


EXPERIAN_HOSTS = {
    "sandbox": "https://sandbox-eu-api.experian.com",
    "uat": "https://uat-eu-api.experian.com",
    "production": "https://eu-api.experian.com",
}
TOKEN_PATH = "/oauth2/v1/token"
_TOKEN_CACHE: dict[str, tuple[str, float, str | None, int | None]] = {}
_TOKEN_LOCK = threading.Lock()


class ExperianConfigurationError(RuntimeError):
    pass


class ExperianRequestError(RuntimeError):
    def __init__(self, message: str, *, code: str = "experian_request_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ExperianToken:
    access_token: str
    token_type: str | None
    expires_in: int | None
    host: str


def default_experian_configuration() -> dict[str, Any]:
    """Safe defaults that do not guess a product-specific API contract."""
    return {
        "region": "emea",
        "product": "experian_one_customer_acquisition",
        "bureau_endpoint_path": "",
        "request_template": {},
        "response_mapping": {},
        "max_report_age_hours": 24,
        "require_before_affordability": False,
        "include_bureau_commitments_in_affordability": False,
        "bureau_debt_mode": "max",
        "decline_below_score": None,
        "refer_below_score": None,
        "block_defaults": False,
        "require_identity_match": False,
    }


def public_configuration(row: OriginationIntegrationConfiguration | None) -> dict[str, Any]:
    if not row:
        return default_experian_configuration()
    result = default_experian_configuration()
    result.update(dict(row.configuration or {}))
    # Never allow credentials, tokens or a full arbitrary URL to leak through
    # the public configuration bag.
    for key in (
        "username",
        "password",
        "client_id",
        "client_secret",
        "access_token",
        "refresh_token",
        "api_base_url",
    ):
        result.pop(key, None)
    return result


def _credentials(row: OriginationIntegrationConfiguration) -> dict[str, str]:
    if not row.encrypted_credentials:
        raise ExperianConfigurationError("Experian credentials have not been configured")
    try:
        parsed = json.loads(decrypt_credential(row.encrypted_credentials))
    except (ValueError, TypeError, json.JSONDecodeError, RuntimeError) as error:
        raise ExperianConfigurationError("Stored Experian credentials are invalid") from error
    if not isinstance(parsed, dict):
        raise ExperianConfigurationError("Stored Experian credentials are invalid")
    required = ("username", "password", "client_id", "client_secret")
    missing = [key for key in required if not str(parsed.get(key) or "").strip()]
    if missing:
        raise ExperianConfigurationError(
            "Experian credentials are incomplete; Developer Portal username, password, Client ID and Client Secret are required"
        )
    return {key: str(parsed[key]).strip() for key in required}


def _host(environment: str) -> str:
    value = str(environment or "sandbox").strip().lower()
    if value not in EXPERIAN_HOSTS:
        raise ExperianConfigurationError("Experian environment must be sandbox, uat or production")
    return EXPERIAN_HOSTS[value]


def _cache_key(row: OriginationIntegrationConfiguration, credentials: dict[str, str]) -> str:
    return f"{row.id}:{row.environment}:{credentials['client_id']}:{credentials['username']}"


def get_access_token(
    row: OriginationIntegrationConfiguration,
    *,
    force_refresh: bool = False,
    timeout_seconds: float = 20.0,
) -> ExperianToken:
    credentials = _credentials(row)
    host = _host(row.environment)
    key = _cache_key(row, credentials)
    now = time.monotonic()

    if not force_refresh:
        with _TOKEN_LOCK:
            cached = _TOKEN_CACHE.get(key)
            if cached and cached[1] > now:
                return ExperianToken(cached[0], cached[2], cached[3], host)

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client:
            response = client.post(
                f"{host}{TOKEN_PATH}",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Grant_type": "password",
                },
                json={
                    "username": credentials["username"],
                    "password": credentials["password"],
                    "client_id": credentials["client_id"],
                    "client_secret": credentials["client_secret"],
                },
            )
    except httpx.TimeoutException as error:
        raise ExperianRequestError("Experian did not respond before the connection timeout", code="experian_timeout") from error
    except httpx.HTTPError as error:
        raise ExperianRequestError("LoanHub could not establish a secure connection to Experian", code="experian_connection_failed") from error

    if response.status_code >= 400:
        raise ExperianRequestError(
            "Experian rejected the authentication request. Check the environment and application credentials.",
            code=f"experian_auth_{response.status_code}",
        )
    try:
        payload = response.json()
    except ValueError as error:
        raise ExperianRequestError("Experian returned an unreadable authentication response", code="experian_auth_invalid_response") from error

    token = str(payload.get("access_token") or "").strip()
    if not token:
        raise ExperianRequestError("Experian authentication succeeded without an access token", code="experian_auth_missing_token")
    try:
        expires_in = int(payload.get("expires_in")) if payload.get("expires_in") is not None else None
    except (TypeError, ValueError):
        expires_in = None
    token_type = str(payload.get("token_type") or "Bearer")
    # Experian documents 30-minute sandbox tokens. Cache conservatively and
    # refresh before expiry; no access/refresh token is persisted in LoanHub.
    ttl = max(30, min((expires_in or 1800) - 90, 1620))
    with _TOKEN_LOCK:
        _TOKEN_CACHE[key] = (token, now + ttl, token_type, expires_in)
    return ExperianToken(token, token_type, expires_in, host)


def test_connection(row: OriginationIntegrationConfiguration) -> dict[str, Any]:
    token = get_access_token(row, force_refresh=True)
    return {
        "provider": "experian",
        "environment": row.environment,
        "host": token.host,
        "status": "connected",
        "token_type": token.token_type,
        "expires_in": token.expires_in,
    }


def _validate_endpoint_path(value: Any) -> str:
    path = str(value or "").strip()
    if not path:
        raise ExperianConfigurationError(
            "Configure the product-specific Experian bureau endpoint path from the API documentation attached to your Experian app"
        )
    if not path.startswith("/") or path.startswith("//") or "://" in path or "\\" in path:
        raise ExperianConfigurationError("Experian bureau endpoint must be a relative API path, not an external URL")
    return path


def _context_value(context: dict[str, Any], key: str) -> Any:
    return context.get(key)


def _render_template(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {str(key): _render_template(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [_render_template(item, context) for item in value]
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if stripped.startswith("{{") and stripped.endswith("}}") and stripped.count("{{") == 1:
        key = stripped[2:-2].strip()
        return _context_value(context, key)
    rendered = value
    for key, item in context.items():
        rendered = rendered.replace("{{" + key + "}}", "" if item is None else str(item))
    return rendered


def _get_path(payload: Any, path: Any, default: Any = None) -> Any:
    text = str(path or "").strip()
    if not text:
        return default
    current = payload
    for part in text.split("."):
        if isinstance(current, dict):
            if part not in current:
                return default
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index < 0 or index >= len(current):
                return default
            current = current[index]
            continue
        return default
    return current


def _integer(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return 0.0


def _boolean(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"true", "yes", "1", "match", "matched", "pass", "passed"}:
        return True
    if text in {"false", "no", "0", "mismatch", "not_matched", "fail", "failed"}:
        return False
    return None


def normalize_response(payload: dict[str, Any], configuration: dict[str, Any]) -> dict[str, Any]:
    mapping = dict(configuration.get("response_mapping") or {})

    def mapped(name: str, *fallbacks: str, default: Any = None) -> Any:
        configured = mapping.get(name)
        if configured:
            return _get_path(payload, configured, default)
        for path in fallbacks:
            value = _get_path(payload, path, None)
            if value is not None:
                return value
        return default

    return {
        "provider_reference": mapped("provider_reference", "reference", "transactionId", "applicationReference"),
        "score": _integer(mapped("score", "score", "creditScore", "decision.score")),
        "risk_band": mapped("risk_band", "riskBand", "risk.band", "decision.riskBand"),
        "identity_match": _boolean(mapped("identity_match", "identityMatch", "identity.match")),
        "open_accounts_count": _integer(mapped("open_accounts_count", "openAccounts", "summary.openAccounts", default=0)) or 0,
        "defaults_count": _integer(mapped("defaults_count", "defaults", "summary.defaults", default=0)) or 0,
        "judgments_count": _integer(mapped("judgments_count", "judgments", "summary.judgments", default=0)) or 0,
        "collections_count": _integer(mapped("collections_count", "collections", "summary.collections", default=0)) or 0,
        "recent_enquiries_count": _integer(mapped("recent_enquiries_count", "recentEnquiries", "summary.recentEnquiries", default=0)) or 0,
        "monthly_commitments": _number(mapped("monthly_commitments", "monthlyCommitments", "summary.monthlyCommitments", default=0)),
        "total_balance": _number(mapped("total_balance", "totalBalance", "summary.totalBalance", default=0)),
    }


def run_bureau_enquiry(
    row: OriginationIntegrationConfiguration,
    *,
    context: dict[str, Any],
    timeout_seconds: float = 30.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not row.is_enabled:
        raise ExperianConfigurationError("Experian is not enabled for this lending company")
    configuration = public_configuration(row)
    endpoint = _validate_endpoint_path(configuration.get("bureau_endpoint_path"))
    request_template = configuration.get("request_template")
    if not isinstance(request_template, dict) or not request_template:
        raise ExperianConfigurationError(
            "Configure the Experian request template from the API documentation for the product attached to your app"
        )
    request_payload = _render_template(deepcopy(request_template), context)
    token = get_access_token(row)

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client:
            response = client.post(
                f"{token.host}{endpoint}",
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token.access_token}",
                },
                json=request_payload,
            )
    except httpx.TimeoutException as error:
        raise ExperianRequestError("Experian did not return the bureau enquiry before the timeout", code="experian_enquiry_timeout") from error
    except httpx.HTTPError as error:
        raise ExperianRequestError("LoanHub could not complete the secure Experian bureau request", code="experian_enquiry_connection_failed") from error

    if response.status_code >= 400:
        raise ExperianRequestError(
            f"Experian rejected the bureau enquiry with HTTP {response.status_code}. Review the product endpoint, sandbox test data and app permissions.",
            code=f"experian_enquiry_{response.status_code}",
        )
    try:
        raw_payload = response.json()
    except ValueError as error:
        raise ExperianRequestError("Experian returned an unreadable bureau response", code="experian_enquiry_invalid_response") from error
    if not isinstance(raw_payload, dict):
        raise ExperianRequestError("Experian returned an unexpected bureau response shape", code="experian_enquiry_invalid_shape")
    return normalize_response(raw_payload, configuration), raw_payload
