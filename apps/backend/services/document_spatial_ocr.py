"""Spatial OCR primitives for scanned payslips and stamp localisation.

Returns page-coordinate word boxes and proposed regions for human/adapter review.
No stamp date is accepted merely because a date appears on the page. Financial
figures are not automatically assigned to earnings/deductions without layout checks.
"""
from __future__ import annotations

from dataclasses import dataclass
from io import StringIO
import csv
import re
from typing import Sequence

from PIL import Image

from services.document_intelligence_reader import DocumentReadError, _png, _run


@dataclass(frozen=True)
class OCRWord:
    text: str
    confidence: float
    left: int
    top: int
    width: int
    height: int
    block: int
    paragraph: int
    line: int

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass(frozen=True)
class OCRLine:
    text: str
    words: tuple[OCRWord, ...]
    left: int
    top: int
    right: int
    bottom: int

    @property
    def confidence(self) -> float:
        return sum(x.confidence for x in self.words) / len(self.words)


@dataclass(frozen=True)
class StampRegion:
    left: int
    top: int
    right: int
    bottom: int
    evidence: tuple[str, ...]
    requires_review: bool = True


STAMP_ANCHORS = (
    "stamp", "stamped", "certified", "received", "official", "signature",
)
DATE_TOKEN = re.compile(
    r"\b(?:\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|"
    r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b", re.I,
)


def parse_tesseract_tsv(tsv: str, *, width: int, height: int) -> tuple[OCRWord, ...]:
    """Retain location and OCR confidence; reject invalid or out-of-image boxes."""
    if width <= 0 or height <= 0:
        raise ValueError("invalid page dimensions")
    words = []
    for row in csv.DictReader(StringIO(tsv), delimiter="\t"):
        try:
            content = (row["text"] or "").strip()
            confidence = float(row["conf"])
            left, top, w, h = (int(row[x]) for x in ("left", "top", "width", "height"))
            block, par, line = (int(row[x]) for x in ("block_num", "par_num", "line_num"))
        except (TypeError, ValueError, KeyError) as exc:
            raise DocumentReadError("malformed spatial OCR output") from exc
        if not content or confidence < 0:
            continue
        if not 0 <= confidence <= 100 or left < 0 or top < 0 or w <= 0 or h <= 0:
            raise DocumentReadError("invalid OCR word bounds")
        if left + w > width or top + h > height:
            raise DocumentReadError("OCR word outside image")
        words.append(OCRWord(content, confidence, left, top, w, h, block, par, line))
    return tuple(words)


def spatial_ocr(image: Image.Image) -> tuple[OCRWord, ...]:
    """Use existing Tesseract binary with a bounded input; no persistence."""
    if image.width * image.height > 18_000_000 or max(image.size) > 5500:
        raise DocumentReadError("image exceeds spatial OCR limits")
    if image.width <= 0 or image.height <= 0:
        raise DocumentReadError("empty image")
    tsv = _run(
        ["tesseract", "stdin", "stdout", "--psm", "11", "tsv"],
        input=_png(image.convert("RGB")),
    ).decode("utf-8", errors="replace")
    return parse_tesseract_tsv(tsv, width=image.width, height=image.height)


def group_lines(words: Sequence[OCRWord]) -> tuple[OCRLine, ...]:
    """Group by Tesseract block/paragraph/line, not page-wide Y position.

    Two columns at the same vertical level must remain separate when the OCR
    engine assigns distinct line identifiers.
    """
    grouped: dict[tuple[int, int, int], list[OCRWord]] = {}
    for word in words:
        grouped.setdefault((word.block, word.paragraph, word.line), []).append(word)
    lines = []
    for group in grouped.values():
        group.sort(key=lambda x: (x.left, x.top))
        lines.append(OCRLine(
            text=" ".join(word.text for word in group),
            words=tuple(group),
            left=min(x.left for x in group),
            top=min(x.top for x in group),
            right=max(x.right for x in group),
            bottom=max(x.bottom for x in group),
        ))
    lines.sort(key=lambda x: (x.top, x.left))
    return tuple(lines)


def propose_stamp_regions(
    lines: Sequence[OCRLine], *,
    width: int,
    height: int,
    padding_px: int = 100,
) -> tuple[StampRegion, ...]:
    """Suggest candidates across the ENTIRE document, independent of position.

    Anchors provide localisation hints only; the stamp must subsequently be
    distinguished from payroll text and its date verified from the stamp crop.
    """
    if width <= 0 or height <= 0 or padding_px < 0:
        raise ValueError("invalid image dimensions or padding")
    proposals: list[StampRegion] = []
    for line in lines:
        tokens = set(re.findall(r"[a-z]+", line.text.casefold()))
        evidence = tuple(sorted(tokens.intersection(STAMP_ANCHORS)))
        if not evidence:
            continue
        proposals.append(StampRegion(
            max(0, line.left - padding_px),
            max(0, line.top - padding_px),
            min(width, line.right + padding_px),
            min(height, line.bottom + padding_px),
            evidence,
        ))
    return tuple(proposals)


def date_strings_in_stamp_crop(lines: Sequence[OCRLine]) -> tuple[str, ...]:
    """Candidate raw strings only; returns no 'valid stamp' decision."""
    dates: list[str] = []
    for line in lines:
        dates.extend(match.group() for match in DATE_TOKEN.finditer(line.text))
    return tuple(dict.fromkeys(dates))
