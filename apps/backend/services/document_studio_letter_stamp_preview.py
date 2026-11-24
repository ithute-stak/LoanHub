"""Non-authoritative, opt-in visual company stamp for Document Studio PDF previews.

This deliberately does NOT issue an official document, approve a stamp, or
produce a QR verification claim. Only use to preview the layout of unsigned
company-owned client letters. The production default is disabled.
"""
from __future__ import annotations

from html import escape
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, Paragraph, Spacer, Table, TableStyle

from services.client_document_template_service import CLIENT_LETTER_TEMPLATE_KEYS

# Ordinary correspondence also uses Document Studio, not client-loan templates.
PREVIEW_LETTER_TEMPLATE_KEYS = CLIENT_LETTER_TEMPLATE_KEYS | {
    "formal_letter", "business_letter",
}

from services.company_stamp_configuration import stamp_from_company


def letter_stamp_preview_story(*, document, company):
    """Render below the letter body, never overlay existing signatures/text."""
    if getattr(document, "template_key", None) not in PREVIEW_LETTER_TEMPLATE_KEYS:
        return []
    if (getattr(document, "finalized_at", None) is not None
            or getattr(document, "status", "draft") not in ("draft",)):
        raise PermissionError("Only unsigned draft letters may show stamp previews")
    tenant_id = getattr(document, "company_id", None)
    if not isinstance(tenant_id, UUID) or company is None or getattr(company, "id", None) != tenant_id:
        raise PermissionError("Letter company stamp must belong to document tenant")
    stamp = stamp_from_company(company, authenticated_tenant_id=tenant_id)

    center = ParagraphStyle(
        "LetterStampPreviewCentre", fontName="Helvetica-Bold",
        fontSize=9, leading=11, alignment=1, textColor=colors.HexColor("#334155"),
    )
    detail = ParagraphStyle(
        "LetterStampPreviewDetail", fontName="Helvetica",
        fontSize=7.5, leading=10, alignment=1,
        textColor=colors.HexColor("#475569"),
    )
    warning = ParagraphStyle(
        "LetterStampPreviewWarning", fontName="Helvetica-Bold",
        fontSize=7, leading=9, alignment=1,
        textColor=colors.HexColor("#9A3412"),
    )
    def clean(value):
        return escape(" ".join(str(value).split()))

    details = [stamp.registration_number, stamp.license_number, stamp.address]
    details = [value for value in details if value]
    cells = [
        [Paragraph("COMPANY STAMP — PREVIEW", center)],
        [Paragraph(clean(stamp.legal_name), center)],
        [Paragraph(clean(" · ".join(details)), detail)],
        [Paragraph("NOT APPROVED OR VERIFIED — VISUAL PREVIEW ONLY", warning)],
    ]
    seal = Table(cells, colWidths=[91 * mm], hAlign="RIGHT")
    seal.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 1.25, colors.HexColor("#64748B")),
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("TOPPADDING", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, -1), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
    ]))
    return [KeepTogether([Spacer(1, 7 * mm), seal])]
