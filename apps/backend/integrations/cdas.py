from __future__ import annotations

import asyncio
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
    """Small CDAS client for phases 1-2 of the clean reintegration."""

    LOGIN_PATH = "/api/security/login"
    EMPLOYEE_DETAILS_PATH = "/api/employee/getDetails"
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
    ) -> None:
        self.base_url = (base_url or "").rstrip("/")
        self.username = username
        self.password = password
        self.timeout_seconds = timeout_seconds or settings.CDAS_TIMEOUT_SECONDS
        self.transport = transport
        self._token: _TokenState | None = None
        self._token_lock = asyncio.Lock()
        self._session_cookies = httpx.Cookies()

    def _require_configuration(self) -> None:
        if not self.base_url or not self.username or not self.password:
            raise CdasConfigurationError(503, "CDAS authentication credentials are incomplete")

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
            return response.text.strip()

    @staticmethod
    def _message(payload: Any, fallback: str) -> str:
        if isinstance(payload, dict):
            for key in ("message", "Message", "detail", "Detail", "error", "Error"):
                if payload.get(key):
                    return str(payload[key])
        if isinstance(payload, list) and payload:
            return "; ".join(str(item) for item in payload)
        return payload if isinstance(payload, str) and payload else fallback

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
                response = await client.post(
                    path,
                    json=payload,
                    headers={"Authorization": token},
                )
                self._session_cookies.update(client.cookies)
            except httpx.RequestError as exc:
                raise CdasError(503, "CDAS service is unavailable") from exc

        if response.status_code in self._SESSION_EXPIRED_STATUS_CODES and retry_expired_session:
            await self.authenticate(force=True)
            return await self._post_authenticated(
                path,
                payload=payload,
                retry_expired_session=False,
            )

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
        return response_payload

    async def get_employee_details(self, employee_no: str) -> dict[str, str | None]:
        employee_no = employee_no.strip()
        if not employee_no:
            raise CdasError(422, "Employee number is required")

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

    async def check_connection(self) -> None:
        await self.authenticate(force=True)
