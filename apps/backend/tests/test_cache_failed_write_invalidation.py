"""Ensure failed financial writes do not invalidate unrelated response cache entries."""
import os
os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("FERNET_SECRET_KEY", "test-fernet-key")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware
from core.response_cache import TenantResponseCacheMiddleware, response_cache
from utils.convex import current_user_id


def test_failed_payment_does_not_invalidate_cached_references_or_loans(monkeypatch):
    entries = {}
    generations = {}
    reads = {"loans": 0, "departments": 0}

    async def generation(scope):
        return generations.get(scope, 0)

    async def get(key):
        return entries.get(key)

    async def set_(key, *, response, body, ttl_seconds):
        entries[key] = {
            "status_code": response.status_code,
            "headers": {"content-type": "application/json"},
            "body": body.decode(),
        }

    async def bump(scope):
        generations[scope] = generations.get(scope, 0) + 1

    monkeypatch.setattr(response_cache, "generation", generation)
    monkeypatch.setattr(response_cache, "get", get)
    monkeypatch.setattr(response_cache, "set", set_)
    monkeypatch.setattr(response_cache, "bump_generation", bump)

    class FakeAuth(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            token = current_user_id.set("user-a")
            try:
                return await call_next(request)
            finally:
                current_user_id.reset(token)

    app = FastAPI()

    @app.get("/api/v1/loans")
    def loans():
        reads["loans"] += 1
        return {"version": reads["loans"]}

    @app.get("/api/v1/hr/departments")
    def departments():
        reads["departments"] += 1
        return {"version": reads["departments"]}

    @app.post("/api/v1/payments", status_code=422)
    def rejected_payment():
        return {"error": "rejected"}

    app.add_middleware(TenantResponseCacheMiddleware)
    app.add_middleware(FakeAuth)
    with TestClient(app) as client:
        headers = {"X-Company-ID": "tenant-a"}
        for path in ("/api/v1/loans", "/api/v1/hr/departments"):
            assert client.get(path, headers=headers).headers["X-LoanHub-Server-Cache"] == "MISS"
        assert client.post("/api/v1/payments", headers=headers).status_code == 422
        for path in ("/api/v1/loans", "/api/v1/hr/departments"):
            assert client.get(path, headers=headers).headers["X-LoanHub-Server-Cache"] == "HIT"
    assert reads == {"loans": 1, "departments": 1}
