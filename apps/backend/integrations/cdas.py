from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from database.config.config import settings


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
    """Small, request-driven CDAS client for the clean reintegration."""

    LOGIN_PATH = "/api/security/login"
    EMPLOYEE_DETAILS_PATH = "/api/employee/getDetails"
    AFFORDABILITY_PATH = "/api/employee/check-affordability"
    ALL_DEDUCTIONS_PATH = "/api/policy/view-all-deduction"
    OWN_DEDUCTIONS_PATH = "/api/policy/view-deduction"
    ADD_UPDATE_DEDUCTION_PATH = "/api/policy/add-update-deduction"
    ACTIVE_APPROVED_DEDUCTION_PATH = "/api/policy/get-active-and-approved-deduction"
    MODIFY_ACTIVE_DEDUCTION_PATH = "/api/policy/modify-active-deduction"
    SETTLED_DEDUCTION_PATH = "/api/policy/settled-deduction"
    DOCUMENT_PATH = "/api/policy/get_document"

    _TOKEN_MAX_AGE = timedelta(hours=7, minutes=50)
    _TOKEN_IDLE_AGE = timedelta(minutes=9)
    _SESSION_EXPIRED_STATUS_CODES = {401, 402, 419}

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
        self._session_cookies = httpx.Cookies()

    def _require_configuration(self) -> None:
        if not self.base_url or not self.username or not self.password:
            raise CdasConfigurationError(503, "CDAS authentication credentials are incomplete")

    def _reserve_request(self) -> None:
        if self.request_guard is not None:
            self.request_guard()

    def _invalidate_session(self) -> None:
        self._token = None
        self._session_cookies = httpx.Cookies()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _token_is_fresh(self) -> bool:
        if self._token is None:
            return False
        now = self._now()
        return (
            now - self._token.obtained_at < self._TOKEN_MAX_AGE
            and now - self._token.last_used_at < self._TOKEN_IDLE_AGE
        )

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
    def _message(payload: Any, fallback: str) -> str:
        if isinstance(payload, dict):
            for key in ("message", "Message", "detail", "Detail", "error", "Error"):
                if payload.get(key):
                    return str(payload[key])
        if isinstance(payload, list) and payload:
            return "; ".join(str(item) for item in payload)
        return payload if isinstance(payload, str) and payload else fallback

    @staticmethod
    def _require_employee_number(employee_no: str) -> str:
        normalized = employee_no.strip()
        if not normalized:
            raise CdasError(422, "Employee number is required")
        return normalized

    async def authenticate(self, *, force: bool = False) -> str:
        self._require_configuration()
        async with self._token_lock:
            if not force and self._token_is_fresh():
                assert self._token is not None
                self._token.last_used_at = self._now()
                return self._token.value

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
                    cookies = httpx.Cookies()
                    cookies.update(client.cookies)
                except httpx.RequestError as exc:
                    raise CdasError(503, "CDAS authentication service is unavailable") from exc

            payload = self._decode_response(response)
            if response.status_code >= 400:
                raise CdasError(
                    response.status_code,
                    self._message(
                        payload,
                        f"CDAS authentication failed with status {response.status_code}",
                    ),
                    payload,
                )
            if not isinstance(payload, dict) or not payload.get("Authorization"):
                raise CdasError(502, "CDAS authentication returned an invalid response")

            token = str(payload["Authorization"]).strip()
            if not token:
                raise CdasError(502, "CDAS authentication returned an empty authorization token")

            now = self._now()
            self._session_cookies = cookies
            self._token = _TokenState(token, now, now)
            return token

    async def _post_authenticated(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        header_name: str = "Authorization",
        retry_expired_session: bool = True,
    ) -> Any:
        token = await self.authenticate()

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
                    json=payload,
                    headers={header_name: token},
                )
                self._session_cookies.update(client.cookies)
            except httpx.RequestError as exc:
                raise CdasError(503, "CDAS service is unavailable") from exc

        if response.status_code in self._SESSION_EXPIRED_STATUS_CODES:
            if retry_expired_session:
                await self.authenticate(force=True)
                return await self._post_authenticated(
                    path,
                    payload=payload,
                    header_name=header_name,
                    retry_expired_session=False,
                )
            # A mutation must never be replayed automatically. Clear local session
            # state so the next explicit user action starts with a fresh login.
            self._invalidate_session()

        response_payload = self._decode_response(response)
        if response.status_code >= 400:
            raise CdasError(
                response.status_code,
                self._message(
                    response_payload,
                    f"CDAS request failed with status {response.status_code}",
                ),
                response_payload,
            )
        if self._token is not None:
            self._token.last_used_at = self._now()
        return response_payload

    async def get_employee_details(self, employee_no: str) -> dict[str, str | None]:
        employee_no = self._require_employee_number(employee_no)
        payload = await self._post_authenticated(
            self.EMPLOYEE_DETAILS_PATH,
            payload={"EmployeeNo": employee_no},
        )
        if not isinstance(payload, dict) or not payload.get("EmployeeNo"):
            raise CdasError(502, "CDAS employee lookup returned an invalid response", payload)

        fields = (
            "EmployeeNo",
            "Name",
            "Surname",
            "DOB",
            "Department",
            "JoiningDate",
            "TerminationDate",
        )
        return {
            field: str(payload[field]) if payload.get(field) is not None else None
            for field in fields
        }

    async def check_affordability(self, employee_no: str) -> float:
        employee_no = self._require_employee_number(employee_no)
        payload = await self._post_authenticated(
            self.AFFORDABILITY_PATH,
            payload={"EmployeeNo": employee_no},
            header_name="Token",
        )
        if isinstance(payload, bool) or not isinstance(payload, (int, float)):
            raise CdasError(502, "CDAS affordability check returned an invalid response", payload)
        return float(payload)

    async def view_all_deductions(self, employee_no: str) -> list[dict[str, Any]]:
        employee_no = self._require_employee_number(employee_no)
        payload = await self._post_authenticated(
            self.ALL_DEDUCTIONS_PATH,
            payload={"EmployeeNo": employee_no},
            header_name="Token",
        )
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise CdasError(502, "CDAS all-deductions lookup returned an invalid response", payload)
        return payload

    async def view_own_deductions(
        self,
        employee_no: str,
        deduction_status: int,
    ) -> list[dict[str, Any]]:
        employee_no = self._require_employee_number(employee_no)
        if deduction_status < 1 or deduction_status > 10:
            raise CdasError(422, "Deduction status must be between 1 and 10")
        payload = await self._post_authenticated(
            self.OWN_DEDUCTIONS_PATH,
            payload={
                "EmployeeNo": employee_no,
                "DeductionStatus": deduction_status,
            },
            header_name="Token",
        )
        if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
            raise CdasError(502, "CDAS own-deductions lookup returned an invalid response", payload)
        return payload

    async def add_update_deduction(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        payload = await self._post_authenticated(
            self.ADD_UPDATE_DEDUCTION_PATH,
            payload=request_payload,
            header_name="Token",
            retry_expired_session=False,
        )
        if not isinstance(payload, dict):
            raise CdasError(502, "CDAS deduction lifecycle request returned an invalid response", payload)
        return payload

    async def get_active_and_approved_deduction(self, employee_no: str) -> dict[str, Any]:
        employee_no = self._require_employee_number(employee_no)
        payload = await self._post_authenticated(
            self.ACTIVE_APPROVED_DEDUCTION_PATH,
            payload={"EmployeeNo": employee_no},
            header_name="Token",
        )
        if not isinstance(payload, dict):
            raise CdasError(
                502,
                "CDAS active/approved deduction lookup returned an invalid response",
                payload,
            )
        return payload

    async def modify_active_deduction(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        payload = await self._post_authenticated(
            self.MODIFY_ACTIVE_DEDUCTION_PATH,
            payload=request_payload,
            header_name="Token",
            retry_expired_session=False,
        )
        if not isinstance(payload, dict):
            raise CdasError(502, "CDAS active deduction modification returned an invalid response", payload)
        return payload

    async def settle_deduction(self, request_payload: dict[str, Any]) -> dict[str, Any]:
        payload = await self._post_authenticated(
            self.SETTLED_DEDUCTION_PATH,
            payload=request_payload,
            header_name="Token",
            retry_expired_session=False,
        )
        if not isinstance(payload, dict):
            raise CdasError(502, "CDAS deduction settlement returned an invalid response", payload)
        return payload

    async def get_document(self, *, year: int, month: int, document_type: int) -> dict[str, Any]:
        payload = await self._post_authenticated(
            self.DOCUMENT_PATH,
            payload={
                "Year": year,
                "Month": month,
                "DocumentType": document_type,
            },
            header_name="Token",
        )
        if not isinstance(payload, dict):
            raise CdasError(502, "CDAS document request returned an invalid response", payload)
        return payload

    async def check_connection(self) -> None:
        await self.authenticate(force=True)
