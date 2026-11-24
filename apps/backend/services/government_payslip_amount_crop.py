"""Targeted monetary-cell OCR for scanned government payslips.

A caller must first locate the exact printed monetary *cell* (not its label).
The reader compares OCR configurations of the SAME crop, which is useful for
recovery but is not independent document verification or proof of authenticity.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
import re

from PIL import Image, ImageEnhance

from services.document_intelligence_foundation import money
from services.document_intelligence_reader import DocumentReadError, _run

_MONEY = re.compile(r"^\s*(?:M|LSL)?\s*([0-9][0-9,]*\.[0-9]{2})\s*$", re.I)


@dataclass(frozen=True)
class AmountCropEvidence:
    candidate: Decimal | None
    recognized_readings: tuple[str, ...]
    mode_agreement: bool
    review_required: bool
    review_reasons: tuple[str, ...]


def _run_amount_ocr(image: Image.Image, psm: int) -> str:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return _run(
        ["tesseract", "stdin", "stdout", "--psm", str(psm)],
        input=buffer.getvalue(),
    ).decode("utf-8", errors="replace").strip()


def read_amount_crop(
    image: Image.Image, box: tuple[int, int, int, int],
) -> AmountCropEvidence:
    """Return corroborated candidates from a precisely located box.

    Never search the entire document for a matching amount, since unrelated
    balances and salary fields may share the same monetary values.
    """
    if len(box) != 4:
        raise ValueError("monetary crop requires four coordinates")
    left, top, right, bottom = box
    if not (0 <= left < right <= image.width and 0 <= top < bottom <= image.height):
        raise ValueError("invalid monetary crop bounds")
    if (right-left)*(bottom-top) > 2_000_000 or right-left < 20 or bottom-top < 12:
        raise DocumentReadError("monetary crop outside allowed dimensions")
    original = image.convert("L").crop(box)
    adjusted = ImageEnhance.Contrast(
        ImageEnhance.Sharpness(original).enhance(2.0)
    ).enhance(2.0)
    processed = adjusted.resize((adjusted.width * 4, adjusted.height * 4))
    readings = tuple(_run_amount_ocr(processed, psm) for psm in (6, 7))
    candidates: list[Decimal] = []
    for raw in readings:
        hit = _MONEY.fullmatch(raw)
        if hit:
            candidates.append(money(hit.group(1)))
    unique = set(candidates)
    agreement = len(candidates) == len(readings) and len(unique) == 1
    reasons = ["printed_amount_crop_requires_reviewer_confirmation"]
    if not candidates:
        reasons.append("amount_crop_unreadable")
    elif not agreement:
        reasons.append("amount_crop_ocr_disagreement")
    return AmountCropEvidence(
        candidate=next(iter(unique)) if agreement else None,
        recognized_readings=readings,
        mode_agreement=agreement,
        review_required=True,
        review_reasons=tuple(reasons),
    )
