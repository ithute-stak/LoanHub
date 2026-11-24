"""Fail-closed backend PDF stamping primitives for LoanHub tenant documents.

This module does not issue documents, persist proofs, or make a QR authoritative.
Callers must persist immutable final-PDF bytes and their SHA-256 in a tenant-scoped
issuance registry before publishing the document as verified.
"""
from __future__ import annotations

import hashlib
import hmac
import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from pypdf import PdfReader, PdfWriter
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas


class DocumentStampError(ValueError):
    """Document cannot be safely prepared for issuance."""


@dataclass(frozen=True)
class StampCompany:
    tenant_id: str
    name: str
    registration_number: str
    address: str
    phone: str
    email: str

    @classmethod
    def from_company(cls, company):
        """Use the active tenant's approved canonical Company Configuration."""
        if company is None or getattr(company, "id", None) is None:
            raise DocumentStampError("An authenticated tenant company is required")
        return cls(
            tenant_id=str(company.id),
            name=str(getattr(company, "name", "") or "").strip(),
            registration_number=str(getattr(company, "registration_number", "") or "").strip(),
            address=str(getattr(company, "address", "") or "").strip(),
            phone=str(getattr(company, "phone", "") or "").strip(),
            email=str(getattr(company, "email", "") or "").strip(),
        )

    def validate(self) -> None:
        for field in ("tenant_id", "name", "registration_number", "address", "phone", "email"):
            value = getattr(self, field)
            if not value or len(value) > 500 or any(ord(c) < 32 for c in value):
                raise DocumentStampError(f"Missing or unsafe approved company field: {field}")
        if "@" not in self.email:
            raise DocumentStampError("Company email is invalid")


def _verification_url(base_url: str, public_id: str) -> str:
    """Never allow untrusted hosts, arbitrary paths, or guessable short IDs."""
    parsed = urlsplit(base_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise DocumentStampError("Verification origin must be a configured HTTPS origin")
    if not re.fullmatch(r"[A-Za-z0-9_-]{22,128}", public_id):
        raise DocumentStampError("Public document ID must be a high-entropy token")
    return f"{base_url.rstrip('/')}/verify/{public_id}"


def sha256_pdf(pdf: bytes) -> str:
    if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF-") or len(pdf) > 25 * 1024 * 1024:
        raise DocumentStampError("Invalid or oversized PDF")
    return hashlib.sha256(pdf).hexdigest()


def verify_exact_pdf(pdf: bytes, stored_sha256: str) -> bool:
    """True only for exact final artifact bytes; a copied QR is insufficient."""
    if not re.fullmatch(r"[0-9a-f]{64}", stored_sha256 or ""):
        return False
    try:
        return hmac.compare_digest(sha256_pdf(pdf), stored_sha256)
    except DocumentStampError:
        return False


def _draw_safe_line(canvas: Canvas, value: str, x: float, y: float, width: float) -> None:
    """Draw a bounded text line; no user-supplied rich text or PDF instructions."""
    canvas.setFont("Helvetica", 8.5)
    text = value
    while text and canvas.stringWidth(text, "Helvetica", 8.5) > width:
        text = text[:-1]
    canvas.drawString(x, y, text)


def _certificate_page(company: StampCompany, public_id: str, url: str, when: datetime) -> bytes:
    out = BytesIO()
    c = Canvas(out, pagesize=A4)
    w, h = A4
    ink = colors.HexColor("#3C5790")
    c.setStrokeColor(ink)
    c.setLineWidth(1.5)
    c.rect(18 * mm, 90 * mm, w - 36 * mm, h - 135 * mm)
    c.setFillColor(ink)
    c.setFont("Helvetica-Bold", 15)
    c.drawCentredString(w / 2, h - 60 * mm, "COMPANY DOCUMENT STAMP")
    c.setFont("Helvetica-Bold", 12)
    c.drawCentredString(w / 2, h - 74 * mm, company.name[:60])
    x = 28 * mm
    entries = (
        ("Registration number", company.registration_number),
        ("Physical address", company.address),
        ("Telephone", company.phone),
        ("Email", company.email),
        ("Issued (Africa/Maseru)", when.astimezone(ZoneInfo("Africa/Maseru")).strftime("%d %b %Y %H:%M:%S %Z")),
        ("Document identifier", public_id),
    )
    y = h - 95 * mm
    for title, value in entries:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x, y, title)
        _draw_safe_line(c, value, x, y - 6 * mm, w - 60 * mm)
        y -= 18 * mm
    code = qr.QrCodeWidget(url)
    bounds = code.getBounds()
    width, height = bounds[2] - bounds[0], bounds[3] - bounds[1]
    size = 40 * mm
    drawing = Drawing(size, size, transform=[size / width, 0, 0, size / height, 0, 0])
    drawing.add(code)
    renderPDF.draw(drawing, c, 28 * mm, 110 * mm)
    c.setFont("Helvetica-Bold", 8)
    c.drawString(76 * mm, 136 * mm, "Verify document with LoanHub")
    c.setFont("Helvetica", 7)
    c.drawString(76 * mm, 130 * mm, "QR lookup alone does not prove a PDF is unchanged.")
    c.drawString(76 * mm, 125 * mm, "Compare the actual file against the official checksum.")
    c.setFont("Helvetica", 6.5)
    _draw_safe_line(c, url, 28 * mm, 101 * mm, w - 56 * mm)
    c.setFont("Helvetica-Bold", 7)
    c.drawString(22 * mm, 67 * mm, "An illustrated stamp is not a cryptographic PDF signature.")
    c.drawString(22 * mm, 61 * mm, "Authenticity requires server-side issuance, exact-file verification, and status checks.")
    c.showPage()
    c.save()
    return out.getvalue()


def prepare_stamped_pdf(
    source_pdf: bytes,
    *,
    company: StampCompany,
    public_id: str,
    verification_origin: str,
    issued_at: datetime,
) -> tuple[bytes, str]:
    """Append a non-overlapping full company stamp/security page.

    Returns bytes and SHA-256. Caller must store both atomically with a
    tenant-bound issuance record and must NEVER advertise successful verification
    until that persistence succeeds. Source signed PDFs must not be modified.
    """
    company.validate()
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise DocumentStampError("Issue time must be timezone-aware")
    url = _verification_url(verification_origin, public_id)
    sha256_pdf(source_pdf)
    try:
        reader = PdfReader(BytesIO(source_pdf), strict=True)
        if reader.is_encrypted or not reader.pages or len(reader.pages) > 250:
            raise DocumentStampError("Encrypted, empty, or oversized PDF page set")
        writer = PdfWriter()
        writer.append_pages_from_reader(reader)
        certificate = PdfReader(BytesIO(_certificate_page(company, public_id, url, issued_at)))
        writer.add_page(certificate.pages[0])
        writer.add_metadata({"/Producer": "LoanHub tenant document stamping"})
        output = BytesIO()
        writer.write(output)
        result = output.getvalue()
    except DocumentStampError:
        raise
    except Exception as exc:
        raise DocumentStampError("PDF stamp preparation failed") from exc
    return result, sha256_pdf(result)
