from __future__ import annotations

import asyncio
from collections.abc import Callable
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


@dataclass(frozen=True, slots=True)
class _AuthMode:
    header: Literal["Authorization", "Token"]
    bearer: bool = False


class CdasClient:
    """Server-side client for one company's official CDAS Third Party API account."""

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

    # These statuses mean a read may need a fresh login. 406 is documented as an
    # invalid token format, but older CDAS behavior also used it for unusable
    # sessions, so reads refresh once before negotiating alternate safe formats.
    _AUTH_REFRESH_STATUSES = {401, 402, 406, 419}
    _AUTH_FORMAT_STATUSES = {406, 417}
    _AUTH_FAILURE_STATUSES = {401, 402, 406, 417, 419}

    def __init__(
        self,
        *,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout_seconds: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
        request_guard: Callable[[], None] | None = None,
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.username = username
        self.password = password
        self.timeout_seconds = timeout_seconds or settings.CDAS_TIMEOUT_SECONDS
        self.transport = transport
        self.request_guard = request_guard
        self._token: _TokenState | None = None
        self._token_lock = asyncio.Lock()
        # CDAS v1.5 documents token headers but does not document cookies. Keep
        # the authenticated HTTP session cookies anyway because the Test gateway
        # may bind the returned token to the login session.
        self._session_cookies = httpx.Cookies()
        # Cache the first read-auth mode accepted by each documented header
        # family so a snapshot does not repeatedly spend provider requests on
        # compatibility negotiation.
        self._read_auth_modes: dict[str, _AuthMode] = {}

    def _require_configuration(self) -> None:
        if not self.base_url or not self.username or not self.password:
            raise CdasConfigurationError(
                status_code=503,
                message="CDAS integration credentials are incomplete",
            )

    def _reserve_request(self) -> None:
        if self.request_guard is not None:
            self.request_guard()

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

            # Login always starts with a clean cookie jar. If CDAS establishes a
            # gateway/session cookie, preserve the complete resulting jar and use
            # it for every request made with the returned token.
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
                cookies=httpx.Cookies(),
            ) as client:
                try:
                    self._reserve_request()
                    response = await client.post(
                        self.LOGIN_PATH,
                        json={"Username": self.username, "Password": self.password},
                    )
                    login_cookies = httpx.Cookies()
                    login_cookies.update(client.cookies)
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

            token_value = str(payload["Authorization"]).strip()
            if not token_value:
                raise CdasError(
                    status_code=502,
                    message="CDAS authentication returned an empty authorization token",
                )

            now = self._now()
            self._session_cookies = login_cookies
            self._token = _TokenState(
                value=token_value,
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
            406: "CDAS rejected the authorization token format",
            417: "CDAS reported a missing authorization token",
            419: "The CDAS session is inactive or expired",
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

    @staticmethod
    def _opposite_header(
        header: Literal["Authorization", "Token"],
    ) -> Literal["Authorization", "Token"]:
        return "Token" if header == "Authorization" else "Authorization"

    @staticmethod
    def _format_token(token: str, *, bearer: bool) -> str:
        value = token.strip()
        if bearer and not value.lower().startswith("bearer "):
            return f"Bearer {value}"
        return value

    def _auth_candidates(
        self,
        documented_header: Literal["Authorization", "Token"],
        token: str,
        *,
        negotiate: bool,
    ) -> list[_AuthMode]:
        if not negotiate:
            return [_AuthMode(documented_header, False)]

        opposite = self._opposite_header(documented_header)
        default_modes = [
            _AuthMode(documented_header, False),
            _AuthMode(opposite, False),
            _AuthMode(documented_header, True),
            _AuthMode(opposite, True),
        ]
        cached = self._read_auth_modes.get(documented_header)
        if cached is not None:
            default_modes.insert(0, cached)

        # If login already returned a value beginning with "Bearer ", the raw
        # and bearer renderings are identical. Do not spend duplicate requests.
        seen: set[tuple[str, str]] = set()
        result: list[_AuthMode] = []
        for mode in default_modes:
            rendered = self._format_token(token, bearer=mode.bearer)
            identity = (mode.header, rendered)
            if identity in seen:
                continue
            seen.add(identity)
            result.append(mode)
        return result

    def _mark_token_used(self) -> None:
        if self._token is not None:
            self._token.last_used_at = self._now()

    async def _post(
        self,
        path: str,
        *,
        body: dict[str, Any],
        token_header: Literal["Authorization", "Token"] = "Token",
        retry_auth: bool = True,
        negotiate_read_auth: bool = True,
    ) -> Any:
        token = await self._login()
        refreshed = False

        async def send(current_token: str, mode: _AuthMode) -> httpx.Response:
            header_value = self._format_token(current_token, bearer=mode.bearer)
            async with httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout_seconds,
                transport=self.transport,
                cookies=self._session_cookies,
            ) as client:
                try:
                    self._reserve_request()
                    response = await client.post(
                        path,
                        headers={mode.header: header_value},
                        json=body,
                    )
                    # Preserve any gateway/session rotation returned by CDAS.
                    self._session_cookies.update(client.cookies)
                    return response
                except httpx.RequestError as exc:
                    raise CdasError(
                        status_code=503,
                        message="CDAS service is unavailable",
                    ) from exc

        last_format_failure: tuple[httpx.Response, Any] | None = None

        while True:
            restart_after_login = False
            candidates = self._auth_candidates(
                token_header,
                token,
                negotiate=negotiate_read_auth,
            )

            for mode in candidates:
                response = await send(token, mode)
                payload = self._decode_response(response)
                status = response.status_code

                # Reads may safely obtain one fresh login and retry. Writes pass
                # retry_auth=False, so once a provider write is submitted it is
                # never replayed automatically under any authentication failure.
                if status in self._AUTH_REFRESH_STATUSES and retry_auth and not refreshed:
                    token = await self._login(force=True)
                    refreshed = True
                    restart_after_login = True
                    break

                if negotiate_read_auth and status in self._AUTH_FORMAT_STATUSES:
                    last_format_failure = (response, payload)
                    continue

                # Any non-authentication response proves this header mode reached
                # the endpoint. Cache it even when the business result is 404,
                # 429, 49x, or 500 so future reads do not renegotiate needlessly.
                if negotiate_read_auth and status not in self._AUTH_FAILURE_STATUSES:
                    self._read_auth_modes[token_header] = mode
                    self._mark_token_used()

                if status >= 400:
                    raise self._error_from_response(response, payload)

                if negotiate_read_auth:
                    self._read_auth_modes[token_header] = mode
                self._mark_token_used()
                return payload

            if restart_after_login:
                last_format_failure = None
                continue

            # If every format was rejected as 406/417, do one fresh login before
            # declaring failure. This also establishes a fresh Test-gateway cookie
            # if the gateway binds auth to the login HTTP session.
            if negotiate_read_auth and last_format_failure is not None and retry_auth and not refreshed:
                token = await self._login(force=True)
                refreshed = True
                last_format_failure = None
                continue

            if last_format_failure is not None:
                response, _payload = last_format_failure
                raise CdasError(
                    status_code=response.status_code,
                    message=(
                        "CDAS rejected all supported read authorization formats after a fresh login. "
                        "The CDAS API account or Test gateway must be checked by the provider."
                    ),
                    details={"provider_status": response.status_code},
                )

            raise CdasError(
                status_code=502,
                message="CDAS request ended without a usable response",
            )

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
        # State-changing CDAS calls are never replayed or auth-negotiated
        # automatically. A failure after submission is surfaced for reconciliation
        # before any user explicitly retries, avoiding duplicate deductions.
        value = await self._post(
            self.ADD_UPDATE_DEDUCTION_PATH,
            body=payload,
            retry_auth=False,
            negotiate_read_auth=False,
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
            negotiate_read_auth=False,
        )

    async def settle_deduction(self, payload: dict[str, Any]) -> Any:
        return await self._post(
            self.SETTLE_DEDUCTION_PATH,
            body=payload,
            retry_auth=False,
            negotiate_read_auth=False,
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
        """Run one deliberate, user-triggered read snapshot."""
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
