from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from database.models.enums import UserRole
from database.schemas.auth import WebSocketSessionRequest
from routers import auth
from routers.ws import _origin_allowed, _websocket_token


class _WebSocketStub:
    def __init__(
        self,
        *,
        protocols: list[str] | None = None,
        cookie_token: str | None = None,
        query_token: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.scope = {"subprotocols": protocols or []}
        self.headers = headers or {}
        self.cookies = (
            {"loanhub_ws_session": cookie_token}
            if cookie_token
            else {}
        )
        self.query_params = (
            {"token": query_token}
            if query_token
            else {}
        )


def test_websocket_subprotocol_token_wins_over_stale_cookie() -> None:
    websocket = _WebSocketStub(
        protocols=["loanhub.v1", "loanhub.jwt.fresh-token"],
        cookie_token="stale-cookie-token",
        query_token="legacy-query-token",
    )

    token, accepted_protocol, transport = _websocket_token(websocket)

    assert token == "fresh-token"
    assert accepted_protocol == "loanhub.v1"
    assert transport == "subprotocol"



def test_same_origin_websocket_is_allowed_without_cors_duplication() -> None:
    websocket = _WebSocketStub(
        headers={
            "origin": "https://loanhub.example",
            "host": "loanhub.example",
        },
    )

    assert _origin_allowed(websocket) is True

def test_websocket_session_returns_client_bound_short_lived_token(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_create_token(payload, expires_delta):
        captured["payload"] = payload
        captured["expires_delta"] = expires_delta
        return "signed-websocket-token"

    monkeypatch.setattr(auth, "create_token", fake_create_token)

    user = SimpleNamespace(id=uuid4(), role=UserRole.SUPERADMIN)
    response = auth.create_websocket_session(
        WebSocketSessionRequest(
            company_id=None,
            client_id="browser-client-123",
        ),
        current_user=user,
        db=SimpleNamespace(),
    )

    body = json.loads(response.body)
    assert body == {
        "websocket_token": "signed-websocket-token",
        "expires_in": auth.WS_SESSION_TTL_SECONDS,
    }
    assert captured["payload"]["token_type"] == "websocket"
    assert captured["payload"]["client_id"] == "browser-client-123"
    assert captured["payload"]["jti"]
    assert response.headers["cache-control"] == "no-store, private"
    assert "loanhub_ws_session=" in response.headers["set-cookie"]
    assert "Path=/api/v1/ws" in response.headers["set-cookie"]


def test_frontend_uses_short_lived_subprotocol_not_query_token() -> None:
    frontend = Path(__file__).resolve().parents[2] / "frontend"
    provider = (
        frontend / "provider" / "realtimeProvider.tsx"
    ).read_text(encoding="utf-8")
    auth_api = (frontend / "api" / "auth.ts").read_text(encoding="utf-8")

    assert "websocket_token?: string" in auth_api
    assert "client_id: clientId" in auth_api
    assert "loanhub.jwt.${websocketToken}" in provider
    assert "session.websocket_token" in provider
    assert 'url.searchParams.set("token"' not in provider
