"""Synthetic integration tests for review-only scanned payslip financial status."""
from decimal import Decimal
from unittest.mock import patch

from PIL import Image

from services.government_payslip_net_pay_preview import NetPayPreview
from services.government_payslip_scanned_tables import ScannedPayItem, ScannedPayslipFinancials
from services.government_payslip_spatial_layout import AmbiguousPayslipLayout
from services.government_payslip_financial_preview import preview_scanned_payslip_financials


def net(value="880.00"):
    return NetPayPreview(Decimal(value) if value is not None else None,
                         "candidate_only" if value is not None else "manual_review",
                         True, ("printed_amount_crop_requires_reviewer_confirmation",))


def scanned(reconciled=True):
    return ScannedPayslipFinancials(
        (ScannedPayItem("1011", "Salary", Decimal("1000.00")),),
        (ScannedPayItem("0533", "Tax", Decimal("120.00")),),
        Decimal("1000.00"), Decimal("120.00"), Decimal("880.00"),
        reconciled, True, ("issuer_and_original_document_unverified",),
    )


def test_complete_arithmetic_is_reported_only_as_candidate_for_review():
    with patch("services.government_payslip_financial_preview.preview_net_pay_amount", return_value=net()):
        with patch("services.government_payslip_financial_preview._single_image",
                   return_value=Image.new("RGB", (900, 1000))):
            with patch("services.government_payslip_financial_preview.spatial_ocr", return_value=()):
                with patch("services.government_payslip_financial_preview.read_scanned_payslip_financials",
                           return_value=scanned()):
                    result = preview_scanned_payslip_financials(b"test", "scan.png")
    assert result.status == "arithmetic_reconciled_review_required"
    assert result.review_required
    assert result.printed_gross_candidate == Decimal("1000.00")
    assert result.deduction_rows == 1


def test_unreadable_table_does_not_turn_net_candidate_into_verified_payslip():
    with patch("services.government_payslip_financial_preview.preview_net_pay_amount", return_value=net()):
        with patch("services.government_payslip_financial_preview._single_image",
                   return_value=Image.new("RGB", (900, 1000))):
            with patch("services.government_payslip_financial_preview.spatial_ocr", return_value=()):
                with patch("services.government_payslip_financial_preview.read_scanned_payslip_financials",
                           side_effect=AmbiguousPayslipLayout("bad row")):
                    result = preview_scanned_payslip_financials(b"test", "scan.png")
    assert result.status == "manual_review"
    assert result.net_pay_candidate == Decimal("880.00")
    assert result.printed_gross_candidate is None
    assert "financial_table_unreadable_or_ambiguous" in result.review_reasons


def test_native_text_pdf_no_spatial_image_needs_manual_review():
    with patch("services.government_payslip_financial_preview.preview_net_pay_amount", return_value=net(None)):
        with patch("services.government_payslip_financial_preview._single_image", return_value=None):
            result = preview_scanned_payslip_financials(b"test", "scan.pdf")
    assert result.status == "manual_review"
    assert result.earnings_rows is None


def test_inconsistent_total_remains_manual_review_even_if_rows_read():
    with patch("services.government_payslip_financial_preview.preview_net_pay_amount", return_value=net()):
        with patch("services.government_payslip_financial_preview._single_image",
                   return_value=Image.new("RGB", (900, 1000))):
            with patch("services.government_payslip_financial_preview.spatial_ocr", return_value=()):
                with patch("services.government_payslip_financial_preview.read_scanned_payslip_financials",
                           return_value=scanned(False)):
                    result = preview_scanned_payslip_financials(b"test", "scan.png")
    assert result.status == "manual_review"
    assert result.review_required



def test_gross_crop_candidate_is_passed_to_table_reconciliation():
    from services.government_payslip_amount_crop import AmountCropEvidence
    from services.government_payslip_amount_locator import LocatedAmountCell

    with patch("services.government_payslip_financial_preview.preview_net_pay_amount", return_value=net()):
        with patch("services.government_payslip_financial_preview._single_image",
                   return_value=Image.new("RGB", (900, 1000))):
            with patch("services.government_payslip_financial_preview.spatial_ocr", return_value=()):
                with patch("services.government_payslip_financial_preview.locate_dark_bar_gross_cell",
                           return_value=LocatedAmountCell("gross_dark_bar_candidate", (200, 400, 330, 440))):
                    with patch("services.government_payslip_financial_preview.read_amount_crop",
                               return_value=AmountCropEvidence(
                                   Decimal("1000.00"), ("1,000.00", "1,000.00"),
                                   True, True, ("printed_amount_crop_requires_reviewer_confirmation",),
                               )):
                        with patch(
                            "services.government_payslip_financial_preview.read_scanned_payslip_financials",
                            return_value=scanned(),
                        ) as table:
                            result = preview_scanned_payslip_financials(b"test", "scan.png")
    assert table.call_args.kwargs["gross_crop_candidate"] == Decimal("1000.00")
    assert result.status == "arithmetic_reconciled_review_required"
    assert result.review_required
