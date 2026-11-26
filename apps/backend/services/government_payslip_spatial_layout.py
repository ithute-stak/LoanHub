"""Spatial separation of government payslip earnings and deductions.

This module produces column-specific OCR lines. It does not interpret amounts,
approve a payslip or infer which stamp/date belongs to an issuer.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Sequence

from services.document_spatial_ocr import OCRLine, OCRWord, group_lines


class AmbiguousPayslipLayout(ValueError):
    pass


@dataclass(frozen=True)
class PayslipColumns:
    earnings: tuple[OCRLine, ...]
    deductions: tuple[OCRLine, ...]
    divider_x: int
    review_reasons: tuple[str, ...]


def _header(lines: Sequence[OCRLine], target: str) -> OCRLine:
    matching = [line for line in lines if re.sub(r"\s+", " ", line.text.strip()).casefold() == target]
    if len(matching) != 1:
        raise AmbiguousPayslipLayout("missing or duplicate " + target + " header")
    return matching[0]


def separate_financial_columns(
    words: Sequence[OCRWord], *, page_width: int, min_confidence: float = 55.0,
) -> PayslipColumns:
    """Locate both table headers, then split word coordinates by their midpoints.

    The two headers must be well separated and aligned horizontally.
    Any word spanning the divider in the table is explicitly rejected.
    A later adapter must still validate printed totals and each monetary row.
    """
    if page_width < 200 or not 0 <= min_confidence <= 100:
        raise ValueError("invalid page geometry or OCR threshold")
    lines = group_lines(words)
    left_header = _header(lines, "earnings")
    right_header = _header(lines, "deductions")
    if left_header.left >= right_header.left or right_header.left - left_header.left < page_width * 0.2:
        raise AmbiguousPayslipLayout("financial columns are not sufficiently separated")
    if abs(left_header.top - right_header.top) > max(left_header.bottom-left_header.top, right_header.bottom-right_header.top) * 2:
        raise AmbiguousPayslipLayout("financial headings are not on the same row")
    divider = (left_header.right + right_header.left) // 2
    if not left_header.right < divider < right_header.left:
        raise AmbiguousPayslipLayout("financial headings overlap")

    warnings: list[str] = []
    earning_words: list[OCRWord] = []
    deduction_words: list[OCRWord] = []
    for word in words:
        if word.top <= max(left_header.bottom, right_header.bottom):
            continue
        if word.confidence < min_confidence:
            warnings.append("low_confidence_financial_word")
        if word.left < divider < word.right:
            raise AmbiguousPayslipLayout("financial text crosses column divider")
        if word.right <= divider:
            earning_words.append(word)
        elif word.left >= divider:
            deduction_words.append(word)
        else:
            raise AmbiguousPayslipLayout("unassigned financial word")
    if not earning_words or not deduction_words:
        raise AmbiguousPayslipLayout("one financial column has no OCR words")
    return PayslipColumns(
        earnings=group_lines(earning_words),
        deductions=group_lines(deduction_words),
        divider_x=divider,
        review_reasons=tuple(sorted(set(warnings))),
    )
