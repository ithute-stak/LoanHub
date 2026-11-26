"""Read-only assessment assembly for LoanHub government payslip evidence.

The caller must perform authenticated uploads and tenant checks separately.
This service never registers clients, changes loans or declares issuer authenticity.
OCR readings, financial arithmetic and stamp-date evidence remain separate, so
a passing check cannot silently override a failed or missing one.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Mapping, Sequence

from services.document_intelligence_foundation import DocumentKind, StampStatus
from services.document_intelligence_reader import ReadDocument
from services.government_payslip_ocr_acceptance import (
    PayslipAcceptance,
    assess_payslip_ocr_totals,
)
from services.government_payslip_stamp_evidence import StampEvidence


class FinancialEvidenceStatus(str, Enum):
    ARITHMETIC_RECONCILED = "arithmetic_reconciled"
    REVIEW_REQUIRED = "review_required"


class ReviewDisposition(str, Enum):
    HUMAN_REVIEW_REQUIRED = "human_review_required"
    UNUSABLE_EVIDENCE = "unusable_evidence"


@dataclass(frozen=True)
class PayslipDocumentAssessment:
    document_type: DocumentKind
    page_count: int
    financial_status: FinancialEvidenceStatus
    printed_gross: Decimal | None
    printed_deductions: Decimal | None
    printed_net: Decimal | None
    stamp_date_status: StampStatus
    stamp_date: date | None
    disposition: ReviewDisposition
    review_required: bool
    auto_approval_allowed: bool
    review_reasons: tuple[str, ...]


def assemble_government_payslip_assessment(
    document: ReadDocument,
    financial: PayslipAcceptance,
    stamp: StampEvidence,
) -> PayslipDocumentAssessment:
    """Combine independently obtained evidence into one fail-closed review result.

    Financial acceptance only means printed totals and itemised arithmetic
    corroborate. A recent stamp only passes the date policy. Neither is
    sufficient to verify the document's origin or approve a loan.
    """
    if not document.pages:
        raise ValueError("document must have at least one page")
    reasons: list[str] = []
    kind = document.classification
    if kind != DocumentKind.GOVERNMENT_PAYSLIP:
        reasons.append("not_recognised_as_government_payslip")
    if document.review_required or any(p.review_required for p in document.pages):
        reasons.append("document_ocr_requires_review")
    if any(p.classification not in (DocumentKind.GOVERNMENT_PAYSLIP, DocumentKind.UNKNOWN) for p in document.pages):
        reasons.append("mixed_document_types")
    if not financial.accepted_financial_totals:
        reasons.append("financial_evidence_incomplete")
    reasons.extend(financial.review_reasons)
    if stamp.assessment.status != StampStatus.VALID_DATE:
        reasons.append("stamp_date_not_valid")
    reasons.extend(stamp.review_reasons)
    if stamp.requires_manual_review:
        reasons.append("stamp_authenticity_manual_review")
    if any(value is None for value in (financial.printed_gross, financial.printed_deductions, financial.printed_net)):
        reasons.append("printed_financial_totals_missing")

    unusable = kind != DocumentKind.GOVERNMENT_PAYSLIP or not financial.accepted_financial_totals
    return PayslipDocumentAssessment(
        document_type=kind,
        page_count=len(document.pages),
        financial_status=(
            FinancialEvidenceStatus.ARITHMETIC_RECONCILED
            if financial.accepted_financial_totals
            else FinancialEvidenceStatus.REVIEW_REQUIRED
        ),
        printed_gross=financial.printed_gross,
        printed_deductions=financial.printed_deductions,
        printed_net=financial.printed_net,
        stamp_date_status=stamp.assessment.status,
        stamp_date=stamp.assessment.stamp_date,
        disposition=(
            ReviewDisposition.UNUSABLE_EVIDENCE
            if unusable else ReviewDisposition.HUMAN_REVIEW_REQUIRED
        ),
        review_required=True,
        auto_approval_allowed=False,
        review_reasons=tuple(dict.fromkeys(reasons + ["issuer_authenticity_unverified"])),
    )


def assess_government_payslip_evidence(
    document: ReadDocument,
    *,
    ocr_passes: Mapping[str, str],
    stamp: StampEvidence,
    itemised_earnings: Sequence[Decimal] | None = None,
    itemised_deductions: Sequence[Decimal] | None = None,
) -> PayslipDocumentAssessment:
    """Compose multi-pass financial OCR evaluation and stamp evidence.

    Raw image/PDF OCR and locating the stamp are upstream tasks. No stamp date
    may be derived from the payroll period, DOB, or other non-stamp regions.
    """
    financial = assess_payslip_ocr_totals(
        ocr_passes,
        itemised_earnings=itemised_earnings,
        itemised_deductions=itemised_deductions,
    )
    return assemble_government_payslip_assessment(document, financial, stamp)
