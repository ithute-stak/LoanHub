from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES
from database.models.enums import UserRole
from database.schemas.professional_lending import (
    DirectApplicationApprove,
    DirectApplicationCreate,
    DirectApplicationReject,
)
from routers.loan_products import validate_values
from routers.professional_lending import (
    DIRECT_APPLICATION_APPROVAL_ROLES,
    DIRECT_APPLICATION_REVIEW_ROLES,
    DIRECT_APPLICATION_VIEW_ROLES,
)
from services.billing_service import company_plan_limit


def manual_dates(count: int = 3):
    first = date.today() + timedelta(days=30)
    return [first + timedelta(days=35 * index) for index in range(count)]


def test_direct_application_accepts_monthly_micro_loan_request():
    payload = DirectApplicationCreate(
        borrower_id=uuid4(),
        requested_amount=Decimal("1000.00"),
        term_count=3,
        repayment_type="monthly",
        installment_due_dates=manual_dates(),
    )
    assert payload.requested_amount == Decimal("1000.00")
    assert payload.term_count == 3


def test_direct_application_rejects_non_monthly_repayment_type():
    with pytest.raises(ValidationError):
        DirectApplicationCreate(
            borrower_id=uuid4(),
            requested_amount=Decimal("1000.00"),
            term_count=3,
            repayment_type="weekly",
            installment_due_dates=manual_dates(),
        )


def test_approval_payload_accepts_product_defaults_or_overrides():
    payload = DirectApplicationApprove(
        product_id=uuid4(),
        approved_amount=Decimal("1000.00"),
        interest_rate=Decimal("20"),
        processing_fee=Decimal("25.00"),
        installment_due_dates=manual_dates(),
    )
    assert payload.interest_rate == Decimal("20")
    assert payload.processing_fee == Decimal("25.00")


def test_rejection_requires_a_meaningful_reason():
    with pytest.raises(ValidationError):
        DirectApplicationReject(reason="no")


def test_product_range_validation_returns_controlled_client_error():
    with pytest.raises(HTTPException) as caught:
        validate_values(
            min_amount=Decimal("1000"),
            max_amount=Decimal("500"),
            min_term_months=1,
            max_term_months=3,
        )
    assert caught.value.status_code == 400
    assert "Maximum amount" in str(caught.value.detail)


def test_missing_optional_billing_tables_use_product_limit_fallback():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    with Session(engine) as session:
        assert company_plan_limit(
            session,
            company_id=uuid4(),
            resource="products",
            fallback=3,
        ) == 3


def test_internal_application_separation_of_duties():
    assert UserRole.LOAN_OFFICER in DIRECT_APPLICATION_VIEW_ROLES
    assert UserRole.LOAN_OFFICER not in DIRECT_APPLICATION_APPROVAL_ROLES
    assert UserRole.RISK_MANAGER in DIRECT_APPLICATION_REVIEW_ROLES
    assert UserRole.BRANCH_MANAGER in DIRECT_APPLICATION_APPROVAL_ROLES
    assert COMPANY_MANAGEMENT_ROLES.issubset(DIRECT_APPLICATION_APPROVAL_ROLES)
