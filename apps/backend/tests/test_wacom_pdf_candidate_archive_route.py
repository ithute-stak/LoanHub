"""Wacom final PDF candidate archive must NEVER execute the contract."""
from hashlib import sha256
from types import SimpleNamespace as Row
from uuid import uuid4
import inspect

import pytest
from fastapi import HTTPException

from routers import wacom_pdf_candidates as routes


def test_archive_off_by_default(monkeypatch):
    monkeypatch.delenv(routes.FLAG, raising=False)
    with pytest.raises(HTTPException) as exc:
        routes._gate()
    assert exc.value.status_code == 503


def test_archive_requires_exact_explicit_gate(monkeypatch):
    monkeypatch.setenv(routes.FLAG, "true")
    with pytest.raises(HTTPException):
        routes._gate()
    monkeypatch.setenv(routes.FLAG, "1")
    routes._gate()


def test_only_explicit_archive_endpoint():
    routes_found = {
        (method, r.path)
        for r in routes.router.routes
        for method in (getattr(r, "methods", None) or set())
    }
    assert routes_found == {
        ("POST", "/wacom-pdf-candidates/authorizations/{authorization_id}/archive")
    }


def test_receipt_response_always_declares_unsigned():
    record = Row(
        id=uuid4(), executed_file_id=uuid4(), executed_pdf_sha256="a" * 64,
    )
    result = routes._receipt_response(record, duplicate=False)
    assert result["contract_signed"] is False
    assert result["execution_performed"] is False
    assert result["status"] == "candidate_archived_not_signed"
    assert result["duplicate"] is False


def test_no_contract_signing_or_loan_mutation_in_route():
    source = inspect.getsource(routes)
    for forbidden in (
        "contract.status =", "contract.borrower_signed_at =",
        "contract.locked_at =", "authorization.status =",
        "authorization.consumed_at =", "receipt.status = 'executed'",
    ):
        assert forbidden not in source


def test_archival_uses_locks_and_tenant_scoped_authentication():
    source = inspect.getsource(routes.archive_pdf_candidate)
    assert "require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)" in source
    assert "with_for_update()" in source
    assert "_locked_sources(db, ctx," in source
    assert "reserve_execution_blockers(" in source
    assert "execution_commit_blockers(" in source
    assert "read_file_bytes(stored)" in source
    assert "is_confidential=True" in source
    assert "db.commit()" in source


def test_same_request_does_not_issue_new_receipt(monkeypatch):
    row = Row(
        id=uuid4(), company_id=uuid4(), contract_id=uuid4(),
        intent_id=uuid4(), authorization_id=uuid4(),
        field_binding_sha256="f" * 64, status="reserved",
        executed_file_id=uuid4(), executed_pdf_sha256="a" * 64,
    )
    intent = Row(id=row.intent_id, contract_id=row.contract_id)
    permit = Row(id=row.authorization_id, field_binding_sha256="f" * 64)
    ctx = Row(company_id=row.company_id)
    saved = Row(
        id=row.executed_file_id, company_id=row.company_id,
        is_deleted=False, is_encrypted=True, is_confidential=True,
        scan_status="clean", category="wacom_execution_candidate",
        checksum_sha256=row.executed_pdf_sha256,
    )
    class Query:
        def filter(self, *args):
            return self
        def one_or_none(self):
            return saved
    class Db:
        def query(self, *args):
            return Query()
    monkeypatch.setattr(routes, "read_file_bytes", lambda stored: b"sample")
    with pytest.raises(HTTPException) as exc:
        routes._verify_existing(Db(), ctx, row, intent, permit)
    assert exc.value.status_code == 409


def test_replayed_receipt_cannot_change_authorization():
    row = Row(
        id=uuid4(), company_id=uuid4(), contract_id=uuid4(),
        intent_id=uuid4(), authorization_id=uuid4(),
        field_binding_sha256="f" * 64, status="reserved",
        executed_file_id=uuid4(), executed_pdf_sha256="a" * 64,
    )
    ctx = Row(company_id=row.company_id)
    intent = Row(id=row.intent_id, contract_id=row.contract_id)
    permit = Row(id=uuid4(), field_binding_sha256="f" * 64)
    with pytest.raises(HTTPException) as exc:
        routes._verify_existing(None, ctx, row, intent, permit)
    assert exc.value.status_code == 409
