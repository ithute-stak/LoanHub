"""Find a conservative net-pay monetary cell from spatial OCR coordinates.

This locator never guesses a salary amount. The label NET PAY must be present
as nearby OCR words, with a clear right-side cell on the same baseline.
Ambiguity stops processing; downstream crop OCR remains reviewer-confirmed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from services.document_spatial_ocr import OCRWord


class AmountCellLocationError(ValueError):
    pass


@dataclass(frozen=True)
class LocatedAmountCell:
    label: str
    box: tuple[int, int, int, int]
    review_required: bool = True


def locate_net_pay_cell(
    words: Sequence[OCRWord], *, width: int, height: int,
    min_label_confidence: float = 65.0,
) -> LocatedAmountCell:
    """Find a NET + PAY label; return a bounded amount-only search rectangle.

    Assumes a horizontal row layout. Rotated, stacked, or ambiguous labels
    must undergo a separate preprocessing and review step.
    """
    if width < 120 or height < 60 or not 0 <= min_label_confidence <= 100:
        raise ValueError("invalid OCR page geometry")
    matches: list[tuple[OCRWord, OCRWord]] = []
    for first in words:
        if first.text.strip().casefold().rstrip(":") != "net":
            continue
        for second in words:
            if second.text.strip().casefold().rstrip(":") != "pay":
                continue
            if first.confidence < min_label_confidence or second.confidence < min_label_confidence:
                continue
            if second.left <= first.left or second.left - first.right > max(first.height, second.height) * 3:
                continue
            if abs(first.top - second.top) > max(first.height, second.height):
                continue
            matches.append((first, second))
    if len(matches) != 1:
        raise AmountCellLocationError("missing or ambiguous NET PAY label")
    left_label, right_label = matches[0]
    # A monetary cell should lie directly right of the label. Do not consume
    # the next line, where unrelated debt or salary figures may appear.
    row_height = max(left_label.height, right_label.height)
    top = max(0, min(left_label.top, right_label.top) - row_height // 2)
    bottom = min(height, max(left_label.bottom, right_label.bottom) + row_height // 2)
    left = right_label.right + max(4, row_height // 4)
    right = min(width, left + min(450, max(100, width // 3)))
    if right - left < 35 or bottom - top < 12 or (right-left)*(bottom-top) > 2_000_000:
        raise AmountCellLocationError("NET PAY monetary cell cannot be safely isolated")
    # Reject any other label that appears inside the proposed money cell.
    for word in words:
        if word is left_label or word is right_label:
            continue
        if word.top < bottom and word.bottom > top and word.left < right and word.right > left:
            token = word.text.strip().replace(",", "").replace(".", "")
            if any(ch.isalpha() for ch in token) and token.upper() not in {"M", "LSL"}:
                raise AmountCellLocationError("non-monetary content in NET PAY cell")
    return LocatedAmountCell("net_pay", (left, top, right, bottom))
