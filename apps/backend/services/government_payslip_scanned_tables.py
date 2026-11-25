"""Bounded table OCR for Lesotho government staff payslips.

Crop the two actual financial columns using independently detected headings,
recognise their payroll-code rows, and verify all printed totals. An OCR read
is not evidence of issuer authenticity, identity or an approved loan.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
import re

from PIL import Image

from services.document_intelligence_reader import DocumentReadError, _run
from services.document_intelligence_foundation import money, validate_payslip_totals
from services.document_spatial_ocr import OCRWord
from services.government_payslip_spatial_layout import AmbiguousPayslipLayout

_AMOUNT = r"([0-9][0-9,]*\.[0-9]{2})"
_ENTRY = re.compile(r"^\s*(\d{3,5})\s+(.+?)\s+" + _AMOUNT + r"\s*$")
_EARNINGS_TOTAL = re.compile(r"^\s*Total Earnings\s*:\s*" + _AMOUNT + r"\s*$", re.I)
_DEDUCTIONS_TOTAL = re.compile(r"^\s*Total Deductions\s*:\s*" + _AMOUNT + r"\s*$", re.I)


@dataclass(frozen=True)
class ScannedPayItem:
    payroll_code: str
    description: str
    amount: Decimal


@dataclass(frozen=True)
class ScannedPayslipFinancials:
    earnings: tuple[ScannedPayItem, ...]
    deductions: tuple[ScannedPayItem, ...]
    printed_gross: Decimal
    printed_deductions: Decimal
    printed_net_candidate: Decimal | None
    totals_reconciled: bool
    review_required: bool
    review_reasons: tuple[str, ...]


def _heading(words: tuple[OCRWord, ...], text: str, *, width: int, height: int) -> OCRWord:
    matches = [w for w in words if w.text.casefold().strip().rstrip(":") == text
               and w.confidence >= 55 and w.top < height * 0.65]
    distinct: list[OCRWord] = []
    for item in sorted(matches, key=lambda w: -w.confidence):
        if not any(abs(item.left - other.left) < width // 80
                   and abs(item.top - other.top) < height // 120 for other in distinct):
            distinct.append(item)
    if len(distinct) != 1:
        raise AmbiguousPayslipLayout("missing or ambiguous " + text + " column heading")
    return distinct[0]


def _ocr_table(image: Image.Image) -> str:
    out = BytesIO()
    image.save(out, format="PNG")
    return _run(
        ["tesseract", "stdin", "stdout", "--psm", "6"],
        input=out.getvalue(),
    ).decode("utf-8", errors="replace")


def _parse_table(text: str, *, section: str, allow_missing_heading: bool = False) -> tuple[tuple[ScannedPayItem, ...], Decimal]:
    required_header = "earnings" if section == "earnings" else "deductions"
    expected_total = _EARNINGS_TOTAL if section == "earnings" else _DEDUCTIONS_TOTAL
    rows: list[ScannedPayItem] = []
    totals: list[Decimal] = []
    started = allow_missing_heading
    for raw in text.splitlines():
        line = raw.strip().lstrip("| ").strip()
        if not line:
            continue
        if not started:
            if line.casefold() == required_header:
                started = True
            continue
        if started and line.casefold() == required_header and not rows:
            continue
        match = expected_total.fullmatch(line)
        if match:
            totals.append(money(match.group(1)))
            break
        entry = _ENTRY.fullmatch(line)
        if not entry:
            # No unrecognised line can silently disappear from a financial table.
            raise AmbiguousPayslipLayout("unrecognised " + section + " payroll row")
        code, description, amount = entry.groups()
        if not description.strip() or any(row.payroll_code == code for row in rows):
            raise AmbiguousPayslipLayout("duplicate or missing payroll description")
        rows.append(ScannedPayItem(code, description.strip(), money(amount)))
    if not started or len(totals) != 1 or not rows:
        raise AmbiguousPayslipLayout("missing table heading, item or printed total")
    if sum((x.amount for x in rows), Decimal("0.00")) != totals[0]:
        raise AmbiguousPayslipLayout("printed " + section + " total does not match itemised rows")
    return tuple(rows), totals[0]


def read_scanned_payslip_financials(
    image: Image.Image, words: tuple[OCRWord, ...], *,
    net_pay_candidate: Decimal | None = None,
) -> ScannedPayslipFinancials:
    """Use located EARNINGS/DEDUCTIONS headings; no pixel coordinates hard-coded.

    Does not infer net pay from subtraction, nor accept mismatching or missing
    payroll items. All results are for a staff reviewer, not auto-approval.
    """
    width, height = image.size
    if width < 650 or height < 850 or width * height > 18_000_000:
        raise DocumentReadError("payslip scan outside layout bounds")
    right = _heading(words, "deductions", width=width, height=height)
    missing_left_heading = False
    try:
        left = _heading(words, "earnings", width=width, height=height)
    except AmbiguousPayslipLayout:
        # On some scanned payslips the dark EARNINGS band vanishes in OCR.
        # Still allow a left table only when the independently located right
        # DEDUCTIONS column is in the expected half of the same page.
        if right.left < width * .52 or right.left > width * .75:
            raise
        missing_left_heading = True
        left = None
    if left is not None and (
        right.left - left.left < width * .25
        or abs(left.top-right.top) > height * .03
    ):
        raise AmbiguousPayslipLayout("payslip financial columns not aligned")
    divider = ((left.right + right.left) // 2 if left is not None
               else right.left - width // 20)
    start = max(0, (min(left.top, right.top) if left else right.top) - height // 100)
    finish = min(height, start + height // 5)
    left_start = (max(0, left.left-width//100) if left is not None else width // 10)
    if finish <= start or not left_start < divider < right.left:
        raise AmbiguousPayslipLayout("unsafe financial table bounds")
    left_crop = image.crop((left_start, start, divider, finish))
    right_crop = image.crop((max(0, right.left-width//100), start, width, finish))
    earnings, printed_gross = _parse_table(
        _ocr_table(left_crop), section="earnings",
        allow_missing_heading=missing_left_heading,
    )
    deductions, printed_deductions = _parse_table(_ocr_table(right_crop), section="deductions")
    reasons: list[str] = ["issuer_and_original_document_unverified"]
    if missing_left_heading:
        reasons.append("earnings_heading_not_recognised")
    reconciled = False
    if net_pay_candidate is None:
        reasons.append("printed_net_pay_unconfirmed")
    else:
        checked = validate_payslip_totals(
            [x.amount for x in earnings], [x.amount for x in deductions],
            printed_earnings=printed_gross, printed_deductions=printed_deductions,
            printed_net_pay=net_pay_candidate,
        )
        reconciled = checked.is_reconciled
        if not reconciled:
            reasons.append("printed_net_pay_does_not_reconcile")
    return ScannedPayslipFinancials(
        earnings, deductions, printed_gross, printed_deductions,
        net_pay_candidate, reconciled, True, tuple(reasons),
    )
