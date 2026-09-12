from datetime import date, datetime, timezone
from uuid import uuid4
from decimal import Decimal

from database.schemas.company_clients import (
    AssistedCompanyClientCreate,
    CompanyClientExistingLoanCheckRead,
)
from routers.company_clients import router
from services.company_client_service import borrower_existing_loan_exposure


def test_existing_loan_check_route_is_registered_before_uuid_route():
    paths = [route.path for route in router.routes]
    assert "/company-clients/existing-loan-check" in paths
    assert "/company-clients/{account_id}" in paths
    assert paths.index("/company-clients/existing-loan-check") < paths.index(
        "/company-clients/{account_id}"
    )


def test_existing_borrower_payload_can_omit_new_temporary_password():
    payload = AssistedCompanyClientCreate(
        phone="58000000",
        first_name="Mpho",
        last_name="Mokoena",
        gender="male",
        date_of_birth=date(1990, 1, 1),
        national_id="900101123456",
        district="Maseru",
        employment_status="employed",
    )
    assert payload.temporary_password is None


def test_existing_loan_check_response_preserves_totals():
    response = CompanyClientExistingLoanCheckRead(
        national_id="900101123456",
        borrower_found=True,
        already_company_client=False,
        company_client_account_id=None,
        has_existing_loans=True,
        total_loan_count=5,
        active_loan_count=2,
        completed_loan_count=2,
        defaulted_loan_count=1,
        overdue_loan_count=1,
        lender_count=3,
        loanhub_outstanding_total=Decimal("1500.00"),
        declared_existing_loan_total=Decimal("250.00"),
        existing_loan_total=Decimal("1750.00"),
        lifetime_principal_total=Decimal("6500.00"),
        lifetime_paid_total=Decimal("4750.00"),
        latest_loan_at=datetime.now(timezone.utc),
        checked_at=datetime.now(timezone.utc),
    )
    assert response.total_loan_count == 5
    assert response.active_loan_count == 2
    assert response.completed_loan_count == 2
    assert response.defaulted_loan_count == 1
    assert response.existing_loan_total == Decimal("1750.00")
    assert response.lifetime_paid_total == Decimal("4750.00")


def test_missing_borrower_history_returns_complete_zero_summary():
    result = borrower_existing_loan_exposure(
        None,  # type: ignore[arg-type]
        borrower=None,
        company_id=uuid4(),
    )
    assert result["borrower_found"] is False
    assert result["company_client_account_id"] is None
    assert result["total_loan_count"] == 0
    assert result["defaulted_loan_count"] == 0
    assert result["lifetime_principal_total"] == Decimal("0.00")
