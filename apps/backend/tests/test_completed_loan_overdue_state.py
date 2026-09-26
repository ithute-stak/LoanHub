from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from database.models.enums import LoanStatus, RepaymentType, RiskLevel
from database.schemas.loan import LoanRead


ROOT = Path(__file__).resolve().parents[3]
FRONTEND_LOAN_API = ROOT / "apps" / "frontend" / "api" / "loans.ts"


def loan_read(**overrides) -> LoanRead:
    payload = {
        "id": uuid4(),
        "loan_request_id": None,
        "loan_offer_id": None,
        "company_id": uuid4(),
        "branch_id": None,
        "borrower_id": uuid4(),
        "loan_reference": "LEG-TEST-COMPLETE",
        "origination_channel": "legacy_cashout",
        "principal_amount": Decimal("1800.00"),
        "interest_rate": Decimal("0"),
        "processing_fee": Decimal("0"),
        "total_repayable": Decimal("2376.00"),
        "repayment_type": RepaymentType.MONTHLY,
        "repayment_period": 3,
        "installment_amount": Decimal("792.00"),
        "calculation_method": "micro_loan",
        "calculation_breakdown": {},
        "approved_at": None,
        "disbursed_at": None,
        "first_payment_due": None,
        "maturity_date": None,
        "amount_paid": Decimal("2376.00"),
        "balance": Decimal("0.00"),
        "status": LoanStatus.COMPLETED,
        "risk_level": RiskLevel.LOW,
        "is_overdue": True,
        "installments": [],
        "renewal_cycles": [],
    }
    payload.update(overrides)
    return LoanRead(**payload)


def test_completed_zero_balance_loan_cannot_be_currently_overdue() -> None:
    loan = loan_read()

    assert loan.status == LoanStatus.COMPLETED
    assert loan.balance == Decimal("0.00")
    assert loan.is_overdue is False


def test_zero_balance_active_loan_cannot_be_currently_overdue() -> None:
    loan = loan_read(status=LoanStatus.ACTIVE)

    assert loan.is_overdue is False


def test_non_live_loan_cannot_be_currently_overdue_even_with_balance() -> None:
    loan = loan_read(
        status=LoanStatus.APPROVED,
        balance=Decimal("2376.00"),
        amount_paid=Decimal("0.00"),
    )

    assert loan.is_overdue is False


def test_live_outstanding_loan_preserves_real_overdue_state() -> None:
    loan = loan_read(
        status=LoanStatus.ACTIVE,
        balance=Decimal("835.20"),
        amount_paid=Decimal("1540.80"),
        is_overdue=True,
    )

    assert loan.is_overdue is True


def test_frontend_normalizes_loan_state_before_portfolio_rendering() -> None:
    source = FRONTEND_LOAN_API.read_text(encoding="utf-8")

    assert "function normalizeLoanCurrentState(loan: Loan): Loan" in source
    assert 'status === "active" || status === "defaulted"' in source
    assert "hasOutstandingBalance" in source
    assert ".data.map(normalizeLoanCurrentState)" in source
    assert "return normalizeLoanCurrentState(" in source
