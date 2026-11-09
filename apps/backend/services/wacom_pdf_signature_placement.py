"""Explicit-field Wacom handwriting placement PREVIEW only.

No signing endpoint, contract mutation or release authorization is exposed.
All generated pages have unmistakable NOT EXECUTED watermarking; a later
independently authorized execution transaction must generate a fresh final
document and recheck every permission under database locks.
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass

from fastapi import HTTPException
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_PNG_BYTES = 2 * 1024 * 1024
MAX_PAGES = 100
STAMP = "DRAFT WACOM PLACEMENT - NOT EXECUTED"


@dataclass(frozen=True, slots=True)
class SignatureField:
    """Explicit PDF page and field rectangle in POINTS from bottom-left.

    Not inferred from handwritten ink or guessed from document text.
    """
    page_index: int
    x: float
    y: float
    width: float
    height: float

    def validate(self, *, page_width: float, page_height: float, pages: int) -> None:
        import math
        numbers = (self.x, self.y, self.width, self.height, page_width, page_height)
        if any(not isinstance(x, (int, float)) or not math.isfinite(x) for x in numbers):
            raise ValueError("Signature rectangle has invalid dimensions")
        if isinstance(self.page_index, bool) or not isinstance(self.page_index, int):
            raise ValueError("Signature page index must be an integer")
        if self.page_index < 0 or self.page_index >= pages:
            raise ValueError("Signature placement page outside source PDF")
        if self.width < 36 or self.height < 15 or self.width > 350 or self.height > 150:
            raise ValueError("Signature field outside allowed dimensions")
        if self.x < 16 or self.y < 16 or self.x+self.width > page_width-16 or self.y+self.height > page_height-16:
            raise ValueError("Signature field outside printable page area")


def render_signature_placement_preview(
    *, source_pdf: bytes, source_sha256: str,
    handwriting_png: bytes, handwriting_sha256: str,
    field: SignatureField, expected_page_count: int,
) -> tuple[bytes, str]:
    """Pure byte transformation: returns watermarked PDF, fingerprint.

    Does not persist anything. The resulting document IS NOT signed.
    """
    if (not source_pdf or len(source_pdf) > MAX_PDF_BYTES or
        not source_pdf.startswith(b"%PDF-") or
        hashlib.sha256(source_pdf).hexdigest() != source_sha256):
        raise HTTPException(409, "Contract PDF changed or is not available")
    if (not handwriting_png or len(handwriting_png) > MAX_PNG_BYTES or
        not handwriting_png.startswith(b"\x89PNG\r\n\x1a\n") or
        hashlib.sha256(handwriting_png).hexdigest() != handwriting_sha256):
        raise HTTPException(409, "Handwriting evidence changed or is not available")
    try:
        reader = PdfReader(io.BytesIO(source_pdf), strict=True)
        if reader.is_encrypted or len(reader.pages) < 1 or len(reader.pages) > MAX_PAGES:
            raise ValueError("Unsupported source contract")
        if len(reader.pages) != expected_page_count:
            raise ValueError("Document page count changed")
        ink = Image.open(io.BytesIO(handwriting_png))
        if ink.format != "PNG" or not 2 <= ink.width <= 4000 or not 2 <= ink.height <= 4000 or ink.width*ink.height > 4_000_000:
            raise ValueError("Invalid handwriting preview")
        ink.load()
        if ink.getbbox() is None:
            raise ValueError("Blank handwriting preview")
        # Crop transparent/white background conservatively; preserve original ink geometry.
        if ink.mode not in ("RGB", "RGBA"):
            ink = ink.convert("RGBA")
        writer = PdfWriter()
        for index, original in enumerate(reader.pages):
            if int(original.get("/Rotate", 0)) % 360:
                raise ValueError("Rotated PDF pages require explicit canonicalization")
            page_width = float(original.mediabox.width)
            page_height = float(original.mediabox.height)
            if page_width <= 0 or page_height <= 0 or page_width > 2000 or page_height > 2000:
                raise ValueError("Unsupported PDF page dimensions")
            if index == field.page_index:
                field.validate(page_width=page_width, page_height=page_height, pages=len(reader.pages))
            overlay = io.BytesIO()
            c = canvas.Canvas(overlay, pagesize=(page_width, page_height))
            c.saveState()
            c.setFillColorRGB(0.65, 0.10, 0.10)
            c.setFont("Helvetica-Bold", 12)
            c.drawString(20, page_height-22, STAMP)
            c.drawString(20, 10, STAMP)
            c.restoreState()
            if index == field.page_index:
                # Fit entirely within the approved field; no clipping outside bounds.
                scale = min(field.width/ink.width, field.height/ink.height)
                width, height = ink.width*scale, ink.height*scale
                draw_x = field.x+(field.width-width)/2
                draw_y = field.y+(field.height-height)/2
                c.drawImage(ImageReader(ink), draw_x, draw_y, width=width, height=height,
                            preserveAspectRatio=True, mask="auto")
                c.setStrokeColorRGB(0.7, 0.1, 0.1)
                c.rect(field.x, field.y, field.width, field.height, stroke=1, fill=0)
            c.save()
            overlay.seek(0)
            original.merge_page(PdfReader(overlay).pages[0])
            writer.add_page(original)
        writer.add_metadata({
            "/Title": "LoanHub Wacom handwriting placement - NOT EXECUTED",
            "/Subject": "Draft preview; not a signed contract or digital signature",
        })
        out = io.BytesIO()
        writer.write(out)
        result = out.getvalue()
        if len(result) > MAX_PDF_BYTES+5*1024*1024:
            raise ValueError("Placement preview too large")
        return result, hashlib.sha256(result).hexdigest()
    except (ValueError, TypeError, KeyError, OSError, PdfReadError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, "Unable to safely place Wacom handwriting in PDF preview") from exc
