"""Wacom ceremony challenge issuance is server-owned and never executes a loan."""
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from types import SimpleNamespace as R
from uuid import uuid4
import inspect

import pytest
from fastapi import HTTPException, Response

from routers import wacom_execution_ceremonies as routes


def test_feature_gate_denies_by_default(monkeypatch):
    monkeypatch.delenv(routes.FEATURE_FLAG, raising=False)
    with pytest.raises(HTTPException) as exc:
        routes._gate()
    assert exc.value.status_code == 503


def test_feature_gate_requires_exact_1(monkeypatch):
    monkeypatch.setenv(routes.FEATURE_FLAG, "true")
    with pytest.raises(HTTPException):
        routes._gate()
    monkeypatch.setenv(routes.FEATURE_FLAG, "1")
    routes._gate()


def test_only_issue_endpoint_and_no_acceptance_endpoint():
    assert {
        (method, route.path)
        for route in routes.router.routes
        for method in (route.methods or set())
    } == {
        ("POST", "/wacom-execution-ceremonies/authorizations/{authorization_id}/challenge")
    }


def test_router_cannot_mark_signed_or_verify_hardware():
    code = inspect.getsource(routes)
    assert 'status="pending"' in code
    for forbidden in (
        "contract.borrower_signed_at =", "contract.status =",
        "authorization.consumed_at =", 'status="verified"',
        'status="consumed"', '"device_verified": True',
    ):
        assert forbidden not in code


def test_challenge_uses_server_randomness_and_persists_digest_only():
    code = inspect.getsource(routes.issue_ceremony_challenge)
    assert "secrets.token_urlsafe(48)" in code
    assert 'hashlib.sha256(plaintext.encode("ascii")).hexdigest()' in code
    assert "challenge_sha256=digest" in code
    assert '"challenge_secret": plaintext' in code
    assert "challenge_secret" not in code[code.index('db.add(AuditLog('):code.index("    try:\n        db.commit()")]
    assert 'response.headers["Cache-Control"] = "no-store"' in code


def test_includes_locking_tenant_and_evidence_integrity_checks():
    code = inspect.getsource(routes.issue_ceremony_challenge)
    assert "require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)" in code
    assert "_locked_sources(db, ctx, candidate.intent_id)" in code
    assert code.count(".with_for_update()") >= 4
    assert "ceremony_challenge_blockers(" in code
    assert "_confirm_packet(db, ctx, packet)" in code
    assert "read_file_bytes(saved)" in code
    assert "hashlib.sha256(archived_pdf).hexdigest()" in code


def test_unique_challenge_digest_and_contract_schema_constraints():
    from database.models.wacom_execution_ceremony_challenge import WacomExecutionCeremonyChallenge
    table = WacomExecutionCeremonyChallenge.__table__
    unique_sets = {
        tuple(sorted(c.columns.keys()))
        for c in table.constraints if type(c).__name__ == "UniqueConstraint"
    }
    assert ("company_id", "contract_id") in unique_sets
    assert ("authorization_id",) in unique_sets
    assert ("receipt_id",) in unique_sets
    assert ("challenge_sha256",) in unique_sets


def test_no_plaintext_challenge_column():
    from database.models.wacom_execution_ceremony_challenge import WacomExecutionCeremonyChallenge
    cols = WacomExecutionCeremonyChallenge.__table__.columns.keys()
    assert "challenge_sha256" in cols
    assert "challenge_secret" not in cols
    assert "secret" not in cols
