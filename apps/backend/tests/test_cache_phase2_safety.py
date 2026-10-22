"""Phase 2 safety regression coverage for the existing backend response cache.

These tests document isolation and failure behaviour before optimizing cache
invalidation granularity. No production caching policy changes are implied.
"""
from __future__ import annotations

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("FERNET_SECRET_KEY", "test-fernet-key")

from starlette.requests import Request

from core.response_cache import _request_is_cacheable, response_cache
from utils.convex import current_user_id


def request(path: str, *, query: bytes = b"", method: str = "GET", headers=None) -> Request:
    return Request({
        "type": "http", "http_version": "1.1", "method": method,
        "scheme": "https", "path": path, "raw_path": path.encode(),
        "query_string": query, "headers": headers or [],
        "client": ("127.0.0.1", 12000), "server": ("testserver", 443),
    })


def test_cache_keys_isolate_tenants_users_roles_and_filters():
    req = request("/api/v1/company/clients", query=b"page=2&status=active")
    identities = [
        "user-a:company-a:admin", "user-a:company-b:admin",
        "user-b:company-a:admin", "user-a:company-a:staff",
    ]
    keys = [response_cache.response_key(request=req, identity=identity, generation=2) for identity in identities]
    assert len(set(keys)) == len(keys)
    reordered = request("/api/v1/company/clients", query=b"status=active&page=2")
    assert response_cache.response_key(request=reordered, identity=identities[0], generation=2) == keys[0]
    different_filter = request("/api/v1/company/clients", query=b"status=overdue&page=2")
    assert response_cache.response_key(request=different_filter, identity=identities[0], generation=2) != keys[0]
    assert response_cache.response_key(request=req, identity=identities[0], generation=3) != keys[0]


def test_auth_sensitive_payloads_and_writes_never_enter_response_cache():
    token = current_user_id.set("user-a")
    try:
        for path in (
            "/api/v1/auth/me", "/api/v1/payroll/payslips", "/api/v1/banking/accounts",
            "/api/v1/financial-profile", "/api/v1/files/download",
            "/api/v1/loans/export", "/api/v1/payments/receipt",
        ):
            assert not _request_is_cacheable(request(path)), path
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            assert not _request_is_cacheable(request("/api/v1/payments", method=method))
        assert not _request_is_cacheable(request("/api/v1/company/clients", headers=[(b"x-loanhub-cache", b"bypass")]))
    finally:
        current_user_id.reset(token)


def test_backend_cache_falls_back_when_redis_is_unavailable(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from starlette.middleware.base import BaseHTTPMiddleware
    from core.response_cache import TenantResponseCacheMiddleware

    async def unavailable_generation(_scope):
        return 0

    async def unavailable_get(_key):
        return None

    async def unavailable_set(*args, **kwargs):
        return None

    async def unavailable_bump(_scope):
        return None

    monkeypatch.setattr(response_cache, "generation", unavailable_generation)
    monkeypatch.setattr(response_cache, "get", unavailable_get)
    monkeypatch.setattr(response_cache, "set", unavailable_set)
    monkeypatch.setattr(response_cache, "bump_generation", unavailable_bump)

    class Auth(BaseHTTPMiddleware):
        async def dispatch(self, req, call_next):
            token = current_user_id.set("user-a")
            try:
                return await call_next(req)
            finally:
                current_user_id.reset(token)

    app = FastAPI()
    calls = {"read": 0}

    @app.get("/api/v1/company/clients")
    def clients():
        calls["read"] += 1
        return {"read": calls["read"]}

    @app.post("/api/v1/company/clients")
    def create():
        return {"ok": True}

    app.add_middleware(TenantResponseCacheMiddleware)
    app.add_middleware(Auth)
    with TestClient(app) as client:
        first = client.get("/api/v1/company/clients")
        second = client.get("/api/v1/company/clients")
        write = client.post("/api/v1/company/clients")
    assert first.status_code == second.status_code == write.status_code == 200
    assert first.json()["read"] == 1
    assert second.json()["read"] == 2
    assert first.headers["X-LoanHub-Server-Cache"] == "MISS"
    assert write.headers["X-LoanHub-Server-Cache"] == "BYPASS"
