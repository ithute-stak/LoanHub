from __future__ import annotations

import json
import base64
import io
import zipfile
from dataclasses import dataclass
from typing import Any
from xml.etree import ElementTree

import httpx
from services.credential_service import decrypt_credential


EXPERIAN_HOSTS = {
    "sandbox": "https://apis-uat.experian.co.ls:9443",
    "uat": "https://apis-uat.experian.co.ls:9443",
    "production": "https://apis.experian.co.ls:9443",
}
NORMAL_SEARCH_PATH = "/NormalSearchService"
PING_PATH = "/PingServer/"
PREVIOUS_ENQUIRY_PATH = "/EnqIdPrevEnqService"


class ExperianConfigurationError(RuntimeError):
    pass


class ExperianRequestError(RuntimeError):
    def __init__(self, message: str, *, code: str = "experian_request_failed") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ExperianConnection:
    host: str
    environment: str


def default_experian_configuration() -> dict[str, Any]:
    """Normal Search v0.5 defaults from the supplied Experian Lesotho guide."""
    return {
        "region": "lesotho",
        "product": "normal_search_v2",
        "origin": "LNHUB",
        "origin_version": "1.0",
        "dll_version": "1.0",
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


def public_configuration(row) -> dict[str, Any]:
    if not row:
        return default_experian_configuration()
    result = default_experian_configuration()
    result.update(dict(row.configuration or {}))
    # Never allow credentials, tokens or a full arbitrary URL to leak through
    # the public configuration bag.
    for key in (
        "username",
        "password",
        "access_token",
        "refresh_token",
        "api_base_url",
    ):
        result.pop(key, None)
    return result


def _credentials(row) -> dict[str, str]:
    if not row.encrypted_credentials:
        raise ExperianConfigurationError("Experian credentials have not been configured")
    try:
        parsed = json.loads(decrypt_credential(row.encrypted_credentials))
    except (ValueError, TypeError, json.JSONDecodeError, RuntimeError) as error:
        raise ExperianConfigurationError("Stored Experian credentials are invalid") from error
    if not isinstance(parsed, dict):
        raise ExperianConfigurationError("Stored Experian credentials are invalid")
    required = ("username", "password")
    missing = [key for key in required if not str(parsed.get(key) or "").strip()]
    if missing:
        raise ExperianConfigurationError(
            "Experian username and password are required"
        )
    return {key: str(parsed[key]).strip() for key in required}


def _host(environment: str) -> str:
    value = str(environment or "sandbox").strip().lower()
    if value not in EXPERIAN_HOSTS:
        raise ExperianConfigurationError("Experian environment must be sandbox, uat or production")
    return EXPERIAN_HOSTS[value]


def test_connection(
    row,
    *,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    host = _host(row.environment)
    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client:
            response = client.get(
                f"{host}{PING_PATH}",
                headers={"Accept": "application/json, text/plain, */*"},
            )
    except httpx.TimeoutException as error:
        raise ExperianRequestError("Experian Lesotho ping timed out", code="experian_timeout") from error
    except httpx.HTTPError as error:
        raise ExperianRequestError(
            "LoanHub could not establish a secure connection to Experian Lesotho",
            code="experian_connection_failed",
        ) from error

    if response.status_code >= 400:
        raise ExperianRequestError(
            f"Experian Lesotho ping returned HTTP {response.status_code}",
            code=f"experian_ping_{response.status_code}",
        )
    return {
        "provider": "experian",
        "environment": row.environment,
        "host": host,
        "status": "connected",
        "endpoint": f"{host}{NORMAL_SEARCH_PATH}",
    }


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
        elif isinstance(current, list) and part.isdigit():
            index = int(part)
            if index < 0 or index >= len(current):
                return default
            current = current[index]
        else:
            return default
    return current


def _integer(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _number(value: Any) -> float:
    if value in (None, ""):
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
    """Normalize only explicitly configured report fields.

    The Lesotho v0.5 guide defines the request/transport contract but not the
    internal report-result schema, so LoanHub keeps the full provider result
    encrypted and does not invent score/account paths.
    """
    mapping = dict(configuration.get("response_mapping") or {})

    def mapped(name: str, default: Any = None) -> Any:
        configured = mapping.get(name)
        return _get_path(payload, configured, default) if configured else default

    return {
        "provider_reference": mapped("provider_reference"),
        "score": _integer(mapped("score")),
        "risk_band": mapped("risk_band"),
        "identity_match": _boolean(mapped("identity_match")),
        "open_accounts_count": _integer(mapped("open_accounts_count", 0)) or 0,
        "defaults_count": _integer(mapped("defaults_count", 0)) or 0,
        "judgments_count": _integer(mapped("judgments_count", 0)) or 0,
        "collections_count": _integer(mapped("collections_count", 0)) or 0,
        "recent_enquiries_count": _integer(mapped("recent_enquiries_count", 0)) or 0,
        "monthly_commitments": _number(mapped("monthly_commitments", 0)),
        "total_balance": _number(mapped("total_balance", 0)),
    }


def _require_text(value: Any, field: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ExperianConfigurationError(f"{field} is required for the Experian enquiry")
    if len(text) > max_length:
        raise ExperianConfigurationError(f"{field} exceeds Experian's {max_length}-character limit")
    return text


def _optional_text(value: Any, field: str, max_length: int) -> str:
    text = str(value or "").strip()
    if len(text) > max_length:
        raise ExperianConfigurationError(f"{field} exceeds Experian's {max_length}-character limit")
    return text


def _yn(value: Any) -> str:
    return "Y" if bool(value) else "N"


def build_normal_search_payload(row, *, context: dict[str, Any]) -> dict[str, Any]:
    credentials = _credentials(row)
    configuration = public_configuration(row)

    date_of_birth = str(context.get("date_of_birth") or "").replace("-", "")
    if len(date_of_birth) != 8 or not date_of_birth.isdigit():
        raise ExperianConfigurationError("Date of birth is required in YYYYMMDD format")

    identity = str(context.get("national_id") or context.get("passport_number") or "").strip()
    passport_flag = "N" if context.get("national_id") else "Y"
    gender = str(context.get("gender") or "").strip().upper()
    if gender not in {"M", "F"}:
        raise ExperianConfigurationError("Borrower gender must be Male or Female before running Experian")

    purpose = int(context.get("enquiry_purpose") or 12)
    if purpose < 1 or purpose > 19:
        raise ExperianConfigurationError("Experian enquiry purpose must be between 1 and 19")

    result_type = str(context.get("result_type") or "JSON").strip().upper()
    if result_type not in {"JSON", "XML"}:
        raise ExperianConfigurationError("Experian REST resultType must be JSON or XML")

    return {
        "username": credentials["username"],
        "password": credentials["password"],
        "myOrigin": _require_text(configuration.get("origin") or "LNHUB", "Experian origin", 5),
        "dllVersion": _require_text(configuration.get("dll_version") or "1.0", "Experian DLL version", 30),
        "searchCriteria": {
            "csData": _yn(context.get("cs_data", True)),
            "cpaPlusNLRData": _yn(context.get("cpa_plus_nlr_data", True)),
            "deeds": _yn(context.get("deeds", False)),
            "directors": _yn(context.get("directors", False)),
            "runCompuScore": _yn(context.get("run_compuscore", True)),
            "runCodix": _yn(context.get("run_codix", False)),
            "passportFlag": passport_flag,
            "identity_number": _require_text(identity, "Identity number", 13),
            "forename": _require_text(context.get("forename"), "Forename", 15),
            "forename2": _optional_text(context.get("forename2"), "Forename2", 15),
            "forename3": _optional_text(context.get("forename3"), "Forename3", 15),
            "surname": _require_text(context.get("surname"), "Surname", 25),
            "gender": gender,
            "dateOfBirth": date_of_birth,
            "address1": _require_text(context.get("address1"), "Address1", 25),
            "address2": _require_text(context.get("address2"), "Address2", 25),
            "address3": _optional_text(context.get("address3"), "Address3", 25),
            "address4": _optional_text(context.get("address4"), "Address4", 25),
            "postalCode": _require_text(context.get("postal_code"), "PostalCode", 5),
            "homeTelCode": _optional_text(context.get("home_tel_code"), "HomeTelCode", 7),
            "homeTelNo": _optional_text(context.get("home_tel_no"), "HomeTelNo", 13),
            "workTelCode": _optional_text(context.get("work_tel_code"), "WorkTelCode", 7),
            "workTelNo": _optional_text(context.get("work_tel_no"), "WorkTelNo", 13),
            "cellTelNo": _optional_text(context.get("cell_tel_no"), "CellTelNo", 13),
            "clientConsent": "Y",
            "adrs_Mandatory": _yn(context.get("address_mandatory", True)),
            "resultType": result_type,
            "enqPurpose": purpose,
        },
    }


def _decode_ret_data(value: Any) -> dict[str, Any]:
    text = str(value or "").strip()
    if not text:
        return {}
    try:
        data = base64.b64decode(text, validate=True)
    except Exception:
        return {"retData": text}

    decoded: dict[str, Any] = {"encoding": "base64", "size": len(data)}
    if not data.startswith(b"PK"):
        try:
            decoded["text"] = data.decode("utf-8")
        except UnicodeDecodeError:
            decoded["binary_base64"] = text
        return decoded

    documents: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for name in archive.namelist():
                body = archive.read(name)
                item: dict[str, Any] = {"name": name, "size": len(body)}
                try:
                    rendered = body.decode("utf-8")
                    item["text"] = rendered
                    if name.lower().endswith(".json"):
                        try:
                            item["json"] = json.loads(rendered)
                        except ValueError:
                            pass
                    elif name.lower().endswith(".xml"):
                        try:
                            item["xml_root"] = ElementTree.fromstring(rendered).tag
                        except ElementTree.ParseError:
                            pass
                except UnicodeDecodeError:
                    item["base64"] = base64.b64encode(body).decode("ascii")
                documents.append(item)
    except (zipfile.BadZipFile, OSError):
        return {"encoding": "base64", "binary_base64": text}

    decoded["zip"] = True
    decoded["documents"] = documents
    return decoded


def run_bureau_enquiry(
    row,
    *,
    context: dict[str, Any],
    timeout_seconds: float = 30.0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not row.is_enabled:
        raise ExperianConfigurationError("Experian is not enabled at platform level")

    host = _host(row.environment)
    configuration = public_configuration(row)
    request_payload = build_normal_search_payload(row, context=context)

    try:
        with httpx.Client(timeout=timeout_seconds, follow_redirects=False) as client:
            response = client.post(
                f"{host}{NORMAL_SEARCH_PATH}",
                headers={"Accept": "application/json", "Content-Type": "application/json"},
                json=request_payload,
            )
    except httpx.TimeoutException as error:
        raise ExperianRequestError(
            "Experian did not return the bureau enquiry before the timeout",
            code="experian_enquiry_timeout",
        ) from error
    except httpx.HTTPError as error:
        raise ExperianRequestError(
            "LoanHub could not complete the secure Experian Lesotho bureau request",
            code="experian_enquiry_connection_failed",
        ) from error

    if response.status_code >= 400:
        raise ExperianRequestError(
            f"Experian rejected the bureau enquiry with HTTP {response.status_code}",
            code=f"experian_enquiry_{response.status_code}",
        )

    try:
        envelope = response.json()
    except ValueError as error:
        raise ExperianRequestError(
            "Experian returned an unreadable JSON response",
            code="experian_enquiry_invalid_response",
        ) from error
    if not isinstance(envelope, dict):
        raise ExperianRequestError(
            "Experian returned an unexpected response shape",
            code="experian_enquiry_invalid_shape",
        )

    completed = envelope.get("transactionCompleted")
    if completed is False or str(completed).strip().lower() == "false":
        code = str(envelope.get("errorCode") or "experian_transaction_failed")
        message = str(envelope.get("errorString") or "Experian did not complete the enquiry")
        raise ExperianRequestError(message, code=code)

    raw_payload = {
        "transaction": envelope,
        "decoded": _decode_ret_data(envelope.get("retData")),
    }
    return normalize_response(raw_payload, configuration), raw_payload
