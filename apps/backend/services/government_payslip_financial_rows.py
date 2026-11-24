"""Reconstruct payslip financial rows from *spatially separated* OCR columns.

Does not authenticate a payslip, infer missing values, or trigger lending actions.
Every numeric row must be paired with a label, and ambiguous geometry fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Sequence

from services.document_spatial_ocr import OCRLine, OCRWord
from services.government_payslip_adapter import PayslipEntry
from services.government_payslip_spatial_layout import PayslipColumns, AmbiguousPayslipLayout
from services.document_intelligence_foundation import money, validate_payslip_totals

_AMOUNT = re.compile(r"^(?:M|LSL)?\s*([0-9][0-9,]*\.[0-9]{2})$", re.I)
_NUMBER = re.compile(r"\d")
_TOTAL_NAMES = {
    "total earnings": "gross",
    "gross earnings": "gross",
    "gross pay": "gross",
    "total deductions": "deductions",
    "net pay": "net",
    "net salary": "net",
}
_SKIP_NAMES = {"earnings", "deductions"}


@dataclass(frozen=True)
class FinancialRow:
    label: str
    amount: Decimal
    top: int
    confidence: float


@dataclass(frozen=True)
class SpatialFinancialAssessment:
    earnings: tuple[PayslipEntry, ...]
    deductions: tuple[PayslipEntry, ...]
    printed_gross: Decimal
    printed_deductions: Decimal
    printed_net: Decimal
    calculated_net: Decimal
    reconciled: bool
    review_required: bool
    review_reasons: tuple[str, ...]


def _normal(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip().lower().rstrip(":"))


def _rows(lines: Sequence[OCRLine], *, max_vertical_gap: int = 18) -> tuple[FinancialRow, ...]:
    """Cluster independently segmented OCR lines into physical rows.

    Fails closed if OCR yields multiple amounts, an amount with no description,
    or an illegible numeric token. Callers must pass one column only.
    """
    if max_vertical_gap < 0:
        raise ValueError("invalid row gap")
    words = sorted((word for line in lines for word in line.words), key=lambda w: (w.top, w.left))
    bands: list[list[OCRWord]] = []
    for word in words:
        matched: list[OCRWord] | None = None
        for band in reversed(bands):
            # Nearby baselines; do not merge successive rows just because
            # their text boxes overlap vertically by a few pixels.
            if abs(word.top - min(x.top for x in band)) <= max_vertical_gap:
                matched = band
                break
            if word.top - min(x.top for x in band) > max_vertical_gap:
                break
        if matched is None:
            bands.append([word])
        else:
            matched.append(word)
    result: list[FinancialRow] = []
    for band in bands:
        band.sort(key=lambda w: w.left)
        tokens = [x.text.strip() for x in band if x.text.strip()]
        if not tokens:
            continue
        candidate_amounts = [(idx, match.group(1)) for idx, token in enumerate(tokens)
                             if (match := _AMOUNT.fullmatch(token))]
        if len(candidate_amounts) != 1:
            raise AmbiguousPayslipLayout("financial row missing or has multiple amounts")
        idx, amount = candidate_amounts[0]
        if idx != len(tokens) - 1 or idx == 0:
            raise AmbiguousPayslipLayout("unpaired amount or text after amount")
        label_tokens = tokens[:idx]
        if any(_NUMBER.search(token) for token in label_tokens):
            raise AmbiguousPayslipLayout("unrecognised number in financial label")
        label = " ".join(label_tokens).strip()
        if not re.search(r"[A-Za-z]", label):
            raise AmbiguousPayslipLayout("missing financial description")
        if _normal(label) in _SKIP_NAMES:
            continue
        result.append(FinancialRow(
            label=label,
            amount=money(amount),
            top=min(x.top for x in band),
            confidence=min(x.confidence for x in band),
        ))
    return tuple(result)


def reconstruct_payslip_financials(
    columns: PayslipColumns, *, printed_net: str | Decimal | None = None,
    min_confidence: float = 70.0,
) -> SpatialFinancialAssessment:
    """Require independently OCR-recognised totals; never infer a printed net.

    An external page-layout stage must identify the printed net pay region and
    pass its amount explicitly. Stamp verification remains a separate workflow.
    """
    if not 0 <= min_confidence <= 100:
        raise ValueError("invalid confidence threshold")
    earning_rows = _rows(columns.earnings)
    deduction_rows = _rows(columns.deductions)
    totals: dict[str, Decimal] = {}
    entries: dict[str, list[PayslipEntry]] = {"earnings": [], "deductions": []}
    for name, rows in (("earnings", earning_rows), ("deductions", deduction_rows)):
        for row in rows:
            key = _TOTAL_NAMES.get(_normal(row.label))
            if key is not None:
                if key in totals:
                    raise AmbiguousPayslipLayout("duplicate printed financial total")
                totals[key] = row.amount
            else:
                entries[name].append(PayslipEntry(row.label, row.amount))
    if not entries["earnings"] or not entries["deductions"]:
        raise AmbiguousPayslipLayout("missing earnings or deduction entries")
    if "gross" not in totals or "deductions" not in totals or printed_net is None:
        raise AmbiguousPayslipLayout("printed gross, deductions and net totals required")
    totals["net"] = money(printed_net)
    checked = validate_payslip_totals(
        [row.amount for row in entries["earnings"]],
        [row.amount for row in entries["deductions"]],
        printed_earnings=totals["gross"],
        printed_deductions=totals["deductions"],
        printed_net_pay=totals["net"],
    )
    reasons = list(columns.review_reasons)
    if min((row.confidence for row in (*earning_rows, *deduction_rows))) < min_confidence:
        reasons.append("low_confidence_financial_row")
    if not checked.is_reconciled:
        reasons.append("financial_totals_mismatch")
    # Arithmetic is not proof of issuance, identity or acceptable stamp date.
    reasons.append("issuer_identity_and_stamp_require_verification")
    return SpatialFinancialAssessment(
        tuple(entries["earnings"]), tuple(entries["deductions"]),
        totals["gross"], totals["deductions"], totals["net"],
        checked.net_pay, checked.is_reconciled, True, tuple(dict.fromkeys(reasons)),
    )
