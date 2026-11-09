"""Pure Wacom final-PDF *candidate* renderer; NOT an executed contract.

No API, audit record, contract mutation, approval consumption, or signing
assertion. A later locked transaction must revalidate all records, bind this
digest, archive atomically, and determine legally appropriate execution status.
The embedded PNG is a visible mark, not a cryptographic PDF digital signature.
"""
from __future__ import annotations

import hashlib
import io
from decimal import Decimal

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from services.wacom_approved_field import bind_approved_field, stored_field_matches

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PNG_BYTES = 2 * 1024 * 1024
MAX_PAGES = 100


def render_final_pdf_candidate(
    *, source_pdf: bytes, handwriting_png: bytes, authorization,
    expected_source_sha256: str, expected_handwriting_sha256: str,
) -> tuple[bytes, str]:
    """Return marked PDF bytes and SHA-256, with no side effects.

    Callers MUST NOT treat this return value alone as contract execution.
    """
    if (not isinstance(source_pdf, bytes) or not source_pdf.startswith(b"%PDF-")
            or len(source_pdf) > MAX_PDF_BYTES
            or hashlib.sha256(source_pdf).hexdigest() != expected_source_sha256):
        raise HTTPException(409, "Original PDF bytes changed")
    if (not isinstance(handwriting_png, bytes) or
            not handwriting_png.startswith(b"\x89PNG\r\n\x1a\n") or
            len(handwriting_png) > MAX_PNG_BYTES or
            hashlib.sha256(handwriting_png).hexdigest() != expected_handwriting_sha256):
        raise HTTPException(409, "Handwriting evidence changed")
    if (authorization is None
            or authorization.document_sha256 != expected_source_sha256
            or authorization.evidence_sha256 != expected_handwriting_sha256
            or not stored_field_matches(
                authorization=authorization, source_pdf=source_pdf,
                expected_sha256=expected_source_sha256,
            )):
        raise HTTPException(409, "Approved signature field or evidence invalid")

    try:
        reader = PdfReader(io.BytesIO(source_pdf), strict=True)
        if reader.is_encrypted or len(reader.pages) != authorization.field_page_count:
            raise ValueError("PDF source version changed")
        ink = Image.open(io.BytesIO(handwriting_png))
        if (ink.format != "PNG" or ink.width < 2 or ink.height < 2
                or ink.width > 4000 or ink.height > 4000
                or ink.width * ink.height > 4_000_000):
            raise ValueError("Invalid handwriting dimensions")
        ink.load()
        if ink.mode not in ("RGB", "RGBA"):
            ink = ink.convert("RGBA")
        # An opaque all-white PNG is not a handwriting image.
        if ink.getbbox() is None:
            raise ValueError("Blank handwriting")
        if ink.mode == "RGBA":
            alpha = ink.getchannel("A")
            if alpha.getextrema()[1] == 0:
                raise ValueError("Fully transparent handwriting")
        elif ink.convert("L").getextrema() == (255, 255):
            raise ValueError("Blank white handwriting")

        writer = PdfWriter()
        field = authorization
        for index, page in enumerate(reader.pages):
            if int(page.get("/Rotate", 0)) % 360:
                raise ValueError("Rotated document")
            if index == field.field_page_index:
                from services.wacom_pdf_signature_placement import SignatureField
                signature = SignatureField(
                    page_index=index, x=float(field.field_x), y=float(field.field_y),
                    width=float(field.field_width), height=float(field.field_height),
                )
                signature.validate(
                    page_width=float(page.mediabox.width),
                    page_height=float(page.mediabox.height),
                    pages=len(reader.pages),
                )
                overlay = io.BytesIO()
                c = canvas.Canvas(overlay, pagesize=(
                    float(page.mediabox.width), float(page.mediabox.height),
                ))
                ratio = min(signature.width / ink.width, signature.height / ink.height)
                w, h = ink.width * ratio, ink.height * ratio
                c.drawImage(
                    ImageReader(ink),
                    signature.x + (signature.width - w) / 2,
                    signature.y + (signature.height - h) / 2,
                    width=w, height=h, mask="auto",
                )
                c.save()
                overlay.seek(0)
                page.merge_page(PdfReader(overlay).pages[0])
            writer.add_page(page)
        writer.add_metadata({
            "/Title": "LoanHub Wacom contract execution candidate",
            "/Subject": "Visible handwriting placement; NOT proof of contract execution",
        })
        output = io.BytesIO()
        writer.write(output)
        pdf = output.getvalue()
        if len(pdf) > MAX_PDF_BYTES + 5 * 1024 * 1024:
            raise ValueError("Candidate PDF exceeds size limit")
        check = PdfReader(io.BytesIO(pdf), strict=True)
        if len(check.pages) != authorization.field_page_count:
            raise ValueError("Rendered PDF page count mismatch")
        return pdf, hashlib.sha256(pdf).hexdigest()
    except (ValueError, TypeError, KeyError, OSError, PdfReadError,
            UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "Could not safely render PDF candidate") from exc
