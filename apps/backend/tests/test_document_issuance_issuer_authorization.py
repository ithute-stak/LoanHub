"""Official issuer authorization must reflect current persisted membership."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from database.models.enums import CompanyStatus, UserRole
from services.document_issuance_issuer_authorization import require_current_document_issuer


def _case():
    user_id, company_id, staff_id = uuid4(), uuid4(), uuid4()
    user = SimpleNamespace(
        id=user_id, is_active=True, must_change_password=False,
    )
    company = SimpleNamespace(
        id=company_id, is_active=True, status=CompanyStatus.APPROVED,
    )
    staff = SimpleNamespace(
        id=staff_id, user_id=user_id, company_id=company_id,
        role=UserRole.COMPANY_ADMIN, is_active=True,
    )
    context = SimpleNamespace(
        user=user, company=company, staff=staff, company_id=company_id,
        is_platform_admin=False,
    )
    db = Mock()
    db.query.return_value.filter.return_value.populate_existing.return_value.one_or_none.side_effect = [
        user, company, staff,
    ]
    return db, context, user, company, staff


def test_active_current_management_membership_is_required():
    db, context, user, company, staff = _case()
    result = require_current_document_issuer(db=db, context=context)
    assert result.user_id == user.id
    assert result.company_id == company.id
    assert result.staff_id == staff.id
    assert result.role == UserRole.COMPANY_ADMIN.value
    assert db.query.call_count == 3
    # Previously loaded CompanyStaff/LoanCompany objects must not authorize
    # issuance through SQLAlchemy's identity-map cache after an admin update.
    assert db.query.return_value.filter.return_value.populate_existing.call_count == 3
    db.commit.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("is_active", False), ("must_change_password", True),
])
def test_revoked_user_cannot_issue(field, value):
    db, context, user, company, staff = _case()
    setattr(user, field, value)
    with pytest.raises(PermissionError, match="Issuer account"):
        require_current_document_issuer(db=db, context=context)


@pytest.mark.parametrize("field,value", [
    ("is_active", False), ("status", CompanyStatus.PENDING),
    ("id", uuid4()),
])
def test_inactive_or_different_company_rejected(field, value):
    db, context, user, company, staff = _case()
    setattr(company, field, value)
    with pytest.raises(PermissionError, match="company is not currently approved|authenticated company issuer"):
        require_current_document_issuer(db=db, context=context)


@pytest.mark.parametrize("field,value", [
    ("is_active", False), ("role", UserRole.LOAN_OFFICER),
    ("company_id", uuid4()), ("user_id", uuid4()),
    ("id", uuid4()),
])
def test_revoked_or_changed_membership_rejected(field, value):
    db, context, user, company, staff = _case()
    persisted = SimpleNamespace(**vars(staff))
    setattr(persisted, field, value)
    db.query.return_value.filter.return_value.populate_existing.return_value.one_or_none.side_effect = [
        user, company, persisted,
    ]
    with pytest.raises(PermissionError, match="membership was revoked or changed"):
        require_current_document_issuer(db=db, context=context)


def test_context_role_cannot_be_promoted_without_matching_membership():
    db, context, user, company, staff = _case()
    context.staff = SimpleNamespace(**vars(staff))
    context.staff.role = UserRole.COMPANY_OWNER
    with pytest.raises(PermissionError, match="membership was revoked or changed"):
        require_current_document_issuer(db=db, context=context)


def test_foreign_company_or_staff_context_denied_before_database_access():
    db, context, user, company, staff = _case()
    context.staff = SimpleNamespace(**vars(staff))
    context.staff.company_id = uuid4()
    with pytest.raises(PermissionError, match="authenticated company issuer"):
        require_current_document_issuer(db=db, context=context)
    db.query.assert_not_called()


def test_platform_admin_cannot_use_company_issuer_gate():
    db, context, *_ = _case()
    context.is_platform_admin = True
    with pytest.raises(PermissionError):
        require_current_document_issuer(db=db, context=context)
    db.query.assert_not_called()


def test_missing_persisted_staff_denied():
    db, context, user, company, _ = _case()
    db.query.return_value.filter.return_value.populate_existing.return_value.one_or_none.side_effect = [
        user, company, None,
    ]
    with pytest.raises(PermissionError, match="membership"):
        require_current_document_issuer(db=db, context=context)
