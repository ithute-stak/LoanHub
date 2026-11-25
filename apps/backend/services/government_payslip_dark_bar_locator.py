"""Conservative layout fallback for a dark-bar NET PAY row.

For government payslips whose white-on-dark NET PAY label disappears during
OCR, use the separately recognised EARNINGS table heading and horizontal
summary-bar geometry. No payroll amount is inferred: the returned rectangle
must still pass two OCR reads and human verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from PIL import Image

from services.document_spatial_ocr import OCRWord
from services.government_payslip_amount_locator import (
    AmountCellLocationError, LocatedAmountCell,
)


def locate_dark_bar_net_pay_cell(
    image: Image.Image,
    words: Sequence[OCRWord],
    *,
    min_heading_confidence: float = 65.0,
) -> LocatedAmountCell:
    """Find the second of two separated summary bars beneath EARNINGS.

    Fails closed without a reliable earnings anchor, two distinct dark bars,
    or a bounded amount-only box. Designed for horizontal single-page scans.
    The bar location is an OCR *candidate*, never evidence of verified income.
    """
    width, height = image.size
    if width < 650 or height < 850:
        raise AmountCellLocationError("scan too small for geometric net pay locator")
    headings = [
        word for word in words
        if word.text.strip().casefold().rstrip(":") == "earnings"
        and word.confidence >= min_heading_confidence
        and word.top < height // 2
    ]
    # Normal and inverted OCR can report the same physical anchor twice.
    # Deduplicate only overlapping boxes; separate headings remain ambiguous.
    distinct: list[OCRWord] = []
    for candidate in sorted(headings, key=lambda w: -w.confidence):
        if any(
            abs(candidate.left - known.left) <= max(12, width // 70)
            and abs(candidate.top - known.top) <= max(12, height // 130)
            for known in distinct
        ):
            continue
        distinct.append(candidate)
    if len(distinct) != 1:
        raise AmountCellLocationError("missing or ambiguous earnings table anchor")
    heading = distinct[0]
    bar_left = max(0, heading.left - max(8, width // 100))
    bar_right = min(width, bar_left + int(width * 0.29))
    if bar_right - bar_left < 130:
        raise AmountCellLocationError("insufficient space for financial summary bar")

    greyscale = image.convert("L")
    start = heading.bottom + max(30, height // 25)
    finish = min(height * 3 // 4, heading.bottom + height // 3)
    if finish <= start + 40:
        raise AmountCellLocationError("summary region not found")

    bars: list[tuple[int, int]] = []
    active_start: int | None = None
    for y in range(start, finish):
        # PIL histogram is bounded to the expected left-side financial column.
        counts = greyscale.crop((bar_left, y, bar_right, y + 1)).histogram()
        ratio = sum(counts[:155]) / (bar_right - bar_left)
        dark = ratio >= 0.64
        if dark and active_start is None:
            active_start = y
        elif not dark and active_start is not None:
            if y - active_start >= max(12, height // 130):
                bars.append((active_start, y))
            active_start = None
    if active_start is not None and finish - active_start >= max(12, height // 130):
        bars.append((active_start, finish))

    if len(bars) < 2:
        raise AmountCellLocationError("two summary bars not found")
    # Only the first pair is accepted; additional dark bars below may be tax
    # or loan balance summaries and must never be read as the net-pay amount.
    first, second = bars[:2]
    gap = second[0] - first[1]
    if not (height // 130 <= gap <= height // 18):
        raise AmountCellLocationError("summary bar spacing is ambiguous")
    if abs((first[1] - first[0]) - (second[1] - second[0])) > height // 100:
        raise AmountCellLocationError("summary bars have inconsistent heights")

    left = bar_right + max(6, width // 150)
    right = min(width, left + int(width * 0.118))
    top = max(0, second[0] - 2)
    bottom = min(height, second[1] + 2)
    if right - left < 35 or bottom - top < 12 or (right-left)*(bottom-top) > 2_000_000:
        raise AmountCellLocationError("unsafe summary amount crop")
    return LocatedAmountCell("net_pay_dark_bar_candidate", (left, top, right, bottom))
