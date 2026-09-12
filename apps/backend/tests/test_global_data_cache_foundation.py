from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("FERNET_SECRET_KEY", "test-fernet-key")

from starlette.requests import Request

from core.response_cache import (
    _request_is_cacheable,
    response_cache,
    response_cache_policy,
)
from utils.convex import current_user_id


BACKEND_ROOT = Path(__file__).resolve().parents[1]
FRONTEND_ROOT = BACKEND_ROOT.parent / "frontend"


def _request(
    path: str,
    *,
    method: str = "GET",
    query: bytes = b"",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "https",
            "path": path,
            "raw_path": path.encode(),
            "query_string": query,
            "headers": headers or [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 443),
        }
    )


def test_server_cache_uses_short_ttl_for_live_financial_data() -> None:
    assert response_cache_policy("/api/v1/loans").ttl_seconds == 10
    assert response_cache_policy("/api/v1/payments").ttl_seconds == 10
    assert response_cache_policy("/api/v1/collections/workspace").ttl_seconds == 10


def test_server_cache_uses_longer_ttl_for_reference_data() -> None:
    assert response_cache_policy("/api/v1/hr/departments").ttl_seconds == 300
    assert response_cache_policy("/api/v1/hr/positions").ttl_seconds == 300
    assert response_cache_policy("/api/v1/billing/plans").ttl_seconds == 300


def test_server_cache_is_user_and_generation_scoped() -> None:
    request = _request(
        "/api/v1/company/clients",
        query=b"page=1&status=active",
    )
    first = response_cache.response_key(
        request=request,
        identity="user-a:company-a:company_admin",
        generation=3,
    )
    repeated = response_cache.response_key(
        request=request,
        identity="user-a:company-a:company_admin",
        generation=3,
    )
    next_generation = response_cache.response_key(
        request=request,
        identity="user-a:company-a:company_admin",
        generation=4,
    )
    other_user = response_cache.response_key(
        request=request,
        identity="user-b:company-a:company_admin",
        generation=3,
    )

    assert first == repeated
    assert first != next_generation
    assert first != other_user


def test_server_cache_rejects_sensitive_and_mutating_requests() -> None:
    token = current_user_id.set("user-a")
    try:
        assert _request_is_cacheable(_request("/api/v1/company/clients"))
        assert not _request_is_cacheable(_request("/api/v1/auth/me"))
        assert not _request_is_cacheable(_request("/api/v1/chat/conversations"))
        assert not _request_is_cacheable(_request("/api/v1/hr/payroll/runs"))
        assert not _request_is_cacheable(
            _request("/api/v1/company/clients", method="POST")
        )
        assert not _request_is_cacheable(
            _request(
                "/api/v1/company/clients",
                headers=[(b"x-loanhub-cache", b"bypass")],
            )
        )
    finally:
        current_user_id.reset(token)


def test_frontend_installs_one_project_wide_redux_http_cache() -> None:
    providers = (FRONTEND_ROOT / "provider" / "providers.tsx").read_text()
    store = (FRONTEND_ROOT / "store" / "index.ts").read_text()
    cache = (FRONTEND_ROOT / "lib" / "http-cache.ts").read_text()
    cache_slice = (
        FRONTEND_ROOT
        / "store"
        / "features"
        / "slices"
        / "httpCacheSlice.ts"
    ).read_text()

    assert "installReduxHttpCache(api, store)" in providers
    assert "httpCache: httpCacheReducer" in store
    assert "client.defaults.adapter" in cache
    assert "inflightRequests" in cache
    assert "X-Company-ID" in cache
    assert "X-Active-Role" in cache
    assert "MAX_CACHE_ENTRIES" in cache_slice
    assert "cacheTagsInvalidated" in cache_slice

    realtime = (FRONTEND_ROOT / "provider" / "realtimeProvider.tsx").read_text()
    app_data = (FRONTEND_ROOT / "provider" / "appDataProvider.tsx").read_text()
    assert 'payload.type ?? ""' in realtime
    assert "cacheScopeInvalidated" in realtime
    assert "const loadAllData" in app_data
    assert "const refreshAllData" in app_data
    assert "void loadAllData()" in app_data


def test_frontend_cache_does_not_persist_sensitive_api_state() -> None:
    cache = (FRONTEND_ROOT / "lib" / "http-cache.ts").read_text()
    providers = (FRONTEND_ROOT / "provider" / "providers.tsx").read_text()

    assert "redux-persist" not in cache
    assert "persistStore" not in providers
    assert '"/auth/"' in cache
    assert '"/files/"' in cache
    assert '"/pdf"' in cache
    assert '"/export"' in cache


def test_server_middleware_serves_cached_json_and_invalidates_after_write(
    monkeypatch,
) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.middleware.base import BaseHTTPMiddleware

    from core.response_cache import TenantResponseCacheMiddleware

    memory: dict[str, dict[str, object]] = {}
    generation = {"value": 0}

    async def fake_generation(_scope: str) -> int:
        return generation["value"]

    async def fake_get(key: str):
        return memory.get(key)

    async def fake_set(
        key: str,
        *,
        response,
        body: bytes,
        ttl_seconds: int,
    ) -> None:
        assert ttl_seconds > 0
        memory[key] = {
            "status_code": response.status_code,
            "headers": {"content-type": "application/json"},
            "body": body.decode("utf-8"),
        }

    async def fake_bump(_scope: str) -> None:
        generation["value"] += 1

    monkeypatch.setattr(response_cache, "generation", fake_generation)
    monkeypatch.setattr(response_cache, "get", fake_get)
    monkeypatch.setattr(response_cache, "set", fake_set)
    monkeypatch.setattr(response_cache, "bump_generation", fake_bump)

    class FakeAuthContextMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            token = current_user_id.set("user-a")
            try:
                return await call_next(request)
            finally:
                current_user_id.reset(token)

    application = FastAPI()
    calls = {"reads": 0}

    @application.get("/api/v1/test")
    async def read_test():
        calls["reads"] += 1
        return {"reads": calls["reads"]}

    @application.post("/api/v1/test")
    async def write_test():
        return {"ok": True}

    application.add_middleware(TenantResponseCacheMiddleware)
    application.add_middleware(FakeAuthContextMiddleware)

    with TestClient(application) as client:
        first = client.get("/api/v1/test")
        second = client.get("/api/v1/test")
        mutation = client.post("/api/v1/test")
        third = client.get("/api/v1/test")

    assert first.json() == {"reads": 1}
    assert first.headers["X-LoanHub-Server-Cache"] == "MISS"
    assert second.json() == {"reads": 1}
    assert second.headers["X-LoanHub-Server-Cache"] == "HIT"
    assert mutation.status_code == 200
    assert third.json() == {"reads": 2}
    assert third.headers["X-LoanHub-Server-Cache"] == "MISS"
