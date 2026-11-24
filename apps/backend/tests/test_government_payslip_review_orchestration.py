"""Synthetic evidence aggregation tests; no real payslips or client identifiers."""
from datetime import date
from decimal import Decimal

from services.document_intelligence_foundation import (
    DocumentKind, StampStatus, assess_stamp_dates,
)
from services.document_intelligence_reader import ReadDocument, ReadPage
from services.government_payslip_stamp_evidence import StampEvidence
from services.government_payslip_review_orchestration import (
    FinancialEvidenceStatus,
    ReviewDisposition,
    assess_government_payslip_evidence,
)


TODAY = date(2026, 11, 24)
OCR = "Total Earnings: 1000.00\nTotal Deductions: 100.00\nNET PAY: 900.00"


def doc(kind=DocumentKind.GOVERNMENT_PAYSLIP, review=False):
    page = ReadPage(1, "Synthetic government payroll", 0, kind, 97.0, review)
    return ReadDocument((page,), kind, review, page.text)


def stamp(*dates):
    assessment = assess_stamp_dates(dates, assessed_at=TODAY)
    return StampEvidence(
        assessment, tuple(dates), (), 1 if dates else 0,
        True, ("stamp_authenticity_unverified",),
    )


def test_reconciled_evidence_still_requires_human_verification():
    result = assess_government_payslip_evidence(
        doc(),
        ocr_passes={"psm3": OCR, "psm6": OCR},
        itemised_earnings=[Decimal("1000.00")],
        itemised_deductions=[Decimal("100.00")],
        stamp=stamp(date(2026, 11, 23)),
    )
    assert result.financial_status == FinancialEvidenceStatus.ARITHMETIC_RECONCILED
    assert result.stamp_date_status == StampStatus.VALID_DATE
    assert result.disposition == ReviewDisposition.HUMAN_REVIEW_REQUIRED
    assert result.review_required and not result.auto_approval_allowed
    assert "issuer_authenticity_unverified" in result.review_reasons


def test_wrong_document_cannot_pass_even_with_valid_financials():
    result = assess_government_payslip_evidence(
        doc(DocumentKind.BANK_STATEMENT),
        ocr_passes={"a": OCR, "b": OCR},
        itemised_earnings=[Decimal("1000.00")],
        itemised_deductions=[Decimal("100.00")],
        stamp=stamp(date(2026, 11, 23)),
    )
    assert result.disposition == ReviewDisposition.UNUSABLE_EVIDENCE
    assert "not_recognised_as_government_payslip" in result.review_reasons


def test_missing_net_is_unusable_even_when_difference_is_900():
    broken = OCR.replace("NET PAY: 900.00", "NET PAY: unreadable")
    result = assess_government_payslip_evidence(
        doc(),
        ocr_passes={"a": broken, "b": broken},
        itemised_earnings=[Decimal("1000.00")],
        itemised_deductions=[Decimal("100.00")],
        stamp=stamp(date(2026, 11, 23)),
    )
    assert result.disposition == ReviewDisposition.UNUSABLE_EVIDENCE
    assert result.printed_net is None
    assert "net_printed_total_missing" in result.review_reasons


def test_expired_stamp_cannot_be_overridden_by_clean_arithmetic():
    result = assess_government_payslip_evidence(
        doc(),
        ocr_passes={"a": OCR, "b": OCR},
        itemised_earnings=[Decimal("1000.00")],
        itemised_deductions=[Decimal("100.00")],
        stamp=stamp(date(2026, 8, 23)),
    )
    assert result.stamp_date_status == StampStatus.EXPIRED
    assert "stamp_date_not_valid" in result.review_reasons
    assert result.review_required


def test_low_confidence_document_remains_in_review():
    result = assess_government_payslip_evidence(
        doc(review=True),
        ocr_passes={"a": OCR, "b": OCR},
        itemised_earnings=[Decimal("1000.00")],
        itemised_deductions=[Decimal("100.00")],
        stamp=stamp(date(2026, 11, 23)),
    )
    assert "document_ocr_requires_review" in result.review_reasons


def test_no_stamp_candidate_keeps_manual_review():
    result = assess_government_payslip_evidence(
        doc(),
        ocr_passes={"a": OCR, "b": OCR},
        itemised_earnings=[Decimal("1000.00")],
        itemised_deductions=[Decimal("100.00")],
        stamp=stamp(),
    )
    assert result.stamp_date_status == StampStatus.MISSING
    assert "stamp_date_not_valid" in result.review_reasons
