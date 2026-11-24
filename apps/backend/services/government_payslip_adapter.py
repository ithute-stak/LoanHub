"""Conservative structured reader for Lesotho government payslip OCR text.

This adapter only accepts line-preserving, explicitly labelled input. It does
not assert the origin or authenticity of a payslip, and it never determines
loan eligibility. Dates attributed to official stamps must be detected by a
separate stamp-region extractor, not by searching dates globally.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re
from typing import Sequence

from services.document_intelligence_foundation import (
    StampAssessment,
    assess_stamp_dates,
    money,
    validate_payslip_totals,
)

AMOUNT = r"([0-9][0-9,]*\.[0-9]{2})"
LINE_ITEM = re.compile(rf"^\s*(?P<label>[A-Za-z][A-Za-z /().&-]*?)\s{{2,}}(?P<amount>{AMOUNT})\s*$")
FIELD_SEPARATOR = re.compile(r"\s{2,}")
LABELS = {
    "staff no": "employee_number",
    "staff number": "employee_number",
    "employee no": "employee_number",
    "employee number": "employee_number",
    "employee reference": "employee_reference",
    "employee name": "employee_name",
    "staff name": "employee_name",
    "ministry": "ministry",
    "department": "department",
    "designation": "job_title",
    "job title": "job_title",
    "position": "job_title",
}
TOTAL_LABELS = {
    "total earnings": "gross",
    "gross earnings": "gross",
    "gross pay": "gross",
    "total deductions": "deductions",
    "net pay": "net",
    "net salary": "net",
}
EARNINGS_HEADERS = {"earnings", "allowances"}
DEDUCTIONS_HEADERS = {"deductions"}
ENDING_HEADERS = {"summary", "bank details", "leave details", "balances", "year to date"}
PAY_PERIOD = re.compile(
    r"(?im)^\s*(?:pay(?:roll)?\s+period|salary\s+month)\s*:\s*(?P<value>[A-Za-z]+\s+20\d{2}|20\d{2}[-/](?:0?[1-9]|1[0-2]))\s*$"
)


class GovernmentPayslipError(ValueError):
    pass


@dataclass(frozen=True)
class PayslipEntry:
    label: str
    amount: Decimal


@dataclass(frozen=True)
class GovernmentPayslip:
    fields: dict[str, str]
    pay_period: str | None
    earnings: tuple[PayslipEntry, ...]
    deductions: tuple[PayslipEntry, ...]
    printed_gross: Decimal
    printed_deductions: Decimal
    printed_net: Decimal
    calculated_net: Decimal
    totals_reconciled: bool
    review_required: bool
    review_reasons: tuple[str, ...]


def _normalize_label(raw: str) -> str:
    return re.sub(r"\s+", " ", raw.strip().casefold().rstrip(":"))


def parse_government_payslip(text: str) -> GovernmentPayslip:
    """Fail closed unless each amount belongs unambiguously to a known section.

    This parser is intended for layout-preserving OCR or operator-transcribed
    rows. Mixed two-column payslip layouts must first be segmented spatially.
    """
    if not text or len(text) > 200_000:
        raise GovernmentPayslipError("empty or oversized payslip text")
    fields: dict[str, str] = {}
    totals: dict[str, Decimal] = {}
    earnings: list[PayslipEntry] = []
    deductions: list[PayslipEntry] = []
    section: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        label = _normalize_label(line)
        if label in EARNINGS_HEADERS:
            section = "earnings"
            continue
        if label in DEDUCTIONS_HEADERS:
            section = "deductions"
            continue
        if label in ENDING_HEADERS:
            section = None
            continue

        # Named fields must have a colon; OCR has to preserve their boundaries.
        if ":" in line:
            raw_label, raw_value = line.split(":", 1)
            field_key = LABELS.get(_normalize_label(raw_label))
            if field_key is not None:
                value = raw_value.strip()
                if not value or field_key in fields:
                    raise GovernmentPayslipError("missing or repeated identity field")
                fields[field_key] = value
                continue

        # Totals are identified by their exact label, not nearby amounts.
        for printed_label, key in TOTAL_LABELS.items():
            matched = re.fullmatch(
                re.escape(printed_label) + rf"\s*:?[\s]{{1,}}{AMOUNT}", line, flags=re.I
            )
            if matched:
                if key in totals:
                    raise GovernmentPayslipError("duplicate printed total")
                totals[key] = money(matched.group(1))
                section = None
                break
        else:
            if section:
                match = LINE_ITEM.fullmatch(line)
                if match:
                    item_label = match.group("label").strip()
                    item_amount = money(match.group("amount"))
                    entry = PayslipEntry(item_label, item_amount)
                    (earnings if section == "earnings" else deductions).append(entry)
                elif re.search(r"\d[\d,]*\.\d{2}", line):
                    # An amount-containing row that OCR failed to segment
                    # cannot be ignored without risking a false reconciliation.
                    raise GovernmentPayslipError("unparseable financial line")
    if not earnings or not deductions:
        raise GovernmentPayslipError("earnings or deductions missing")
    if set(totals) != {"gross", "deductions", "net"}:
        raise GovernmentPayslipError("printed payslip totals missing")
    checked = validate_payslip_totals(
        [item.amount for item in earnings],
        [item.amount for item in deductions],
        printed_earnings=totals["gross"],
        printed_deductions=totals["deductions"],
        printed_net_pay=totals["net"],
    )
    reasons: list[str] = []
    if not checked.is_reconciled:
        reasons.append("totals_mismatch")
    if "employee_number" not in fields or "employee_name" not in fields:
        reasons.append("employee_identity_incomplete")
    period = PAY_PERIOD.search(text)
    if not period:
        reasons.append("pay_period_not_confirmed")
    # Authentication, stamp verification and issuer checks are always pending
    # at this stage even if every financial total reconciles.
    reasons.append("issuer_and_stamp_unverified")
    return GovernmentPayslip(
        fields=fields,
        pay_period=period.group("value") if period else None,
        earnings=tuple(earnings),
        deductions=tuple(deductions),
        printed_gross=totals["gross"],
        printed_deductions=totals["deductions"],
        printed_net=totals["net"],
        calculated_net=checked.net_pay,
        totals_reconciled=checked.is_reconciled,
        review_required=True,
        review_reasons=tuple(reasons),
    )


def assess_payslip_stamp(
    stamp_region_dates: Sequence[date], *, assessed_at: date
) -> StampAssessment:
    """Assess only dates supplied by a stamp-localisation subsystem."""
    return assess_stamp_dates(stamp_region_dates, assessed_at=assessed_at)
