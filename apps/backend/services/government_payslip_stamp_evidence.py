"""Location-aware stamp date evidence, without confusing payslip dates.

This is a candidate review aid, NOT stamp-authenticity recognition. The caller
supplies proposed stamp boxes from OCR; dates outside those boxes are ignored.
An uncorroborated OCR reading always requires human review.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import calendar
import re
from typing import Sequence

from services.document_intelligence_foundation import (
    StampAssessment, StampStatus, assess_stamp_dates,
)
from services.document_spatial_ocr import OCRLine, StampRegion, date_strings_in_stamp_crop

_MONTHS = {name.casefold(): n for n, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.casefold(): n for n, name in enumerate(calendar.month_abbr) if name})
_TEXT_DATE = re.compile(r"^\s*(\d{1,2})[-\s]+([A-Za-z]{3,9})[-\s]+(\d{4})\s*$")


@dataclass(frozen=True)
class StampEvidence:
    assessment: StampAssessment
    candidate_dates: tuple[date, ...]
    unreadable_dates: tuple[str, ...]
    candidate_region_count: int
    requires_manual_review: bool
    review_reasons: tuple[str, ...]


def _parse_unambiguous_stamp_date(raw: str) -> date | None:
    """Read textual months only; numeric DD/MM vs MM/DD is ambiguous."""
    found = _TEXT_DATE.fullmatch(raw)
    if not found:
        return None
    day, month_name, year = found.groups()
    month = _MONTHS.get(month_name.casefold())
    if not month:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def _overlaps(line: OCRLine, box: StampRegion) -> bool:
    return (line.left < box.right and line.right > box.left
            and line.top < box.bottom and line.bottom > box.top)


def assess_spatial_stamp(
    lines: Sequence[OCRLine],
    proposed_regions: Sequence[StampRegion],
    *,
    assessed_at: date,
    minimum_confidence: float = 70.0,
) -> StampEvidence:
    """Require review even for a recent candidate: dates alone prove no authenticity."""
    if not 0 <= minimum_confidence <= 100:
        raise ValueError("invalid confidence threshold")
    parsed: set[date] = set()
    unreadable: set[str] = set()
    reasons: list[str] = []
    if not proposed_regions:
        reasons.append("stamp_region_not_detected")
    for box in proposed_regions:
        region_lines = [line for line in lines if _overlaps(line, box)]
        raw_dates = date_strings_in_stamp_crop(region_lines)
        if not raw_dates:
            reasons.append("stamp_date_not_detected")
        for raw in raw_dates:
            date_value = _parse_unambiguous_stamp_date(raw)
            if date_value is None:
                unreadable.add(raw)
                continue
            # Any low-confidence OCR word contributing to this region
            # prevents automated reliance on this candidate.
            contributing = [line for line in region_lines if raw.casefold() in line.text.casefold()]
            if not contributing or min(line.confidence for line in contributing) < minimum_confidence:
                reasons.append("stamp_date_low_confidence")
            parsed.add(date_value)
    if unreadable:
        reasons.append("stamp_date_format_ambiguous")
    result = assess_stamp_dates(sorted(parsed), assessed_at=assessed_at)
    if result.status != StampStatus.VALID_DATE:
        reasons.append("stamp_date_" + result.status.value)
    reasons.append("stamp_authenticity_unverified")
    return StampEvidence(
        result,
        tuple(sorted(parsed)),
        tuple(sorted(unreadable)),
        len(proposed_regions),
        True,
        tuple(dict.fromkeys(reasons)),
    )
