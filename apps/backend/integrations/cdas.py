from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any, Literal

import httpx

from database.config.config import settings


class CdasRequestType(IntEnum):
    """Request Type codes exactly as documented by CDAS v1.5."""

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
    """Deduction status codes exactly as documented by CDAS v1.5."""

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


@dataclass(slots=True)
class CdasError(Exception):
    status_code: int
    message: str
    details: Any = None

    def __str__(self) -> str:
        return self.message


class CdasConfigurationError(CdasError):
    pass


@dataclass(slots=True)
class _TokenState:
    value: str
    obtained_at: datetime
    last_used_at: datetime


class CdasClient:
    """Server-side client for one company's official CDAS Third Party API account.

    Credentials are passed explicitly from the company configuration service.
    The client deliberately has no server-wide username/password fallback, which
    prevents one tenant from accidentally using another company's CDAS account.

    The CDAS specification uses two different token headers: employee details
    uses ``Authorization`` while the other documented operations use ``Token``.
    This client intentionally preserves that endpoint-specific contract.
    """

    LOGIN_PATH = "/api/security/login"
    EMPLOYEE_DETAILS_PATH = "/api/employee/getDetails"
    AFFORDABILITY_PATH = "/api/employee/check-affordability"
    ALL_DEDUCTIONS_PATH = "/api/policy/view-all-deduction"
    OWN_DEDUCTIONS_PATH = "/api/policy/view-deduction"
    ADD_UPDATE_DEDUCTION_PATH = "/api/policy/add-update-deduction"
    ACTIVE_APPROVED_DEDUCTION_PATH = "/api/policy/get-active-and-approved-deduction"
    MODIFY_ACTIVE_DEDUCTION_PATH = "/api/policy/modify-active-deduction"
    SETTLE_DEDUCTION_PATH = "/api/policy/settled-deduction"
    DOCUMENT_PATH = "/api/policy/get_document"

    # CDAS documents a maximum token lifetime of 8 hours and inactivity expiry
    # after 10 minutes. Refresh slightly early so user requests do not race the
    # server-side expiry boundary.
    _TOKEN_MAX_AGE = timedelta(hours=7, minutes=50)
    _TOKEN_IDLE_AGE = timedelta(minutes=9)
    _AUTH_RETRY_STATUSES = {401, 402}

    def __init__(
        self,
        *,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.username = username
        self.password = password
        self.timeout_seconds = timeout_seconds or settings.CDAS_TIMEOUT_SECONDS
        self.transport = transport
        self._token: _TokenState | None = None
        self._token_lock = asyncio.Lock()

    def _require_configuration(self) -> None:
        if not self.base_url or not self.username or not self.password:
            raise CdasConfigurationError(
                status_code=503,
                message="CDAS integration credentials are incomplete",
            )

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _token_is_fresh(self) -> bool:
        token = self._token
        if token is None:
            return False
        now = self._now()
        return (
            now - token.obtained_at < self._TOKEN_MAX_AGE
            and now - token.last_used_at < self._TOKEN_IDLE_AGE
        )

    async def _login(self, *, force: bool = False) -> str:
        self._require_configuration()
        async with self._token_lock:
            if not force and self._token_is_fresh():
                assert self._token is not None
                return self._token.value

            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                try:
                    response = await client.post(
                        self.LOGIN_PATH,
                        json={"Username": self.username, "Password": self.password},
                    )
                except httpx.RequestError as exc:
                    raise CdasError(
                        status_code=503,
                        message="CDAS authentication service is unavailable",
                    ) from exc

            payload = self._decode_response(response)
            if response.status_code >= 400:
                raise self._error_from_response(response, payload)
            if not isinstance(payload, dict) or not payload.get("Authorization"):
                raise CdasError(
                    status_code=502,
                    message="CDAS authentication returned an invalid response",
                )

            now = self._now()
            self._token = _TokenState(
                value=str(payload["Authorization"]),
                obtained_at=now,
                last_used_at=now,
            )
            return self._token.value

    async def check_connection(self) -> None:
        """Authenticate without exposing the returned CDAS token to callers."""
        await self._login(force=True)

    @staticmethod
    def _decode_response(response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            text = response.text.strip()
            try:
                return float(text)
            except ValueError:
                return text

    @staticmethod
    def _extract_message(payload: Any, fallback: str) -> str:
        if isinstance(payload, dict):
            for key in ("message", "Message", "detail", "Detail", "error", "Error"):
                value = payload.get(key)
                if value:
                    return str(value)
        if isinstance(payload, str) and payload:
            return payload
        return fallback

    def _error_from_response(self, response: httpx.Response, payload: Any) -> CdasError:
        status = response.status_code
        documented_messages = {
            429: "CDAS request limit has been reached",
            499: "Deduction amount exceeds maximum available fund",
            498: "CDAS rejected the item code for this company",
            497: "CDAS rejected the effective month",
            496: "A loan deduction requires a non-zero installment count",
            495: "An active or approved deduction cannot be modified by this operation",
        }
        message = self._extract_message(
            payload,
            documented_messages.get(status, f"CDAS request failed with status {status}"),
        )
        return CdasError(status_code=status, message=message, details=payload)

    async def _post(
        self,
        path: str,
        *,
        body: dict[str, Any],
        token_header: Literal["Authorization", "Token"] = "Token",
        retry_auth: bool = True,
    ) -> Any:
        token = await self._login()
        headers = {token_header: token}
        async with httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            try:
                response = await client.post(path, headers=headers, json=body)
            except httpx.RequestError as exc:
                raise CdasError(
                    status_code=503,
                    message="CDAS service is unavailable",
                ) from exc

        payload = self._decode_response(response)
        if response.status_code in self._AUTH_RETRY_STATUSES and retry_auth:
            token = await self._login(force=True)
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                try:
                    response = await client.post(
                        path,
                        headers={token_header: token},
                        json=body,
                    )
                except httpx.RequestError as exc:
                    raise CdasError(
                        status_code=503,
                        message="CDAS service is unavailable",
                    ) from exc
            payload = self._decode_response(response)

        if response.status_code >= 400:
            raise self._error_from_response(response, payload)

        if self._token is not None:
            self._token.last_used_at = self._now()
        return payload

    async def employee_details(self, employee_no: str) -> dict[str, Any]:
        payload = await self._post(
            self.EMPLOYEE_DETAILS_PATH,
            body={"EmployeeNo": employee_no},
            token_header="Authorization",
        )
        if not isinstance(payload, dict):
            raise CdasError(502, "CDAS employee details returned an invalid response", payload)
        return payload

    async def affordability(self, employee_no: str) -> float:
        payload = await self._post(
            self.AFFORDABILITY_PATH,
            body={"EmployeeNo": employee_no},
        )
        if isinstance(payload, bool):
            raise CdasError(502, "CDAS affordability returned an invalid response", payload)
        if isinstance(payload, (int, float)):
            return float(payload)
        if isinstance(payload, str):
            try:
                return float(payload)
            except ValueError:
                pass
        raise CdasError(502, "CDAS affordability returned an invalid response", payload)

    async def all_deductions(self, employee_no: str) -> list[dict[str, Any]]:
        payload = await self._post(
            self.ALL_DEDUCTIONS_PATH,
            body={"EmployeeNo": employee_no},
        )
        if not isinstance(payload, list):
            raise CdasError(502, "CDAS deductions returned an invalid response", payload)
        return payload

    async def own_deductions(
        self,
        employee_no: str,
        deduction_status: int,
    ) -> list[dict[str, Any]]:
        payload = await self._post(
            self.OWN_DEDUCTIONS_PATH,
            body={"EmployeeNo": employee_no, "DeductionStatus": deduction_status},
        )
        if not isinstance(payload, list):
            raise CdasError(502, "CDAS deductions returned an invalid response", payload)
        return payload

    async def add_update_deduction(self, payload: dict[str, Any]) -> dict[str, Any]:
        # State-changing CDAS calls are never replayed automatically. A 401/402
        # after submission is surfaced so LoanHub can reconcile status before a
        # user explicitly retries, avoiding duplicate or unintended deductions.
        value = await self._post(
            self.ADD_UPDATE_DEDUCTION_PATH,
            body=payload,
            retry_auth=False,
        )
        if not isinstance(value, dict):
            raise CdasError(502, "CDAS deduction operation returned an invalid response", value)
        return value

    async def active_and_approved_deductions(self, employee_no: str) -> Any:
        return await self._post(
            self.ACTIVE_APPROVED_DEDUCTION_PATH,
            body={"EmployeeNo": employee_no},
        )

    async def modify_active_deduction(self, payload: dict[str, Any]) -> Any:
        return await self._post(
            self.MODIFY_ACTIVE_DEDUCTION_PATH,
            body=payload,
            retry_auth=False,
        )

    async def settle_deduction(self, payload: dict[str, Any]) -> Any:
        return await self._post(
            self.SETTLE_DEDUCTION_PATH,
            body=payload,
            retry_auth=False,
        )

    async def get_document(self, *, year: int, month: int, document_type: int) -> Any:
        return await self._post(
            self.DOCUMENT_PATH,
            body={"Year": year, "Month": month, "DocumentType": document_type},
        )

    async def refresh_employee_snapshot(
        self,
        employee_no: str,
        *,
        own_deduction_status: int | None = None,
    ) -> dict[str, Any]:
        """Run one deliberate, user-triggered read snapshot.

        Calls are sequential on purpose: the CDAS service documents a finite daily
        request allowance, so this method never fans out speculative/background
        requests. Own deductions are only queried when a status is explicitly
        supplied.
        """

        employee = await self.employee_details(employee_no)
        affordability = await self.affordability(employee_no)
        deductions = await self.all_deductions(employee_no)
        own: list[dict[str, Any]] | None = None
        if own_deduction_status is not None:
            own = await self.own_deductions(employee_no, own_deduction_status)
        return {
            "source": "CDAS_API",
            "checked_at": self._now().isoformat(),
            "employee": employee,
            "affordability": affordability,
            "deductions": deductions,
            "own_deductions": own,
        }
