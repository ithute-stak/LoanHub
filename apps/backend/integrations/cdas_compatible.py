from __future__ import annotations

from typing import Any

import httpx

from integrations.cdas import CdasClient, CdasError


class CdasCompatibleClient(CdasClient):
    """CDAS client with provider-compatible authentication negotiation for reads.

    The CDAS Test service has historically accepted different token transports
    across read-only endpoints (Authorization vs Token, raw vs Bearer). Reads
    may safely negotiate those transports. State-changing deduction calls keep
    the base client's single-shot, non-replayed behaviour.
    """

    _FORMAT_FAILURE_STATUSES = {406, 417}
    _FORMAT_FAILURE_MARKERS = (
        "authorization token is missing",
        "authorization token missing",
        "token is missing",
        "token missing",
        "authorization token format",
        "invalid authorization format",
        "invalid token format",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._read_auth_modes: dict[str, tuple[str, bool]] = {}

    @classmethod
    def _is_auth_format_failure(cls, status_code: int, payload: Any) -> bool:
        if status_code in cls._FORMAT_FAILURE_STATUSES:
            return True
        if status_code < 400:
            return False
        message = cls._message(payload, "").strip().casefold()
        return any(marker in message for marker in cls._FORMAT_FAILURE_MARKERS)

    @staticmethod
    def _alternate_header(header_name: str) -> str:
        return "Token" if header_name.casefold() == "authorization" else "Authorization"

    def _read_candidates(self, path: str, header_name: str) -> list[tuple[str, bool]]:
        primary = (header_name, False)
        alternate = (self._alternate_header(header_name), False)
        candidates = [primary, alternate, (header_name, True), (alternate[0], True)]
        cached = self._read_auth_modes.get(path)
        if cached is not None:
            candidates.insert(0, cached)

        unique: list[tuple[str, bool]] = []
        for candidate in candidates:
            if candidate not in unique:
                unique.append(candidate)
        return unique

    @staticmethod
    def _header_value(token: str, bearer: bool) -> str:
        if not bearer:
            return token
        if token.casefold().startswith("bearer "):
            return token
        return f"Bearer {token}"

    async def _send_read(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        token: str,
        mode: tuple[str, bool],
    ) -> tuple[httpx.Response, Any]:
        header_name, bearer = mode
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
                    json=self._json_payload(payload),
                    headers={header_name: self._header_value(token, bearer)},
                )
                self._session_cookies.update(client.cookies)
            except httpx.RequestError as exc:
                raise CdasError(503, "CDAS service is unavailable") from exc
        return response, self._decode_response(response)

    async def _attempt_read_modes(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        header_name: str,
        token: str,
    ) -> tuple[bool, Any, httpx.Response, Any]:
        last_response: httpx.Response | None = None
        last_payload: Any = None

        for mode in self._read_candidates(path, header_name):
            response, response_payload = await self._send_read(
                path,
                payload=payload,
                token=token,
                mode=mode,
            )
            last_response = response
            last_payload = response_payload

            if response.status_code < 400:
                self._read_auth_modes[path] = mode
                return True, response_payload, response, response_payload

            if self._is_auth_format_failure(response.status_code, response_payload):
                continue

            # A genuine expired/inactive session needs a fresh login rather than
            # more header probing with the same token.
            if self._is_session_auth_failure(response.status_code, response_payload):
                break

            raise CdasError(
                response.status_code,
                self._message(
                    response_payload,
                    f"CDAS request failed with status {response.status_code}",
                ),
                response_payload,
            )

        assert last_response is not None
        return False, None, last_response, last_payload

    async def _post_authenticated(
        self,
        path: str,
        *,
        payload: dict[str, Any],
        header_name: str = "Authorization",
        retry_expired_session: bool = True,
    ) -> Any:
        # Mutations remain strictly single-shot. Never negotiate or replay a
        # deduction write because the provider may have applied it already.
        if not retry_expired_session:
            return await super()._post_authenticated(
                path,
                payload=payload,
                header_name=header_name,
                retry_expired_session=False,
            )

        token = await self.authenticate()
        success, value, response, response_payload = await self._attempt_read_modes(
            path,
            payload=payload,
            header_name=header_name,
            token=token,
        )
        if success:
            if self._token is not None:
                self._token.last_used_at = self._now()
                await self._save_shared_session(strict=False)
            return value

        # One fresh login is allowed for a read. Retry the safe transport modes
        # once with the new token, then surface the provider response.
        self._read_auth_modes.pop(path, None)
        token = await self.authenticate(force=True)
        success, value, response, response_payload = await self._attempt_read_modes(
            path,
            payload=payload,
            header_name=header_name,
            token=token,
        )
        if success:
            if self._token is not None:
                self._token.last_used_at = self._now()
                await self._save_shared_session(strict=False)
            return value

        await self._invalidate_session(clear_shared=True)
        raise CdasError(
            response.status_code,
            self._message(
                response_payload,
                f"CDAS request failed with status {response.status_code}",
            ),
            response_payload,
        )
