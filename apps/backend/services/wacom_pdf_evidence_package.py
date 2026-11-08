"""Generate a review-only Wacom PDF evidence package.

Does not sign contracts, use a digital certificate, or modify loan state.
Never place handwriting over a contract's signature field: the image is
presented as reviewed evidence on a clearly marked, separate appendix.
"""
from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

MAX_SOURCE_PDF = 20 * 1024 * 1024
MAX_EVIDENCE_PNG = 2 * 1024 * 1024
MAX_PDF_PAGES = 100


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_review_evidence_pdf(*, source_pdf: bytes, source_sha256: str,
                              handwriting_png: bytes, evidence_sha256: str,
                              contract_id: str, intent_id: str,
                              binding_sha256: str, consent_reference: str,
                              review_reference: str) -> tuple[bytes, str]:
    """Return (PDF bytes, SHA-256), with no storage or database mutation."""
    if (not source_pdf or len(source_pdf) > MAX_SOURCE_PDF or
            not source_pdf.startswith(b"%PDF-") or _digest(source_pdf) != source_sha256):
        raise HTTPException(409, "Source contract PDF integrity check failed")
    if (not handwriting_png or len(handwriting_png) > MAX_EVIDENCE_PNG or
            not handwriting_png.startswith(b"\x89PNG\r\n\x1a\n") or
            _digest(handwriting_png) != evidence_sha256):
        raise HTTPException(409, "Reviewed handwriting evidence integrity check failed")
    if any(not value or len(value) > 180 for value in (
            contract_id, intent_id, binding_sha256, consent_reference, review_reference)):
        raise HTTPException(422, "Evidence-package metadata invalid")
    try:
        image = Image.open(io.BytesIO(handwriting_png))
        if image.format != "PNG":
            raise ValueError("Evidence must be PNG")
        if image.width < 2 or image.height < 2 or image.width * image.height > 4_000_000:
            raise ValueError("Signature preview dimensions outside policy")
        image.load()
        image = image.convert("RGB")
        src = PdfReader(io.BytesIO(source_pdf), strict=True)
        if src.is_encrypted or len(src.pages) < 1 or len(src.pages) > MAX_PDF_PAGES:
            raise ValueError("Unsupported or encrypted PDF document")
        # Materialize pages before generating; refuse malformed input.
        for page in src.pages:
            _ = page.mediabox
        appendix = io.BytesIO()
        page = canvas.Canvas(appendix, pagesize=(595, 842), pageCompression=1)
        page.setTitle("LoanHub Wacom Evidence - NOT A SIGNED CONTRACT")
        page.setFont("Helvetica-Bold", 18)
        page.drawString(48, 785, "REVIEW EVIDENCE ONLY - NOT SIGNED")
        page.setFont("Helvetica", 10)
        page.drawString(48, 750, "This appendix records independently reviewed handwriting evidence.")
        page.drawString(48, 735, "It does not execute a loan agreement or authorize signature reuse.")
        for idx, (name, value) in enumerate((
            ("Contract ID", contract_id), ("Evidence intent", intent_id),
            ("Source PDF SHA-256", source_sha256),
            ("Handwriting SHA-256", evidence_sha256),
            ("Document binding SHA-256", binding_sha256),
            ("Consent reference", consent_reference),
            ("Review reference", review_reference),
        )):
            label_y = 695 - idx * 31
            page.setFont("Helvetica-Bold", 9)
            page.drawString(48, label_y, name + ":")
            page.setFont("Courier", 8)
            page.drawString(48, label_y - 12, value[:100])
        image.thumbnail((480, 210), Image.Resampling.LANCZOS)
        page.setStrokeColorRGB(0.3, 0.3, 0.3)
        page.rect(48, 180, 499, 230)
        page.drawImage(ImageReader(image), 57, 190, width=image.width,
                       height=image.height, preserveAspectRatio=True, anchor="c")
        page.setFont("Helvetica-Bold", 10)
        page.drawString(48, 135, "REVIEW PREVIEW - NOT A LEGALLY FINALIZED DOCUMENT")
        page.setFont("Helvetica", 8)
        page.drawString(48, 120, "Generated: " + datetime.now(timezone.utc).isoformat())
        page.save()
        appendix.seek(0)
        writer = PdfWriter()
        writer.append(src)
        writer.append(PdfReader(appendix))
        writer.add_metadata({
            "/Title": "LoanHub reviewed Wacom evidence - NOT SIGNED",
            "/Subject": "Preview package; no final authorization or execution",
        })
        out = io.BytesIO()
        writer.write(out)
        result = out.getvalue()
        if len(result) > MAX_SOURCE_PDF + 5 * 1024 * 1024:
            raise ValueError("Evidence package exceeds output size policy")
        return result, _digest(result)
    except (ValueError, TypeError, KeyError, OSError, UnidentifiedImageError) as exc:
        raise HTTPException(422, "Unable to safely render Wacom evidence PDF") from exc
