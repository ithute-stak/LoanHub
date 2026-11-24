"""Security and default-off contract tests for managed-file document analysis."""
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi import HTTPException

from database.models.enums import UserRole
from routers.document_intelligence import _authorize, _enabled, router


def actor(*, role=UserRole.LOAN_OFFICER, company_id=None):
    company = company_id or uuid4()
    return SimpleNamespace(
        company_id=company,
        staff=SimpleNamespace(role=role) if role else None,
    )


def file_record(company_id, *, category="borrower_payslip", scan="clean", confidential=True):
    return SimpleNamespace(
        is_deleted=False, company_id=company_id, category=category,
        is_confidential=confidential, scan_status=scan,
    )


def test_feature_disabled_unless_explicitly_enabled():
    with patch.dict("os.environ", {}, clear=True):
        assert not _enabled()
    with patch.dict("os.environ", {"LOANHUB_DOCUMENT_INTELLIGENCE_ENABLED": "true"}):
        assert _enabled()
    with patch.dict("os.environ", {"LOANHUB_DOCUMENT_INTELLIGENCE_ENABLED": "yes"}):
        assert not _enabled()


def test_cross_company_and_non_lending_access_fail_closed():
    company = uuid4()
    context = actor(company_id=company)
    with pytest.raises(HTTPException) as error:
        _authorize(context=context, record=file_record(uuid4()), db=object())
    assert error.value.status_code == 404
    with pytest.raises(HTTPException) as error:
        _authorize(context=actor(role=UserRole.BORROWER), record=file_record(company), db=object())
    assert error.value.status_code == 403


@pytest.mark.parametrize("category,scan,confidential", [
    ("general", "clean", True),
    ("borrower_payslip", "quarantined", True),
    ("borrower_payslip", "clean", False),
])
def test_unapproved_file_evidence_is_not_analysed(category, scan, confidential):
    context = actor()
    record = file_record(context.company_id, category=category, scan=scan, confidential=confidential)
    with pytest.raises(HTTPException) as error:
        _authorize(context=context, record=record, db=object())
    assert error.value.status_code == 404


def test_authorized_file_still_needs_existing_file_access_guard():
    context = actor()
    record = file_record(context.company_id)
    with patch("routers.document_intelligence.can_access_file", return_value=False):
        with pytest.raises(HTTPException) as error:
            _authorize(context=context, record=record, db=object())
    assert error.value.status_code == 404
    with patch("routers.document_intelligence.can_access_file", return_value=True):
        assert _authorize(context=context, record=record, db=object()) is None


def test_only_preview_route_is_exposed():
    routes = [r for r in router.routes if getattr(r, "path", "").endswith("/review")]
    assert len(routes) == 1
    assert routes[0].methods == {"POST"}
