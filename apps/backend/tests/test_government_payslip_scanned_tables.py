"""Payroll table tests use synthetic salary and deduction rows only."""
from decimal import Decimal
from unittest.mock import patch

import pytest
from PIL import Image

from services.document_spatial_ocr import OCRWord
from services.government_payslip_spatial_layout import AmbiguousPayslipLayout
from services.government_payslip_scanned_tables import (
    _parse_table, read_scanned_payslip_financials,
)

EARNINGS = """Earnings
1011 Monthly Basic Salary 1,000.00
Total Earnings: 1,000.00
"""
DEDUCTIONS = """Deductions
0533 PAYE 100.00
2010 Pension Contribution 20.00
Total Deductions: 120.00
"""


def words():
    return (
        OCRWord("Earnings", 96, 220, 910, 110, 24, 1, 1, 1),
        OCRWord("Deductions", 96, 995, 910, 130, 24, 2, 1, 1),
    )


def test_reconciles_two_independently_cropped_financial_tables():
    image = Image.new("RGB", (1698, 2400))
    with patch("services.government_payslip_scanned_tables._ocr_table",
               side_effect=[EARNINGS, DEDUCTIONS]) as reader:
        result = read_scanned_payslip_financials(
            image, words(), net_pay_candidate=Decimal("880.00"),
        )
    assert reader.call_count == 2
    assert len(result.earnings) == 1
    assert len(result.deductions) == 2
    assert result.totals_reconciled
    assert result.review_required
    assert "issuer_and_original_document_unverified" in result.review_reasons


def test_missing_net_pay_is_never_calculated_in_place_of_printed_value():
    with patch("services.government_payslip_scanned_tables._ocr_table",
               side_effect=[EARNINGS, DEDUCTIONS]):
        result = read_scanned_payslip_financials(
            Image.new("RGB", (1698, 2400)), words(),
        )
    assert result.printed_net_candidate is None
    assert not result.totals_reconciled
    assert "printed_net_pay_unconfirmed" in result.review_reasons


def test_mismatched_net_pay_requires_review():
    with patch("services.government_payslip_scanned_tables._ocr_table",
               side_effect=[EARNINGS, DEDUCTIONS]):
        result = read_scanned_payslip_financials(
            Image.new("RGB", (1698, 2400)), words(),
            net_pay_candidate=Decimal("881.00"),
        )
    assert not result.totals_reconciled
    assert "printed_net_pay_does_not_reconcile" in result.review_reasons


def test_missing_deduction_is_detected_by_printed_total():
    damaged = DEDUCTIONS.replace("2010 Pension Contribution 20.00\n", "")
    with pytest.raises(AmbiguousPayslipLayout, match="does not match"):
        _parse_table(damaged, section="deductions")


def test_unreadable_payroll_row_not_silently_ignored():
    damaged = DEDUCTIONS.replace("2010 Pension Contribution 20.00", "2010 Pension Contribution unreadable")
    with pytest.raises(AmbiguousPayslipLayout, match="unrecognised"):
        _parse_table(damaged, section="deductions")


def test_duplicate_codes_rejected_even_if_totals_reconcile():
    text = DEDUCTIONS.replace("2010 Pension Contribution 20.00", "0533 Pension Contribution 20.00")
    with pytest.raises(AmbiguousPayslipLayout, match="duplicate"):
        _parse_table(text, section="deductions")


def test_duplicate_or_missing_headings_fail_closed():
    with pytest.raises(AmbiguousPayslipLayout, match="heading"):
        read_scanned_payslip_financials(Image.new("RGB", (1698, 2400)), words()[:1])
