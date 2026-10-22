"""Cache invalidation regression tests before performance optimizations."""
from __future__ import annotations

import os
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("FERNET_SECRET_KEY", "test-fernet-key")

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from core.response_cache import TenantResponseCacheMiddleware, response_cache
from utils.convex import current_user_id


def test_same_tenant_payment_write_invalidates_cached_reads_without_touching_other_tenants(monkeypatch):
    cache = {}
    generations = {}
    reads = {}

    async def generation(scope):
        return generations.get(scope, 0)

    async def get(key):
        return cache.get(key)

    async def set_(key, *, response, body, ttl_seconds):
        cache[key] = {"body": body.decode(), "status_code": response.status_code, "headers": {"content-type": "application/json"}}

    async def bump(scope):
        generations[scope] = generations.get(scope, 0) + 1

    monkeypatch.setattr(response_cache, "generation", generation)
    monkeypatch.setattr(response_cache, "get", get)
    monkeypatch.setattr(response_cache, "set", set_)
    monkeypatch.setattr(response_cache, "bump_generation", bump)

    class ScopedAuth(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            user = request.headers.get("x-test-user", "user-a")
            token = current_user_id.set(user)
            try:
                return await call_next(request)
            finally:
                current_user_id.reset(token)

    app = FastAPI()

    @app.get("/api/v1/loans")
    def loans(request: Request):
        company = request.headers["x-company-id"]
        reads[company] = reads.get(company, 0) + 1
        return {"company": company, "read": reads[company]}

    @app.post("/api/v1/payments")
    def payment():
        return {"posted": True}

    app.add_middleware(TenantResponseCacheMiddleware)
    app.add_middleware(ScopedAuth)

    with TestClient(app) as client:
        a = {"x-company-id": "tenant-a", "x-test-user": "user-a"}
        b = {"x-company-id": "tenant-b", "x-test-user": "user-b"}
        assert client.get("/api/v1/loans", headers=a).json()["read"] == 1
        assert client.get("/api/v1/loans", headers=a).headers["X-LoanHub-Server-Cache"] == "HIT"
        assert client.get("/api/v1/loans", headers=b).json()["read"] == 1
        assert client.post("/api/v1/payments", headers=a).status_code == 200
        assert client.get("/api/v1/loans", headers=a).json()["read"] == 2
        assert client.get("/api/v1/loans", headers=b).json()["read"] == 1
        assert client.get("/api/v1/loans", headers=b).headers["X-LoanHub-Server-Cache"] == "HIT"
