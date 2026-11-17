from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from database.models.enums import UserRole
from services.document_issuance_registration import register_stored_pdf_issuance


def context(*, company_id=None, role=UserRole.COMPANY_ADMIN, platform=False):
    return SimpleNamespace(
        company_id=company_id or uuid4(),
        staff=SimpleNamespace(role=role),
        user=SimpleNamespace(id=uuid4()),
        is_platform_admin=platform,
    )


def request(db, ctx, **override):
    parameters = dict(
        db=db, context=ctx, managed_file_id=uuid4(),
        source_type="workspace", source_id="doc-123",
        document_type="contract", idempotency_key="request-123",
        version=1, stamp_configuration_version=1,
    )
    parameters.update(override)
    return register_stored_pdf_issuance(**parameters)


def test_platform_administrator_cannot_impersonate_company_issuer():
    db = Mock()
    with pytest.raises(PermissionError):
        request(db, context(platform=True))
    db.query.assert_not_called()


def test_malformed_ids_and_versions_are_rejected_before_db_access():
    for invalid in (
        {"source_id": ""}, {"source_type": " "},
        {"document_type": "a" * 81}, {"idempotency_key": "a" * 121},
        {"version": 0}, {"version": True},
        {"stamp_configuration_version": 0},
    ):
        db = Mock()
        with pytest.raises(ValueError):
            request(db, context(), **invalid)
        db.query.assert_not_called()


def test_non_management_roles_cannot_issue_documents():
    db = Mock()
    with pytest.raises(Exception):
        request(db, context(role=UserRole.LOAN_OFFICER))
    db.query.assert_not_called()
