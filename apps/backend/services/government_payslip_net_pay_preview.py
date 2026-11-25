"""NET PAY crop preview for a managed scanned payslip, strictly review-only."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from services.document_intelligence_reader import _pdf_pages, _safe_image, DocumentReadError
from services.document_spatial_ocr import spatial_ocr
from services.government_payslip_amount_locator import (
    AmountCellLocationError, locate_net_pay_cell,
)
from services.government_payslip_amount_crop import read_amount_crop


@dataclass(frozen=True)
class NetPayPreview:
    candidate: Decimal | None
    status: str
    review_required: bool
    review_reasons: tuple[str, ...]


def preview_net_pay_amount(content: bytes, filename: str) -> NetPayPreview:
    """Read a crop only if it is safely positioned; never approve its value."""
    if filename.casefold().endswith(".pdf"):
        pages = _pdf_pages(content)
        if len(pages) != 1 or pages[0][0] != "image":
            return NetPayPreview(None, "manual_review", True, ("net_pay_spatial_image_unavailable",))
        image = pages[0][1]
    else:
        image = _safe_image(content)
    words = spatial_ocr(image)
    try:
        located = locate_net_pay_cell(words, width=image.width, height=image.height)
    except AmountCellLocationError:
        return NetPayPreview(None, "manual_review", True, ("net_pay_cell_not_reliably_located",))
    evidence = read_amount_crop(image, located.box)
    return NetPayPreview(
        evidence.candidate, "candidate_only" if evidence.candidate is not None else "manual_review",
        True, evidence.review_reasons,
    )
