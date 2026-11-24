"""Loan document source must be bound to an existing approved tenant loan."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from fastapi import HTTPException

from database.models.enums import LoanStatus, UserRole
from services.document_issuance_loan_source import (
    require_authorized_loan_document_record, stage_authorized_loan_pdf_source,
)


def _case():
    tenant, issuer, loan_id = uuid4(), uuid4(), uuid4()
    context = SimpleNamespace(
        company_id=tenant, company=SimpleNamespace(id=tenant),
        user=SimpleNamespace(id=issuer),
        staff=SimpleNamespace(role=UserRole.COMPANY_ADMIN),
        is_platform_admin=False,
    )
    loan = SimpleNamespace(
        id=loan_id, company_id=tenant, borrower_id=uuid4(),
        status=LoanStatus.APPROVED,
        approved_at=datetime.now(timezone.utc),
    )
    db = Mock()
    db.query.return_value.filter.return_value.one_or_none.return_value = loan
    return db, context, loan_id, loan


def test_approved_tenant_loan_is_accepted():
    db, ctx, loan_id, loan = _case()
    assert require_authorized_loan_document_record(
        db=db, context=ctx, loan_id=loan_id,
    ) is loan
    db.add.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.parametrize("change", [
    {"company_id": uuid4()},
    {"id": uuid4()},
    {"borrower_id": None},
    {"approved_at": None},
    {"status": LoanStatus.PENDING},
    {"status": LoanStatus.REJECTED},
    {"status": LoanStatus.CANCELLED},
])
def test_unapproved_or_mismatched_loan_cannot_be_document_source(change):
    db, ctx, loan_id, loan = _case()
    for name, value in change.items():
        setattr(loan, name, value)
    with pytest.raises(PermissionError, match="Approved tenant-owned loan"):
        require_authorized_loan_document_record(
            db=db, context=ctx, loan_id=loan_id,
        )


def test_missing_loan_rejected():
    db, ctx, loan_id, _ = _case()
    db.query.return_value.filter.return_value.one_or_none.return_value = None
    with pytest.raises(PermissionError):
        require_authorized_loan_document_record(
            db=db, context=ctx, loan_id=loan_id,
        )


def test_wrong_role_rejected_without_database_access():
    db, ctx, loan_id, _ = _case()
    ctx.staff.role = UserRole.LOAN_OFFICER
    with pytest.raises(HTTPException) as error:
        require_authorized_loan_document_record(
            db=db, context=ctx, loan_id=loan_id,
        )
    assert error.value.status_code == 403
    db.query.assert_not_called()


def test_stage_uses_exact_approved_loan_identity_as_managed_file_link():
    db, ctx, loan_id, _ = _case()
    source_file_id = uuid4()
    store = object()
    with patch(
        "services.document_issuance_loan_source.stage_authorized_managed_pdf_source",
        return_value="staged",
    ) as stage:
        result = stage_authorized_loan_pdf_source(
            db=db, context=ctx, loan_id=loan_id,
            source_file_id=source_file_id,
            trusted_verification_origin="https://verify.example.test",
            store=store, stamp_configuration_version=3,
        )
    assert result == "staged"
    stage.assert_called_once_with(
        db=db, context=ctx, source_file_id=source_file_id,
        source_type="client_company_loan", source_id=str(loan_id),
        trusted_verification_origin="https://verify.example.test",
        store=store, stamp_configuration_version=3,
    )


def test_rejected_loan_prevents_staging():
    db, ctx, loan_id, loan = _case()
    loan.status = LoanStatus.REJECTED
    with patch(
        "services.document_issuance_loan_source.stage_authorized_managed_pdf_source",
    ) as stage:
        with pytest.raises(PermissionError):
            stage_authorized_loan_pdf_source(
                db=db, context=ctx, loan_id=loan_id,
                source_file_id=uuid4(),
                trusted_verification_origin="https://verify.example.test",
                store=object(), stamp_configuration_version=3,
            )
    stage.assert_not_called()
