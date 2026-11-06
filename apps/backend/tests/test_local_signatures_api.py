"""Local PC bridge contract regression tests (no real database or hardware)."""
import base64
import hashlib
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException, Response

from routers import local_signatures as api


def context():
    return SimpleNamespace(
        company_id=uuid4(),
        branch_id=uuid4(),
        user=SimpleNamespace(id=uuid4(), person=None),
        staff=SimpleNamespace(role=next(iter(api.LENDING_ROLES - api.COMPANY_MANAGEMENT_ROLES))),
    )


def test_routes_registered():
    from api.v1.router import api_router
    paths = {route.path for route in api_router.routes}
    assert "/local-signatures/me/status" in paths
    assert "/local-signatures/clients/lookup" in paths
    assert "/local-signatures/captures" in paths


def test_company_membership_required_before_lookup(monkeypatch):
    ctx = context()
    ctx.company_id = None
    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        api.lookup_client(
            api.ClientLookup(national_id="TEST1234"),
            Response(), db=db, context=ctx,
        )
    assert exc.value.status_code == 403
    db.query.assert_not_called()


def test_lookup_budget_blocks_response(monkeypatch):
    ctx = context()
    db = MagicMock()
    monkeypatch.setattr(api, "require_tenant_roles", lambda *_: None)
    def blocked(*_args):
        raise HTTPException(429, "Lookup budget exhausted")
    monkeypatch.setattr(api, "_reserve_lookup_attempt", blocked)
    with pytest.raises(HTTPException) as exc:
        api.lookup_client(
            api.ClientLookup(national_id="TEST1234"),
            Response(), db=db, context=ctx,
        )
    assert exc.value.status_code == 429


def test_operator_status_never_authorizes_signing(monkeypatch):
    ctx = context()
    db = MagicMock()
    monkeypatch.setattr(api, "require_tenant_roles", lambda *_: None)
    db.query.return_value.filter.return_value.first.return_value = None
    answer = api.operator_signature_status(Response(), db=db, context=ctx)
    assert answer["signature_status"] == "missing"
    assert answer["requires_capture"] is True
    assert answer["usable_for_signing"] is False


def test_client_capture_requires_tenant_bound_borrower(monkeypatch):
    ctx = context()
    monkeypatch.setattr(api, "require_tenant_roles", lambda *_: None)
    monkeypatch.setattr(api.settings, "FILE_ENCRYPTION_ENABLED", True)
    db = MagicMock()
    borrower_id = uuid4()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    payload = api.CaptureSubmission(
        signer_kind="client", borrower_id=borrower_id,
        consent_reference="synthetic-consent",
        capture_png_base64=base64.b64encode(b"fake").decode(),
        capture_sha256=hashlib.sha256(b"fake").hexdigest(),
    )
    with pytest.raises(HTTPException) as exc:
        api.upload_capture(payload, Response(), db=db, context=ctx)
    assert exc.value.status_code == 404
    db.commit.assert_not_called()


def test_invalid_png_never_stored(monkeypatch):
    ctx = context()
    monkeypatch.setattr(api, "require_tenant_roles", lambda *_: None)
    monkeypatch.setattr(api.settings, "FILE_ENCRYPTION_ENABLED", True)
    store = MagicMock()
    monkeypatch.setattr(api, "store_bytes", store)
    raw = b"not-a-png"
    payload = api.CaptureSubmission(
        signer_kind="operator",
        consent_reference="synthetic-consent",
        capture_png_base64=base64.b64encode(raw).decode(),
        capture_sha256=hashlib.sha256(raw).hexdigest(),
    )
    db = MagicMock()
    with pytest.raises(HTTPException) as exc:
        api.upload_capture(payload, Response(), db=db, context=ctx)
    assert exc.value.status_code == 422
    store.assert_not_called()
    db.commit.assert_not_called()


def test_valid_png_is_private_and_pending_review(monkeypatch):
    ctx = context()
    monkeypatch.setattr(api, "require_tenant_roles", lambda *_: None)
    monkeypatch.setattr(api.settings, "FILE_ENCRYPTION_ENABLED", True)
    raw = bytes.fromhex("89504e470d0a1a0a") + b"synthetic"
    payload = api.CaptureSubmission(
        signer_kind="operator", consent_reference="synthetic-consent",
        capture_png_base64=base64.b64encode(raw).decode(),
        capture_sha256=hashlib.sha256(raw).hexdigest(),
    )
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    saved = SimpleNamespace(id=uuid4())
    store = MagicMock(return_value=saved)
    monkeypatch.setattr(api, "store_bytes", store)
    result = api.upload_capture(payload, Response(), db=db, context=ctx)
    assert result["status"] == "pending_review"
    assert result["usable_for_signing"] is False
    kwargs = store.call_args.kwargs
    assert kwargs["is_confidential"] is True
    assert kwargs["visibility"] == "private"
    assert kwargs["company_id"] == ctx.company_id
    assert kwargs["linked_entity_id"] == str(ctx.user.id)
    db.commit.assert_called_once()
