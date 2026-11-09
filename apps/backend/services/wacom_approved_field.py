"""Canonical, SHA-256-bound Wacom field placement (approval metadata only).

No handwritten ink is placed or contract executed by this module. Coordinates
are PDF points with origin at bottom-left on the exact, verified source PDF.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from services.wacom_pdf_signature_placement import SignatureField

MAX_PAGES = 100
MAX_SOURCE_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class ApprovedField:
    page_index: int
    x: Decimal
    y: Decimal
    width: Decimal
    height: Decimal
    page_count: int


def _fixed(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        raise ValueError("Signature coordinate is not numeric")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("Signature coordinate is not finite")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Invalid field coordinate") from exc
    if not number.is_finite():
        raise ValueError("Invalid field coordinate")
    # Exact 0.001-point grid avoids ambiguity from float serialization.
    fixed = number.quantize(Decimal("0.001"))
    if number != fixed:
        raise ValueError("Coordinates must use at most 3 decimal places")
    return fixed


def bind_approved_field(*, source_pdf: bytes, expected_sha256: str,
                        page_index: int, x, y, width, height,
                        expected_page_count: int) -> tuple[ApprovedField, str]:
    if (not isinstance(source_pdf, bytes) or len(source_pdf) < 5
            or len(source_pdf) > MAX_SOURCE_BYTES
            or not source_pdf.startswith(b"%PDF-")
            or hashlib.sha256(source_pdf).hexdigest() != expected_sha256):
        raise ValueError("Changed or unavailable source PDF")
    if (isinstance(page_index, bool) or not isinstance(page_index, int)
            or isinstance(expected_page_count, bool)
            or not isinstance(expected_page_count, int)
            or expected_page_count < 1 or expected_page_count > MAX_PAGES):
        raise ValueError("Invalid signature page index or page count")
    fixed = [_fixed(v) for v in (x, y, width, height)]
    try:
        pdf = PdfReader(io.BytesIO(source_pdf), strict=True)
        if pdf.is_encrypted or len(pdf.pages) != expected_page_count:
            raise ValueError("PDF count changed or encrypted")
        if page_index < 0 or page_index >= len(pdf.pages):
            raise ValueError("Signature page outside PDF")
        for p in pdf.pages:
            if int(p.get("/Rotate", 0)) % 360 != 0:
                raise ValueError("Rotated PDF unsupported")
        page = pdf.pages[page_index]
        if any(not math.isfinite(float(v)) for v in (page.mediabox.width, page.mediabox.height)):
            raise ValueError("Invalid PDF media box")
        SignatureField(
            page_index=page_index, x=float(fixed[0]), y=float(fixed[1]),
            width=float(fixed[2]), height=float(fixed[3]),
        ).validate(
            page_width=float(page.mediabox.width),
            page_height=float(page.mediabox.height),
            pages=expected_page_count,
        )
    except (ValueError, TypeError, KeyError, IndexError, OSError, PdfReadError) as exc:
        raise ValueError("Source PDF field cannot be authorized") from exc
    field = ApprovedField(page_index, *fixed, expected_page_count)
    canonical = {
        "source_sha256": expected_sha256,
        "page_index": page_index, "page_count": expected_page_count,
        "x": str(fixed[0]), "y": str(fixed[1]),
        "width": str(fixed[2]), "height": str(fixed[3]),
    }
    digest = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return field, digest


def stored_field_matches(*, authorization, source_pdf: bytes, expected_sha256: str) -> bool:
    try:
        _, digest = bind_approved_field(
            source_pdf=source_pdf, expected_sha256=expected_sha256,
            page_index=authorization.field_page_index,
            x=authorization.field_x, y=authorization.field_y,
            width=authorization.field_width, height=authorization.field_height,
            expected_page_count=authorization.field_page_count,
        )
        return digest == authorization.field_binding_sha256
    except (AttributeError, ValueError):
        return False
