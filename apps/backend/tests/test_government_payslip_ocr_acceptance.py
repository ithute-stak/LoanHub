"""OCR acceptance checks use synthetic amounts, not personal payslip content."""
from decimal import Decimal

import pytest

from services.government_payslip_ocr_acceptance import assess_payslip_ocr_totals


GOOD = (
    "Total Earnings: 1000.00\n"
    "Total Deductions: 100.00\n"
    "NET PAY: 900.00"
)


def test_two_independent_passes_and_itemised_values_reconcile():
    result = assess_payslip_ocr_totals(
        {"psm3": GOOD, "psm4": GOOD},
        itemised_earnings=[Decimal("1000.00")],
        itemised_deductions=[Decimal("60.00"), Decimal("40.00")],
    )
    assert result.accepted_financial_totals
    assert result.printed_net == Decimal("900.00")


def test_misread_net_pay_requires_manual_review():
    result = assess_payslip_ocr_totals(
        {"psm3": GOOD, "psm4": GOOD.replace("900.00", "90.00")},
        itemised_earnings=[Decimal("1000.00")],
        itemised_deductions=[Decimal("100.00")],
    )
    assert not result.accepted_financial_totals
    assert "net_printed_total_conflicting" in result.review_reasons


def test_unreadable_net_pay_cannot_be_inferred_from_difference():
    text = GOOD.replace("NET PAY: 900.00", "NET PAY: unreadable")
    result = assess_payslip_ocr_totals(
        {"psm3": text, "psm4": text},
        itemised_earnings=[Decimal("1000.00")],
        itemised_deductions=[Decimal("100.00")],
    )
    assert not result.accepted_financial_totals
    assert result.printed_net is None
    assert "net_printed_total_missing" in result.review_reasons


def test_one_pass_is_not_sufficient_even_when_arithmetic_looks_correct():
    result = assess_payslip_ocr_totals(
        {"psm3": GOOD, "psm4": ""},
        itemised_earnings=[Decimal("1000.00")],
        itemised_deductions=[Decimal("100.00")],
    )
    assert not result.accepted_financial_totals
    assert "gross_printed_total_unconfirmed" in result.review_reasons


def test_missing_itemised_rows_are_not_assumed():
    result = assess_payslip_ocr_totals({"psm3": GOOD, "psm4": GOOD})
    assert not result.accepted_financial_totals
    assert "itemised_financial_rows_unverified" in result.review_reasons


def test_arithmetic_mismatch_is_rejected():
    result = assess_payslip_ocr_totals(
        {"psm3": GOOD, "psm4": GOOD},
        itemised_earnings=[Decimal("1000.00")],
        itemised_deductions=[Decimal("99.00")],
    )
    assert not result.accepted_financial_totals
    assert "financial_totals_mismatch" in result.review_reasons


def test_requires_multiple_passes_policy():
    with pytest.raises(ValueError):
        assess_payslip_ocr_totals({"psm3": GOOD}, minimum_independent_passes=1)
