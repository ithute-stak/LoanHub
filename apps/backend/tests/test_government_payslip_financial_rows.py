"""Financial row reconstruction tests, using no customer data."""
from decimal import Decimal

import pytest

from services.document_spatial_ocr import OCRWord
from services.government_payslip_financial_rows import reconstruct_payslip_financials
from services.government_payslip_spatial_layout import (
    AmbiguousPayslipLayout,
    separate_financial_columns,
)


def word(text, x, y, block, *, conf=95.0):
    return OCRWord(text, conf, x, y, max(12, len(text) * 9), 18, block, 1, 1)


def layout(*, deduction_amount="100.00", low_conf=False):
    parts = [
        word("Earnings", 40, 50, 1),
        word("Deductions", 550, 50, 2),
        word("Basic", 40, 105, 3), word("Salary", 105, 105, 4),
        word("1000.00", 280, 105, 5),
        word("PAYE", 550, 105, 6),
        word(deduction_amount, 770, 105, 7, conf=25 if low_conf else 95),
        word("Total", 40, 145, 8), word("Earnings", 115, 145, 9),
        word("1000.00", 280, 145, 10),
        word("Total", 550, 145, 11), word("Deductions", 615, 145, 12),
        word("100.00", 770, 145, 13),
    ]
    return separate_financial_columns(parts, page_width=1000)


def test_reconstructs_and_reconciles_payslip_columns():
    result = reconstruct_payslip_financials(layout(), printed_net="900.00")
    assert result.reconciled
    assert result.calculated_net == Decimal("900.00")
    assert result.earnings[0].label == "Basic Salary"
    assert result.deductions[0].label == "PAYE"
    assert result.review_required
    assert "issuer_identity_and_stamp_require_verification" in result.review_reasons


def test_financial_totals_mismatch_is_not_accepted():
    result = reconstruct_payslip_financials(layout(deduction_amount="99.00"), printed_net="900.00")
    assert not result.reconciled
    assert "financial_totals_mismatch" in result.review_reasons


def test_missing_independent_net_must_fail():
    with pytest.raises(AmbiguousPayslipLayout, match="printed gross"):
        reconstruct_payslip_financials(layout())


def test_low_confidence_financial_line_is_flagged():
    result = reconstruct_payslip_financials(layout(low_conf=True), printed_net="900.00")
    assert "low_confidence_financial_row" in result.review_reasons


def test_unpaired_amount_must_fail():
    cols = layout()
    from services.document_spatial_ocr import OCRLine
    unexpected = word("20.00", 350, 185, 19)
    extra_line = OCRLine("20.00", (unexpected,), 350, 185, unexpected.right, unexpected.bottom)
    from dataclasses import replace
    with pytest.raises(AmbiguousPayslipLayout, match="missing or has multiple amounts"):
        reconstruct_payslip_financials(
            replace(cols, earnings=cols.earnings + (extra_line,)), printed_net="900.00"
        )


def test_multiple_amounts_in_single_row_must_fail():
    from dataclasses import replace
    from services.document_spatial_ocr import OCRLine
    cols = layout()
    extra = word("55.00", 350, 105, 19)
    extra_line = OCRLine("55.00", (extra,), 350, 105, extra.right, extra.bottom)
    with pytest.raises(AmbiguousPayslipLayout, match="multiple amounts"):
        reconstruct_payslip_financials(
            replace(cols, earnings=cols.earnings + (extra_line,)), printed_net="900.00"
        )
