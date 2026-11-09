"""Wacom authorization endpoints remain disabled and do not sign contracts."""
import inspect
import pytest
from fastapi import HTTPException

from routers import wacom_execution_authorizations as routes


def test_feature_off_by_default(monkeypatch):
    monkeypatch.delenv(routes.FEATURE_FLAG, raising=False)
    with pytest.raises(HTTPException) as exc:
        routes._gate()
    assert exc.value.status_code == 503


def test_feature_enabled_only_with_explicit_flag(monkeypatch):
    monkeypatch.setenv(routes.FEATURE_FLAG, "yes")
    with pytest.raises(HTTPException):
        routes._gate()
    monkeypatch.setenv(routes.FEATURE_FLAG, "1")
    routes._gate()


def test_only_request_and_decision_operations_exposed():
    operations = {
        (method, route.path)
        for route in routes.router.routes
        for method in (getattr(route, "methods", None) or [])
    }
    assert operations == {
        ("POST", "/wacom-execution-authorizations/intents/{intent_id}"),
        ("POST", "/wacom-execution-authorizations/{authorization_id}/decision"),
    }


def test_no_final_signing_or_contract_mutation():
    source = inspect.getsource(routes)
    assert "borrower_signed_at =" not in source
    assert "company_signed_at =" not in source
    assert "PdfWriter(" not in source
    assert "store_bytes(" not in source
    assert "LoanContract.status =" not in source


def test_independent_roles_and_locks_are_mandatory():
    source = inspect.getsource(routes)
    assert source.count("require_tenant_roles(ctx, COMPANY_MANAGEMENT_ROLES)") == 2
    assert "with_for_update()" in source
    assert "authorization_decision_blockers(" in source
    assert "authorization_request_blockers(" in source


def test_decision_schema_forbids_unapproved_fields():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        routes.AuthorizationDecision(
            decision="approve", reference="approved-reference",
            exact_document_sha256="a"*64, force_sign=True,
        )
