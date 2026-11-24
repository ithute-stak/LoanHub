"""Conservative stamp evidence preview for stored government payslip scans.

Only returns dates and review statuses, never full OCR text or employee data.
Layout candidates are a heuristic; missing anchors never prove missing stamps.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from io import BytesIO

from PIL import Image

from services.document_intelligence_reader import (
    DocumentReadError, _pdf_pages, _safe_image,
)
from services.document_spatial_ocr import (
    group_lines, propose_stamp_regions, spatial_ocr,
)
from services.government_payslip_stamp_evidence import assess_spatial_stamp


@dataclass(frozen=True)
class PayslipStampPreview:
    status: str
    detected_stamp_date: str | None
    candidate_region_count: int
    manual_review_required: bool
    review_reasons: tuple[str, ...]


def _images(data: bytes, filename: str) -> tuple[Image.Image, ...]:
    if filename.lower().endswith(".pdf"):
        pages = _pdf_pages(data)
        if len(pages) != 1:
            raise DocumentReadError("payslip stamp preview requires a single-page document")
        kind, value = pages[0]
        if kind != "image":
            # Native text extraction does not localize a physical stamp.
            return ()
        return (value,)
    return (_safe_image(data),)


def preview_payslip_stamp(data: bytes, filename: str, *, assessed_at: date) -> PayslipStampPreview:
    """Inspect candidate stamp dates anywhere on a one-page raster image.

    The result always requires human review, including when the date is recent.
    The origin of the stamp and date attribution cannot be authenticated by OCR.
    """
    images = _images(data, filename)
    if not images:
        return PayslipStampPreview(
            "manual_review", None, 0, True, ("stamp_spatial_evidence_unavailable",)
        )
    img = images[0]
    words = spatial_ocr(img)
    lines = group_lines(words)
    regions = propose_stamp_regions(lines, width=img.width, height=img.height)
    evidence = assess_spatial_stamp(lines, regions, assessed_at=assessed_at)
    return PayslipStampPreview(
        evidence.assessment.status.value,
        evidence.assessment.stamp_date.isoformat() if evidence.assessment.stamp_date else None,
        evidence.candidate_region_count,
        True,
        evidence.review_reasons,
    )
