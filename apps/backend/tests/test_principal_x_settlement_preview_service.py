from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from services.principal_x_settlement_preview_service import quote_principal_x_for_loan


def make_loan():
    rows = [
        SimpleNamespace(installment_number=i, due_date=d, total_due=Decimal("464"), is_superseded=False)
        for i, d in enumerate(
            [date(2026, 11, 30), date(2026, 12, 31), date(2027, 1, 31)], 1
        )
    ]
    return SimpleNamespace(
        id="loan-1", company_id="company-1", origination_channel="marketplace",
        renewal_cycle_count=0, disbursed_at=datetime(2026, 11, 1),
        installments=rows, repayment_period=3, total_repayable=Decimal("1392"),
        principal_amount=Decimal("1000"), interest_rate=Decimal("20"),
        amount_paid=Decimal("464"),
    )


def mock_db(payments):
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.all.return_value = payments
    return db


def test_persisted_loan_and_succeeded_payment():
    loan = make_loan()
    payment = SimpleNamespace(amount=Decimal("464"), completed_at=datetime(2026, 11, 30))
    result = quote_principal_x_for_loan(
        mock_db([payment]), loan=loan, settlement_date=date(2026, 12, 15)
    )
    assert result.collectible_due == Decimal("883.20")


def test_fail_closed_when_ledger_disagrees():
    loan = make_loan()
    with pytest.raises(ValueError, match="does not reconcile"):
        quote_principal_x_for_loan(
            mock_db([]), loan=loan, settlement_date=date(2026, 12, 15)
        )


def test_fail_closed_for_legacy_and_renewals():
    loan = make_loan()
    loan.origination_channel = "legacy_cashout"
    with pytest.raises(ValueError, match="Legacy"):
        quote_principal_x_for_loan(
            mock_db([]), loan=loan, settlement_date=date(2026, 12, 15)
        )
    loan.origination_channel = "marketplace"
    loan.renewal_cycle_count = 1
    with pytest.raises(ValueError, match="Renewed"):
        quote_principal_x_for_loan(
            mock_db([]), loan=loan, settlement_date=date(2026, 12, 15)
        )
