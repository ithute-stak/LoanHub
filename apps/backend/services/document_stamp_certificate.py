"""Tenant-specific *visual* stamp renderer for PDF documents.

A visual stamp is NOT proof of authenticity. Official verification additionally
requires an immutable issuance record, exact-byte digest, and revocation check.
This module intentionally performs no issuance or approval side effects.

Never use on already digitally signed PDFs: adding pages would invalidate their
signature. Apply before handing a document to IthuteSign.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from urllib.parse import urlparse
from uuid import UUID

from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderPDF


MAX_SOURCE_BYTES = 20 * 1024 * 1024
MAX_SOURCE_PAGES = 100
MAX_FIELD_LENGTH = 250


@dataclass(frozen=True)
class TenantStamp:
    tenant_id: UUID
    legal_name: str
    address: str
    phones: str
    email: str
    registration_number: str = ""
    license_number: str = ""

    def validate(self) -> None:
        for field in ("legal_name", "address", "phones", "email"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip() or len(value) > MAX_FIELD_LENGTH:
                raise ValueError(f"Invalid company {field}")
        for field in ("registration_number", "license_number"):
            value = getattr(self, field)
            if not isinstance(value, str) or len(value) > MAX_FIELD_LENGTH:
                raise ValueError(f"Invalid company {field}")
        if "\n" in self.email or "\r" in self.email or "@" not in self.email:
            raise ValueError("Invalid company email")


def _fit(c: canvas.Canvas, value: str, *, x: float, y: float, maximum: float) -> None:
    """Use wrapped lines rather than truncating approved tenant details."""
    text = " ".join(value.split())
    words = text.split()
    line = ""
    lines = []
    for word in words:
        candidate = (line + " " + word).strip()
        if c.stringWidth(candidate, "Helvetica", 8) > maximum and line:
            lines.append(line)
            line = word
        else:
            line = candidate
    if line:
        lines.append(line)
    if len(lines) > 4 or any(c.stringWidth(s, "Helvetica", 8) > maximum for s in lines):
        raise ValueError("Company stamp field does not fit")
    for part in lines:
        c.drawString(x, y, part)
        y -= 11
    return y


def render_tenant_stamp_certificate(
    *, source_pdf: bytes, stamp: TenantStamp, public_id: str,
    verification_url: str, issued_at: datetime, expected_tenant_id: UUID,
    trusted_verification_host: str,
) -> bytes:
    """Append a clearly identified, unverified-until-registered company certificate.

    The caller MUST validate and persist the issuance before releasing this PDF.
    The caller MUST calculate SHA-256 on these returned bytes. Do not embed that
    hash into these same bytes (self-referential checksum).
    """
    stamp.validate()
    if stamp.tenant_id != expected_tenant_id:
        raise PermissionError("Company stamp belongs to another tenant")
    if not isinstance(issued_at, datetime) or issued_at.utcoffset() is None:
        raise ValueError("Issued timestamp must be timezone-aware")
    if not isinstance(public_id, str) or not (12 <= len(public_id) <= 96) or not all(
        c.isascii() and (c.isalnum() or c in "-_") for c in public_id
    ):
        raise ValueError("Invalid public verification ID")
    parsed = urlparse(verification_url)
    if (parsed.scheme != "https" or parsed.netloc != trusted_verification_host
            or not trusted_verification_host or parsed.username
            or parsed.password or parsed.query or parsed.fragment
            or not parsed.path.endswith("/verify/" + public_id)):
        raise ValueError("Untrusted verification URL")
    if not isinstance(source_pdf, bytes) or not source_pdf.startswith(b"%PDF-") or len(source_pdf) > MAX_SOURCE_BYTES:
        raise ValueError("Invalid PDF source")
    try:
        reader = PdfReader(BytesIO(source_pdf), strict=True)
        if reader.is_encrypted or not (1 <= len(reader.pages) <= MAX_SOURCE_PAGES):
            raise ValueError("Encrypted or oversized PDF")
        # This must only be applied to unsigned source PDFs.
        if "/AcroForm" in reader.trailer["/Root"]:
            fields = reader.get_fields() or {}
            if any(field.get("/FT") == "/Sig" for field in fields.values()):
                raise ValueError("Signed PDF must not be rewritten")
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        buf = BytesIO()
        c = canvas.Canvas(buf, pagesize=(210 * mm, 297 * mm))
        c.setTitle("LoanHub document issuer information")
        c.setFont("Helvetica-Bold", 16)
        c.setFillColor(colors.HexColor("#19365F"))
        c.drawString(18 * mm, 267 * mm, "DOCUMENT ISSUANCE CERTIFICATE")
        c.setFont("Helvetica", 9)
        c.drawString(18 * mm, 257 * mm, "Company-issued document details and verification reference")
        c.setStrokeColor(colors.HexColor("#3E5C99"))
        c.rect(16 * mm, 92 * mm, 178 * mm, 153 * mm, fill=0, stroke=1)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(22 * mm, 230 * mm, "ISSUING COMPANY")
        c.setFont("Helvetica", 8)
        y = 218 * mm
        for label, value in (
            ("Legal name", stamp.legal_name),
            ("Registration", stamp.registration_number or "Not configured"),
            ("Licence", stamp.license_number or "Not configured"),
            ("Address", stamp.address),
            ("Telephone", stamp.phones),
            ("Email", stamp.email),
        ):
            c.setFont("Helvetica-Bold", 8)
            c.drawString(22 * mm, y, label + ":")
            c.setFont("Helvetica", 8)
            y = _fit(c, value, x=49 * mm, y=y, maximum=137 * mm) - 8
        if y < 119 * mm:
            raise ValueError("Company stamp details exceed certificate space")
        c.setFont("Helvetica-Bold", 9)
        c.drawString(22 * mm, 116 * mm, "Issued: " + issued_at.isoformat())
        c.drawString(22 * mm, 107 * mm, "Reference: " + public_id)
        qr_code = qr.QrCodeWidget(verification_url)
        bounds = qr_code.getBounds()
        drawing = Drawing(29 * mm, 29 * mm, transform=[
            29 * mm / (bounds[2] - bounds[0]), 0, 0,
            29 * mm / (bounds[3] - bounds[1]), 0, 0,
        ])
        drawing.add(qr_code)
        renderPDF.draw(drawing, c, 22 * mm, 56 * mm)
        c.setFont("Helvetica", 8)
        c.drawString(56 * mm, 81 * mm, "Scan to check issuance and revocation status.")
        c.drawString(56 * mm, 75 * mm, "A QR code alone does not authenticate PDF contents.")
        c.drawString(56 * mm, 69 * mm, "Use the LoanHub exact-file verification service.")
        c.setFont("Helvetica", 7)
        c.drawString(18 * mm, 32 * mm, "This is a visible issuer mark, NOT a cryptographic PDF signature.")
        c.drawString(18 * mm, 26 * mm, "Authenticity requires an authoritative issuance record and exact-file digest check.")
        c.save()
        buf.seek(0)
        writer.add_page(PdfReader(buf, strict=True).pages[0])
        out = BytesIO()
        writer.write(out)
        result = out.getvalue()
        if len(PdfReader(BytesIO(result), strict=True).pages) != len(reader.pages) + 1:
            raise ValueError("PDF certificate integrity error")
        return result
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Invalid PDF structure") from exc
