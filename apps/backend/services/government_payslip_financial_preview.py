"""Review-only integration of scanned staff payslip tables and net-pay crop.

The service never writes financial data, trusts a calculated net as a printed
value, or returns employee identity data. Every accepted arithmetic result
still requires operator and issuer verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from PIL import Image, ImageOps

from services.document_intelligence_reader import DocumentReadError, _pdf_pages, _safe_image
from services.document_spatial_ocr import spatial_ocr
from services.government_payslip_net_pay_preview import preview_net_pay_amount
from services.government_payslip_dark_bar_locator import locate_dark_bar_gross_cell
from services.government_payslip_amount_locator import AmountCellLocationError
from services.government_payslip_amount_crop import read_amount_crop
from services.government_payslip_scanned_tables import read_scanned_payslip_financials
from services.government_payslip_spatial_layout import AmbiguousPayslipLayout


@dataclass(frozen=True)
class FinancialPreview:
    status: str
    printed_gross_candidate: Decimal | None
    printed_deductions_candidate: Decimal | None
    net_pay_candidate: Decimal | None
    earnings_rows: int | None
    deduction_rows: int | None
    review_required: bool
    review_reasons: tuple[str, ...]


def _single_image(contents: bytes, filename: str) -> Image.Image | None:
    if filename.lower().endswith(".pdf"):
        pages = _pdf_pages(contents)
        if len(pages) != 1 or pages[0][0] != "image":
            return None
        return pages[0][1]
    return _safe_image(contents)


def preview_scanned_payslip_financials(contents: bytes, filename: str) -> FinancialPreview:
    """Expose financial arithmetic only after all source rows reconcile.

    A missing or failed scan section leaves the entire financial result
    unverified, even if a separate OCR path found the net salary.
    """
    net = preview_net_pay_amount(contents, filename)
    reasons = list(net.review_reasons)
    image = _single_image(contents, filename)
    if image is None:
        return FinancialPreview(
            "manual_review", None, None, net.candidate, None, None, True,
            tuple(dict.fromkeys(reasons + ["scanned_financial_table_unavailable"])),
        )
    try:
        words = spatial_ocr(image)
        # A second contrast pass is only used to locate headings, not as
        # additional independent evidence that the financial values are true.
        words_inverted = spatial_ocr(ImageOps.invert(image.convert("RGB")))
        gross_candidate = None
        try:
            gross_box = locate_dark_bar_gross_cell(
                image, (*words, *words_inverted),
            )
            gross_evidence = read_amount_crop(image, gross_box.box)
            gross_candidate = gross_evidence.candidate
            reasons.extend(gross_evidence.review_reasons)
        except (AmountCellLocationError, DocumentReadError, ValueError):
            reasons.append("gross_total_crop_not_reliably_located_or_read")
        scanned = read_scanned_payslip_financials(
            image, (*words, *words_inverted),
            net_pay_candidate=net.candidate,
            gross_crop_candidate=gross_candidate,
        )
    except (DocumentReadError, AmbiguousPayslipLayout, ValueError):
        return FinancialPreview(
            "manual_review", None, None, net.candidate, None, None, True,
            tuple(dict.fromkeys(reasons + ["financial_table_unreadable_or_ambiguous"])),
        )
    reasons.extend(scanned.review_reasons)
    return FinancialPreview(
        "arithmetic_reconciled_review_required"
        if scanned.totals_reconciled else "manual_review",
        scanned.printed_gross, scanned.printed_deductions,
        scanned.printed_net_candidate, len(scanned.earnings),
        len(scanned.deductions), True, tuple(dict.fromkeys(reasons)),
    )
