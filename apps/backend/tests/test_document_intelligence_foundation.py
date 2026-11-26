from datetime import date
from decimal import Decimal

import pytest

from services.document_intelligence_foundation import (
    BankTransaction,
    DocumentKind,
    StampStatus,
    assess_stamp_dates,
    classify_document,
    orientation_candidates,
    subtract_calendar_months,
    validate_payslip_totals,
    validate_statement_balances,
    money,
)


def test_orientation_candidates_include_all_quarter_turns():
    assert orientation_candidates() == (0, 90, 180, 270)


def test_document_classification_is_conservative():
    assert classify_document("Staff Payslip Net Pay Deductions") == DocumentKind.GOVERNMENT_PAYSLIP
    assert classify_document("Opening Balance Closing Balance Debit Credit") == DocumentKind.BANK_STATEMENT
    assert classify_document("a random letter") == DocumentKind.UNKNOWN


@pytest.mark.parametrize(
    ("stamp_date", "status"),
    [
        (date(2026, 8, 23), StampStatus.EXPIRED),
        (date(2026, 8, 24), StampStatus.VALID_DATE),
        (date(2026, 11, 24), StampStatus.VALID_DATE),
        (date(2026, 11, 25), StampStatus.FUTURE_DATE),
    ],
)
def test_three_calendar_month_stamp_policy(stamp_date, status):
    assert assess_stamp_dates([stamp_date], assessed_at=date(2026, 11, 24)).status == status


def test_missing_or_conflicting_stamp_requires_review():
    assert assess_stamp_dates([], assessed_at=date(2026, 11, 24)).status == StampStatus.MISSING
    result = assess_stamp_dates([date(2026, 10, 1), date(2026, 11, 1)], assessed_at=date(2026, 11, 24))
    assert result.status == StampStatus.AMBIGUOUS


def test_calendar_month_clamping():
    assert subtract_calendar_months(date(2026, 5, 31), 3) == date(2026, 2, 28)


def test_sample_government_payslip_reconciles():
    values = ["847.41", "441.30", "231.00", "20.00", "30.00", "91.00", "4514.00"]
    result = validate_payslip_totals(
        ["8826.00"], values,
        printed_earnings="8826.00", printed_deductions="6174.71", printed_net_pay="2651.29",
    )
    assert result.is_reconciled
    assert result.net_pay == Decimal("2651.29")


def test_payslip_mismatch_rejected():
    result = validate_payslip_totals(
        ["1000.00"], ["100.00"],
        printed_earnings="1000.00", printed_deductions="100.00", printed_net_pay="901.00",
    )
    assert not result.is_reconciled


def test_balance_chain_checks_every_transaction():
    rows = [
        BankTransaction(Decimal("10.00"), Decimal("0.00"), Decimal("90.00")),
        BankTransaction(Decimal("0.00"), Decimal("50.00"), Decimal("140.00")),
    ]
    assert validate_statement_balances("100.00", "140.00", rows)
    assert not validate_statement_balances("100.00", "140.00", [
        rows[0], BankTransaction(Decimal("0.00"), Decimal("50.00"), Decimal("139.00"))
    ])


@pytest.mark.parametrize("invalid", ["NaN", "-1.00", "1.234", "Infinity"])
def test_invalid_money_is_rejected(invalid):
    with pytest.raises(ValueError):
        money(invalid)
