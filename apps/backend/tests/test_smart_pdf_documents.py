from datetime import date
from types import SimpleNamespace

from services.loan_document_service import (
    generate_loan_information_pdf,
    generate_repayment_schedule_pdf,
)
from services.reporting_service import build_pdf


def _loan():
    person = SimpleNamespace(
        full_name="Test Borrower",
        national_id="123456789012",
        passport_number=None,
        physical_address="Maseru",
        town_or_village="Maseru",
        district="Maseru",
    )
    user = SimpleNamespace(person=person, phone="58000000", email="borrower@example.com")
    borrower = SimpleNamespace(user=user)
    company = SimpleNamespace(name="Example Lender", license_number="ML-001")
    paid = SimpleNamespace(value="paid")
    pending = SimpleNamespace(value="pending")
    installments = [
        SimpleNamespace(
            installment_number=1,
            due_date=date(2026, 8, 22),
            principal_due=500,
            interest_due=50,
            fee_due=10,
            total_due=560,
            paid_amount=560,
            status=paid,
        ),
        SimpleNamespace(
            installment_number=2,
            due_date=date(2026, 9, 22),
            principal_due=500,
            interest_due=50,
            fee_due=10,
            total_due=560,
            paid_amount=0,
            status=pending,
        ),
    ]
    return SimpleNamespace(
        loan_reference="LN-TEST-001",
        status=SimpleNamespace(value="active"),
        principal_amount=1000,
        processing_fee=20,
        total_repayable=1120,
        installment_amount=560,
        repayment_period=2,
        interest_rate=10,
        calculation_method="simple_interest",
        calculation_breakdown={
            "method": "simple_interest",
            "method_label": "Simple Interest",
            "rate_basis": "Annual nominal rate applied to original principal",
        },
        first_payment_due=date(2026, 8, 22),
        maturity_date=date(2026, 9, 22),
        amount_paid=560,
        balance=560,
        borrower=borrower,
        company=company,
        installments=installments,
        payment_transactions=[],
        approved_by_user_id=None,
        disbursed_by_user_id=None,
        company_id=None,
        branch_id=None,
    )


def test_smart_loan_information_pdf_is_generated():
    content = generate_loan_information_pdf(None, _loan())
    assert content.startswith(b"%PDF-")
    assert len(content) > 10_000


def test_smart_repayment_schedule_pdf_is_generated():
    content = generate_repayment_schedule_pdf(None, _loan())
    assert content.startswith(b"%PDF-")
    assert len(content) > 10_000


def test_smart_accounting_report_pdf_is_generated():
    content = build_pdf(
        db=None,
        company=SimpleNamespace(name="Example Lender", license_number="ML-001"),
        title="Accounting Report - Example Lender",
        reference="RPT-TEST-001",
        scope_name="Example Lender",
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        metrics={
            "accounting_revenue": 1000,
            "accounting_expenses": 600,
            "accounting_net_profit": 400,
            "accounting_assets": 2000,
            "accounting_liabilities": 500,
            "accounting_equity": 1500,
            "treasury_money_in": 900,
            "treasury_money_out": 500,
            "treasury_net_movement": 400,
            "outstanding_balance": 800,
        },
        report_type="accounting",
    )
    assert content.startswith(b"%PDF-")
    assert len(content) > 10_000
