"""Characterize broad invalidation before enabling selective Redis invalidation.

A payments write currently invalidates even unrelated company reference reads.
This test preserves the conservative behaviour until a dependency-aware
invalidation design is tested against real write paths and cross-resource reads.
"""
from __future__ import annotations
import os

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("FERNET_SECRET_KEY", "test-fernet-key")

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

from core.response_cache import TenantResponseCacheMiddleware, response_cache
from utils.convex import current_user_id


def test_company_reference_cache_is_currently_invalidated_by_unrelated_payment(monkeypatch):
    entries = {}
    generations = {}
    calls = {"reference": 0}

    async def generation(scope):
        return generations.get(scope, 0)

    async def cache_get(key):
        return entries.get(key)

    async def cache_set(key, *, response, body, ttl_seconds):
        entries[key] = {"status_code": response.status_code, "headers": {"content-type": "application/json"}, "body": body.decode()}

    async def bump(scope):
        generations[scope] = generations.get(scope, 0) + 1

    monkeypatch.setattr(response_cache, "generation", generation)
    monkeypatch.setattr(response_cache, "get", cache_get)
    monkeypatch.setattr(response_cache, "set", cache_set)
    monkeypatch.setattr(response_cache, "bump_generation", bump)

    class FakeUser(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            token = current_user_id.set("user-a")
            try:
                return await call_next(request)
            finally:
                current_user_id.reset(token)

    app = FastAPI()

    @app.get("/api/v1/hr/departments")
    def departments(request: Request):
        calls["reference"] += 1
        return {"version": calls["reference"]}

    @app.post("/api/v1/payments")
    def payment():
        return {"posted": True}

    app.add_middleware(TenantResponseCacheMiddleware)
    app.add_middleware(FakeUser)
    with TestClient(app) as client:
        headers = {"X-Company-ID": "tenant-a"}
        first = client.get("/api/v1/hr/departments", headers=headers)
        second = client.get("/api/v1/hr/departments", headers=headers)
        posted = client.post("/api/v1/payments", headers=headers)
        third = client.get("/api/v1/hr/departments", headers=headers)

    assert first.headers["X-LoanHub-Server-Cache"] == "MISS"
    assert second.headers["X-LoanHub-Server-Cache"] == "HIT"
    assert posted.status_code == 200
    assert third.headers["X-LoanHub-Server-Cache"] == "MISS"
    assert calls["reference"] == 2
