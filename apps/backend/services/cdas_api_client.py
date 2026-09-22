from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

import httpx

from database.config.config import settings


class CdasRequestType(IntEnum):
    """Request-type values documented by CDAS Third Party API v1.5.

    The duplicated numeric values are intentional: the CDAS document assigns
    the same value to Reject/Cancelled and AutoSettled/Expired. Do not change
    these aliases without confirmation from CDAS.
    """

    REGISTRATION = 1
    REVIEW = 3
    APPROVE = 4
    ACTIVE = 5
    REJECT = 6
    CANCELLED = 6
    SETTLED = 7
    AUTO_SETTLED = 8
    EXPIRED = 8
    DELETE = 9
    CHANGE_UPDATE = 10


class CdasDeductionStatus(IntEnum):
    REGISTERED = 1
    RESERVED = 2
    REVIEWED = 3
    APPROVED = 4
    ACTIVE = 5
    CANCELLED = 6
    SETTLED = 7
    AUTO_SETTLED = 8
    EXPIRED = 8
    DELETED = 9
    CHANGED = 10


class CdasSettlementReason(IntEnum):
    POLICY_EXPIRED = 1
    PAID_BY_EMPLOYEE = 2
    CONSOLIDATION = 3
    DECEASED_EMPLOYEE = 4


class CdasDeductionType(IntEnum):
    LOAN = 1
    POLICY = 2


class CdasDocumentType(IntEnum):
    OUTPUT_FILE = 1
    STATEMENT = 2


class CdasConfigurationError(RuntimeError):
    """Raised when LoanHub has not been configured to call CDAS."""


class CdasTransportError(RuntimeError):
    """Raised when CDAS could not be reached or timed out."""


class CdasApiError(RuntimeError):
    """Normalized non-success response returned by CDAS."""

    def __init__(self, status_code: int, message: str, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.payload = payload


@dataclass(slots=True)
class _TokenState:
    value: str
    issued_monotonic: float
    last_used_monotonic: float


class CdasApiClient:
    """Backend-only client for the official CDAS Third Party API v1.5.

    CDAS documents an eight-hour token lifetime and expiry after ten minutes of
    inactivity. LoanHub deliberately refreshes slightly before those limits.
    Authentication is endpoint-specific because the employee-details endpoint
    documents an ``Authorization`` header while the remaining authenticated
    endpoints document ``Token``.
    """

    LOGIN_PATH = "/api/security/login"
    EMPLOYEE_DETAILS_PATH = "/api/employee/getDetails"
    AFFORDABILITY_PATH = "/api/employee/check-affordability"
    VIEW_ALL_DEDUCTIONS_PATH = "/api/policy/view-all-deduction"
    VIEW_DEDUCTIONS_PATH = "/api/policy/view-deduction"
    ADD_UPDATE_DEDUCTION_PATH = "/api/policy/add-update-deduction"
    ACTIVE_APPROVED_DEDUCTION_PATH = "/api/policy/get-active-and-approved-deduction"
    MODIFY_ACTIVE_DEDUCTION_PATH = "/api/policy/modify-active-deduction"
    SETTLED_DEDUCTION_PATH = "/api/policy/settled-deduction"
    GET_DOCUMENT_PATH = "/api/policy/get_document"

    # Keep a safety margin below the limits stated by CDAS.
    TOKEN_MAX_AGE_SECONDS = 7 * 60 * 60 + 50 * 60
    TOKEN_IDLE_SECONDS = 9 * 60

    def __init__(
        self,
        *,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url if base_url is not None else settings.CDAS_BASE_URL) or ""
        self.base_url = self.base_url.rstrip("/")
        self.username = username if username is not None else settings.CDAS_USERNAME
        self.password = password if password is not None else settings.CDAS_PASSWORD
        self.timeout_seconds = (
            timeout_seconds if timeout_seconds is not None else settings.CDAS_TIMEOUT_SECONDS
        )
        self._transport = transport
        self._http: httpx.AsyncClient | None = None
        self._token: _TokenState | None = None
        self._token_lock = asyncio.Lock()

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.username and self.password)

    def _require_configuration(self) -> None:
        if not settings.CDAS_ENABLED and self._transport is None:
            raise CdasConfigurationError("CDAS integration is disabled")
        if not self.configured:
            raise CdasConfigurationError(
                "CDAS integration requires a base URL, username and password"
            )

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(self.timeout_seconds),
                transport=self._transport,
                headers={"Accept": "application/json"},
            )
        return self._http

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None
        self.invalidate_token()

    def invalidate_token(self) -> None:
        self._token = None

    def _token_is_fresh(self, now: float) -> bool:
        token = self._token
        if token is None:
            return False
        return (
            now - token.issued_monotonic < self.TOKEN_MAX_AGE_SECONDS
            and now - token.last_used_monotonic < self.TOKEN_IDLE_SECONDS
        )

    async def _get_token(self, *, force_refresh: bool = False) -> str:
        self._require_configuration()
        now = time.monotonic()
        if not force_refresh and self._token_is_fresh(now):
            assert self._token is not None
            return self._token.value

        async with self._token_lock:
            now = time.monotonic()
            if not force_refresh and self._token_is_fresh(now):
                assert self._token is not None
                return self._token.value
            return await self._login()

    async def _login(self) -> str:
        client = await self._client()
        try:
            response = await client.post(
                self.LOGIN_PATH,
                json={"Username": self.username, "Password": self.password},
            )
        except httpx.TimeoutException as exc:
            raise CdasTransportError("CDAS authentication timed out") from exc
        except httpx.RequestError as exc:
            raise CdasTransportError("CDAS authentication could not reach the server") from exc

        payload = self._response_payload(response)
        if response.status_code < 200 or response.status_code >= 300:
            raise CdasApiError(
                response.status_code,
                self._error_message(payload, response.status_code),
                payload,
            )
        if not isinstance(payload, dict):
            raise CdasApiError(502, "CDAS login returned an unexpected response", payload)

        token = payload.get("Authorization")
        if not isinstance(token, str) or not token.strip():
            raise CdasApiError(502, "CDAS login response did not contain Authorization", payload)

        now = time.monotonic()
        self._token = _TokenState(
            value=token.strip(),
            issued_monotonic=now,
            last_used_monotonic=now,
        )
        return self._token.value

    @staticmethod
    def _response_payload(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            text = response.text.strip()
            return text if text else None

    @staticmethod
    def _error_message(payload: Any, status_code: int) -> str:
        if isinstance(payload, dict):
            for key in ("message", "Message", "detail", "Detail", "error", "Error"):
                value = payload.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
        if isinstance(payload, str) and payload.strip():
            return payload.strip()
        return f"CDAS request failed with HTTP {status_code}"

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        auth_header: str,
        retry_expired_token: bool = True,
    ) -> Any:
        token = await self._get_token()
        client = await self._client()
        try:
            response = await client.post(path, json=payload, headers={auth_header: token})
        except httpx.TimeoutException as exc:
            raise CdasTransportError("CDAS request timed out") from exc
        except httpx.RequestError as exc:
            raise CdasTransportError("CDAS server could not be reached") from exc

        # CDAS documents 401 for the eight-hour token expiry and 402 for the
        # ten-minute inactivity expiry. Retry exactly once after a new login.
        if response.status_code in {401, 402} and retry_expired_token:
            self.invalidate_token()
            refreshed_token = await self._get_token(force_refresh=True)
            try:
                response = await client.post(
                    path,
                    json=payload,
                    headers={auth_header: refreshed_token},
                )
            except httpx.TimeoutException as exc:
                raise CdasTransportError("CDAS request timed out after re-authentication") from exc
            except httpx.RequestError as exc:
                raise CdasTransportError(
                    "CDAS server could not be reached after re-authentication"
                ) from exc

        response_payload = self._response_payload(response)
        if response.status_code < 200 or response.status_code >= 300:
            raise CdasApiError(
                response.status_code,
                self._error_message(response_payload, response.status_code),
                response_payload,
            )

        if self._token is not None:
            self._token.last_used_monotonic = time.monotonic()
        return response_payload

    async def get_employee(self, employee_no: str) -> Any:
        return await self._post(
            self.EMPLOYEE_DETAILS_PATH,
            {"EmployeeNo": employee_no},
            auth_header="Authorization",
        )

    async def check_affordability(self, employee_no: str) -> Any:
        return await self._post(
            self.AFFORDABILITY_PATH,
            {"EmployeeNo": employee_no},
            auth_header="Token",
        )

    async def view_all_deductions(self, employee_no: str) -> Any:
        return await self._post(
            self.VIEW_ALL_DEDUCTIONS_PATH,
            {"EmployeeNo": employee_no},
            auth_header="Token",
        )

    async def view_deductions(self, employee_no: str, deduction_status: int) -> Any:
        return await self._post(
            self.VIEW_DEDUCTIONS_PATH,
            {"EmployeeNo": employee_no, "DeductionStatus": deduction_status},
            auth_header="Token",
        )

    async def add_update_deduction(
        self,
        *,
        request_type: int,
        deduction_id: int,
        employee_no: str,
        loan_policy: int,
        item_code: str,
        deduction_amount: float,
        total_installment: int,
        principal_amount: float,
        effective_month: str,
        reference_no: str,
    ) -> Any:
        return await self._post(
            self.ADD_UPDATE_DEDUCTION_PATH,
            {
                "RequestType": request_type,
                "DeductionID": deduction_id,
                "EmployeeNo": employee_no,
                "LoanPolicy": loan_policy,
                "ItemCode": item_code,
                "DeductionAmount": deduction_amount,
                "TotalInstallment": total_installment,
                "PrincipalAmount": principal_amount,
                "EffectiveMonth": effective_month,
                "ReferenceNo": reference_no,
            },
            auth_header="Token",
        )

    async def get_active_and_approved_deduction(self, employee_no: str) -> Any:
        return await self._post(
            self.ACTIVE_APPROVED_DEDUCTION_PATH,
            {"EmployeeNo": employee_no},
            auth_header="Token",
        )

    async def modify_active_deduction(
        self,
        *,
        employee_no: str,
        item_code: str,
        total_installment: int,
        deduction_amount: float,
        principal_amount: float,
        deduction_id: int,
        effective_date: str,
    ) -> Any:
        return await self._post(
            self.MODIFY_ACTIVE_DEDUCTION_PATH,
            {
                "EmployeeNo": employee_no,
                "ItemCode": item_code,
                "TotalInstallment": total_installment,
                "DeductionAmount": deduction_amount,
                "PrincipalAmount": principal_amount,
                "DeductionID": deduction_id,
                "EffectiveDate": effective_date,
            },
            auth_header="Token",
        )

    async def settle_deduction(
        self,
        *,
        item_code: str,
        deduction_id: int,
        effective_date: str,
        employee_no: str,
        settlement_reason: int,
    ) -> Any:
        return await self._post(
            self.SETTLED_DEDUCTION_PATH,
            {
                "ItemCode": item_code,
                "DeductionID": deduction_id,
                "EffectiveDate": effective_date,
                "EmployeeNo": employee_no,
                "SettlementReason": settlement_reason,
            },
            auth_header="Token",
        )

    async def get_document(self, *, year: int, month: int, document_type: int) -> Any:
        return await self._post(
            self.GET_DOCUMENT_PATH,
            {"Year": year, "Month": month, "DocumentType": document_type},
            auth_header="Token",
        )
