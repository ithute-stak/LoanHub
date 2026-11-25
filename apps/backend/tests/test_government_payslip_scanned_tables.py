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


def test_seven_deductions_are_individually_checked_against_printed_total():
    """Synthetic labels with amounts matching the seven-row scanned example."""
    text = """Deductions
0533 Sample Tax 847.41
2010 Sample Pension 441.30
2180 Sample Loan One 231.00
2230 Sample Association 20.00
2419 Sample Insurance 30.00
2670 Sample Rent 91.00
2907 Sample Loan Two 4,514.00
Total Deductions: 6,174.71
"""
    rows, total = _parse_table(text, section="deductions")
    assert len(rows) == 7
    assert total == Decimal("6174.71")
    assert sum((r.amount for r in rows), Decimal("0.00")) == total


def test_earnings_dark_heading_missing_can_be_reviewed_but_not_invented():
    sample = "| 1011 Monthly Basic Salary 8,826.00\nTotal Earnings: 8,826.00\n"
    rows, total = _parse_table(sample, section="earnings", allow_missing_heading=True)
    assert len(rows) == 1
    assert total == Decimal("8826.00")
    with pytest.raises(AmbiguousPayslipLayout):
        _parse_table(sample, section="earnings")


def test_ocr_corrupted_gross_total_fails_closed():
    damaged = "1011 Monthly Basic Salary 8,826.00\nTotal Earnings: 8,826.0C"
    with pytest.raises(AmbiguousPayslipLayout, match="printed total"):
        _parse_table(damaged, section="earnings", allow_missing_heading=True)


def test_missing_earnings_anchor_is_explicitly_flagged():
    page = Image.new("RGB", (1698, 2400))
    only_right = (OCRWord("Deductions", 95, 1019, 951, 113, 25, 2, 1, 1),)
    left_text = "1011 Monthly Basic Salary 1,000.00\nTotal Earnings: 1,000.00"
    with patch("services.government_payslip_scanned_tables._ocr_table",
               side_effect=[left_text, DEDUCTIONS]):
        result = read_scanned_payslip_financials(
            page, only_right, net_pay_candidate=Decimal("880.00"),
        )
    assert result.totals_reconciled
    assert result.review_required
    assert "earnings_heading_not_recognised" in result.review_reasons


def test_corrupted_printed_gross_can_use_matching_separate_crop():
    damaged = "1011 Monthly Basic Salary 8,826.00\nTotal Earnings: 8,826.0C"
    rows, total = _parse_table(
        damaged, section="earnings", allow_missing_heading=True,
        corroborated_total=Decimal("8826.00"),
    )
    assert len(rows) == 1
    assert total == Decimal("8826.00")


def test_gross_crop_cannot_override_legible_but_conflicting_total():
    with pytest.raises(AmbiguousPayslipLayout, match="gross crop conflicts"):
        with patch("services.government_payslip_scanned_tables._ocr_table",
                   side_effect=[EARNINGS, DEDUCTIONS]):
            read_scanned_payslip_financials(
                Image.new("RGB", (1698, 2400)), words(),
                net_pay_candidate=Decimal("880.00"),
                gross_crop_candidate=Decimal("1001.00"),
            )


def test_corrupted_gross_is_not_accepted_if_crop_disagrees_with_itemised_earnings():
    damaged = "1011 Monthly Basic Salary 8,826.00\nTotal Earnings: 8,826.0C"
    with pytest.raises(AmbiguousPayslipLayout, match="does not match"):
        _parse_table(
            damaged, section="earnings", allow_missing_heading=True,
            corroborated_total=Decimal("8825.00"),
        )
