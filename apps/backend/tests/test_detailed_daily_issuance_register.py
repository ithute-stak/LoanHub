"""Detailed issuance register: exact cash-to-borrower semantics and tenant-safe exports."""
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
from types import SimpleNamespace
from uuid import uuid4

from pypdf import PdfReader

from database.models.enums import UserRole
from routers import reports


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *_args):
        return self

    def group_by(self, *_args):
        return self

    def options(self, *_args):
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, daily_rows, loans):
        self.daily_rows = daily_rows
        self.loans = loans
        self.calls = 0

    def query(self, *_args):
        self.calls += 1
        return FakeQuery(self.daily_rows if self.calls == 1 else self.loans)


def make_loan(reference, principal, cash, settlement, is_top_up, branch):
    borrower = SimpleNamespace(
        user=SimpleNamespace(person=SimpleNamespace(full_name="Test Borrower " + reference))
    )
    officer = SimpleNamespace(person=SimpleNamespace(full_name="Test Officer"))
    return SimpleNamespace(
        id=uuid4(), disbursed_at=datetime(2026, 11, 24, 9, 15),
        loan_reference=reference, folio_number="FOL-" + reference,
        branch=SimpleNamespace(name=branch), borrower=borrower,
        disbursed_by=officer, is_top_up=is_top_up,
        principal_amount=Decimal(principal), top_up_cash_amount=Decimal(cash),
        top_up_settlement_amount=Decimal(settlement),
        total_repayable=Decimal("1800.00"), repayment_period=3,
        installment_amount=Decimal("600.00"), first_payment_due=date(2026, 12, 20),
    )


def test_detailed_register_distinguishes_topup_cash_from_new_principal(monkeypatch):
    monkeypatch.setattr(reports, "require_reports", lambda *_args: None)
    daily = [SimpleNamespace(
        issue_date=date(2026, 11, 24), loans_issued=2,
        principal_issued=Decimal("3000.00"),
        expected_contractual_return=Decimal("3600.00"),
    )]
    db = FakeDB(daily, [
        make_loan("ONE", "1000.00", "0.00", "0.00", False, "Maseru"),
        make_loan("TWO", "2000.00", "800.00", "1200.00", True, "Roma"),
    ])
    report = reports.daily_issuance_expected_returns(
        period_start=date(2026, 11, 24),
        period_end=date(2026, 11, 24),
        include_details=True,
        db=db,
        context=SimpleNamespace(
            is_platform_admin=False, role=UserRole.COMPANY_OWNER,
            company_id=uuid4(), branch_id=None,
        ),
    )
    assert report["totals"]["principal_issued"] == "3000.00"
    assert report["cash_to_borrowers"] == "1800.00"
    assert report["details"][0]["client_name"] == "Test Borrower ONE"
    assert report["details"][0]["branch"] == "Maseru"
    assert report["details"][1]["cash_to_borrower"] == "800.00"
    assert report["details"][1]["top_up_settlement"] == "1200.00"
    assert db.calls == 2


def test_detailed_pdf_includes_client_rows_and_cash_payout(monkeypatch):
    report = {
        "period_start": "2026-11-24", "period_end": "2026-11-24",
        "daily": [{
            "date": "2026-11-24", "loans_issued": 1,
            "principal_issued": "2000.00", "expected_contractual_return": "2400.00",
            "expected_return_above_principal": "400.00",
        }],
        "totals": {
            "loans_issued": 1, "principal_issued": "2000.00",
            "expected_contractual_return": "2400.00",
            "expected_return_above_principal": "400.00",
        },
        "cash_to_borrowers": "800.00",
        "details": [{
            "date": "2026-11-24", "time": "09:15", "branch": "Maseru",
            "client_name": "Sample Borrower", "loan_reference": "LN-SAMPLE-2026",
            "disbursed_by": "Test Officer", "principal_issued": "2000.00",
            "cash_to_borrower": "800.00", "installments": 3,
            "installment_amount": "800.00",
        }],
    }
    monkeypatch.setattr(reports, "daily_issuance_expected_returns", lambda **_kwargs: report)
    class NoDB:
        def query(self, *_args):
            raise AssertionError("No tenant lookup without company_id")
    response = reports.export_daily_issuance_pdf(
        period_start=date(2026, 11, 24),
        period_end=date(2026, 11, 24),
        db=NoDB(), context=SimpleNamespace(),
    )
    text = " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.body)).pages)
    assert "Sample Borrower" in text
    assert "LN-SAMPLE-2026" in text
    assert "800.00" in text
