"""Fail-closed acceptance gate for multi-pass government payslip OCR.

OCR modes can disagree. Numeric totals are only candidates until both
printed values and itemised earnings/deductions reconcile independently.
No personal data is logged and this module cannot approve a loan or document.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re
from typing import Mapping, Sequence

from services.document_intelligence_foundation import money, validate_payslip_totals

_AMOUNT = r"(?P<amount>[0-9][0-9,]*\.[0-9]{2})"
_TOTALS = {
    "gross": re.compile(r"\bTotal\s+Earnings\s*:\s*" + _AMOUNT, re.I),
    "deductions": re.compile(r"\bTotal\s+Deductions\s*:\s*" + _AMOUNT, re.I),
    "net": re.compile(r"\bNET\s+PAY\s*:\s*" + _AMOUNT, re.I),
}


@dataclass(frozen=True)
class PayslipAcceptance:
    accepted_financial_totals: bool
    printed_gross: Decimal | None
    printed_deductions: Decimal | None
    printed_net: Decimal | None
    review_reasons: tuple[str, ...]


def _candidates(texts: Sequence[str], pattern: re.Pattern[str]) -> set[Decimal]:
    matches: set[Decimal] = set()
    for text in texts:
        for found in pattern.finditer(text):
            matches.add(money(found.group("amount")))
    return matches


def assess_payslip_ocr_totals(
    ocr_passes: Mapping[str, str], *,
    itemised_earnings: Sequence[Decimal] | None = None,
    itemised_deductions: Sequence[Decimal] | None = None,
    minimum_independent_passes: int = 2,
) -> PayslipAcceptance:
    """Never substitute derived net pay for an unreadable printed net.

    OCR of totals can mistakenly read '651.29' for '2,651.29'. A missing,
    conflicting or insufficiently corroborated total requires human review.
    Supplying itemised amounts is necessary for acceptance.
    """
    if not ocr_passes or minimum_independent_passes < 2:
        raise ValueError("at least two OCR passes are required")
    reasons: list[str] = []
    resolved: dict[str, Decimal | None] = {}
    for label, pattern in _TOTALS.items():
        hits = _candidates(tuple(ocr_passes.values()), pattern)
        corroboration = sum(bool(pattern.search(text)) for text in ocr_passes.values())
        if not hits:
            reasons.append(label + "_printed_total_missing")
            resolved[label] = None
        elif len(hits) > 1:
            reasons.append(label + "_printed_total_conflicting")
            resolved[label] = None
        elif corroboration < minimum_independent_passes:
            reasons.append(label + "_printed_total_unconfirmed")
            resolved[label] = next(iter(hits))
        else:
            resolved[label] = next(iter(hits))
    if itemised_earnings is None or itemised_deductions is None:
        reasons.append("itemised_financial_rows_unverified")
    elif any(resolved[value] is None for value in ("gross", "deductions", "net")):
        reasons.append("financial_reconciliation_blocked")
    else:
        checked = validate_payslip_totals(
            itemised_earnings, itemised_deductions,
            printed_earnings=resolved["gross"],
            printed_deductions=resolved["deductions"],
            printed_net_pay=resolved["net"],
        )
        if not checked.is_reconciled:
            reasons.append("financial_totals_mismatch")
    return PayslipAcceptance(
        not reasons,
        resolved["gross"], resolved["deductions"], resolved["net"],
        tuple(dict.fromkeys(reasons)),
    )
