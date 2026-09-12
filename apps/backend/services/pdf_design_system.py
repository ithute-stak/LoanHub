from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from io import BytesIO
from typing import Any, Iterable, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.company import LoanCompany
from services.document_branding_service import get_company_branding_logos

PAGE_WIDTH, PAGE_HEIGHT = A4
CONTENT_WIDTH = 174 * mm

NAVY = colors.HexColor("#0F2742")
INK = colors.HexColor("#172033")
BLUE = colors.HexColor("#1268B3")
TEAL = colors.HexColor("#0F766E")
GREEN = colors.HexColor("#15803D")
AMBER = colors.HexColor("#B45309")
RED = colors.HexColor("#B91C1C")
MUTED = colors.HexColor("#5E6B7A")
BORDER = colors.HexColor("#D4DEE8")
SOFT_BLUE = colors.HexColor("#EDF6FF")
SOFT_GREEN = colors.HexColor("#ECFDF3")
SOFT_AMBER = colors.HexColor("#FFF7E8")
SOFT_RED = colors.HexColor("#FFF0F0")
SOFT_SLATE = colors.HexColor("#F6F8FB")
WHITE = colors.white

MONEY = Decimal("0.01")


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def money_text(value: Any, currency: str = "LSL") -> str:
    return f"{(currency or 'LSL').upper()} {money(value):,.2f}"


def humanize(value: Any) -> str:
    raw = value.value if hasattr(value, "value") else str(value or "")
    return raw.replace("_", " ").strip().title() or "Not recorded"


def safe_text(value: Any, fallback: str = "Not recorded") -> str:
    text = str(value or "").strip()
    return text or fallback


def date_text(value: Any, fallback: str = "Not recorded") -> str:
    if value is None:
        return fallback
    try:
        return value.strftime("%d %B %Y")
    except AttributeError:
        return str(value)


def datetime_text(value: Any, fallback: str = "Not recorded") -> str:
    if value is None:
        return fallback
    try:
        return value.strftime("%d %B %Y %H:%M UTC")
    except AttributeError:
        return str(value)


def _draw_fitted_image(canvas, image_bytes: bytes, x: float, y: float, max_w: float, max_h: float, *, align: str = "left") -> None:
    try:
        reader = ImageReader(BytesIO(image_bytes))
        image_w, image_h = reader.getSize()
        if not image_w or not image_h:
            return
        scale = min(max_w / float(image_w), max_h / float(image_h))
        draw_w = image_w * scale
        draw_h = image_h * scale
        draw_x = x
        if align == "right":
            draw_x = x + max_w - draw_w
        elif align == "center":
            draw_x = x + (max_w - draw_w) / 2
        draw_y = y + (max_h - draw_h) / 2
        canvas.drawImage(reader, draw_x, draw_y, width=draw_w, height=draw_h, mask="auto")
    except Exception:
        return


@dataclass(frozen=True)
class DocumentContext:
    db: Session | None
    company: LoanCompany | None
    title: str
    reference: str
    footer_note: str = "Generated securely by LoanHub"
    confidential: bool = True


def draw_page_chrome(canvas, doc, context: DocumentContext) -> None:
    """Draw a fixed dual-brand header and footer without touching the content frame."""
    logos = get_company_branding_logos(context.db, context.company)
    canvas.saveState()

    # Header logo boxes are deliberately isolated from company metadata so a wide
    # uploaded logo can never collide with the company name, licence or reference.
    left_x = 17 * mm
    right_x = PAGE_WIDTH - 55 * mm
    logo_y = PAGE_HEIGHT - 23.5 * mm
    logo_h = 11.5 * mm
    if logos.left_logo:
        _draw_fitted_image(canvas, logos.left_logo, left_x, logo_y, 38 * mm, logo_h, align="left")
    else:
        canvas.setFont("Helvetica-Bold", 14)
        canvas.setFillColor(NAVY)
        canvas.drawString(left_x, PAGE_HEIGHT - 16 * mm, settings.PRODUCT_NAME)

    if logos.right_logo:
        _draw_fitted_image(canvas, logos.right_logo, right_x, logo_y, 38 * mm, logo_h, align="right")
    else:
        initials = "".join(part[0] for part in safe_text(getattr(context.company, "name", None), "Company").split()[:3]).upper()
        canvas.setFillColor(SOFT_BLUE)
        canvas.roundRect(PAGE_WIDTH - 36 * mm, PAGE_HEIGHT - 23 * mm, 18 * mm, 11 * mm, 2.5 * mm, fill=1, stroke=0)
        canvas.setFillColor(BLUE)
        canvas.setFont("Helvetica-Bold", 8.5)
        canvas.drawCentredString(PAGE_WIDTH - 27 * mm, PAGE_HEIGHT - 18.6 * mm, initials or "CO")

    center_x = PAGE_WIDTH / 2
    canvas.setFillColor(NAVY)
    canvas.setFont("Helvetica-Bold", 9.5)
    canvas.drawCentredString(center_x, PAGE_HEIGHT - 11.5 * mm, safe_text(getattr(context.company, "name", None), "Loan company")[:54])
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 7.2)
    licence = safe_text(getattr(context.company, "license_number", None), "Not recorded")
    canvas.drawCentredString(center_x, PAGE_HEIGHT - 16.3 * mm, f"Licence: {licence}"[:72])
    canvas.setFont("Helvetica-Bold", 6.9)
    canvas.drawCentredString(center_x, PAGE_HEIGHT - 21.1 * mm, context.title.upper()[:72])

    canvas.setStrokeColor(BLUE)
    canvas.setLineWidth(1.1)
    canvas.line(17 * mm, PAGE_HEIGHT - 29 * mm, PAGE_WIDTH - 17 * mm, PAGE_HEIGHT - 29 * mm)

    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.55)
    canvas.line(17 * mm, 14 * mm, PAGE_WIDTH - 17 * mm, 14 * mm)
    canvas.setFillColor(MUTED)
    canvas.setFont("Helvetica", 6.7)
    prefix = "CONFIDENTIAL | " if context.confidential else ""
    canvas.drawString(17 * mm, 9.5 * mm, f"{prefix}{context.reference}"[:78])
    canvas.drawCentredString(PAGE_WIDTH / 2, 9.5 * mm, context.footer_note[:70])
    canvas.drawRightString(PAGE_WIDTH - 17 * mm, 9.5 * mm, f"Page {doc.page}")
    canvas.restoreState()


def document_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "hero": ParagraphStyle(
            "DocHero",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=25,
            textColor=NAVY,
            alignment=TA_LEFT,
            spaceAfter=2.5 * mm,
        ),
        "hero_subtitle": ParagraphStyle(
            "DocHeroSubtitle",
            parent=base["BodyText"],
            fontSize=9.3,
            leading=13,
            textColor=MUTED,
            spaceAfter=4 * mm,
        ),
        "reference": ParagraphStyle(
            "DocReference",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10,
            textColor=BLUE,
        ),
        "section": ParagraphStyle(
            "DocSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12.2,
            leading=15,
            textColor=NAVY,
            spaceBefore=3 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        "section_note": ParagraphStyle(
            "DocSectionNote",
            parent=base["BodyText"],
            fontSize=8.1,
            leading=11,
            textColor=MUTED,
            spaceAfter=2.5 * mm,
        ),
        "body": ParagraphStyle(
            "DocBody",
            parent=base["BodyText"],
            fontSize=9,
            leading=13,
            textColor=INK,
        ),
        "body_small": ParagraphStyle(
            "DocBodySmall",
            parent=base["BodyText"],
            fontSize=7.7,
            leading=10.4,
            textColor=MUTED,
        ),
        "label": ParagraphStyle(
            "DocLabel",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=9,
            textColor=MUTED,
            spaceAfter=1.2 * mm,
        ),
        "value": ParagraphStyle(
            "DocValue",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10.4,
            leading=13,
            textColor=NAVY,
        ),
        "metric_label": ParagraphStyle(
            "DocMetricLabel",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=7.1,
            leading=8.6,
            textColor=MUTED,
            spaceAfter=1.5 * mm,
        ),
        "metric_value": ParagraphStyle(
            "DocMetricValue",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=13.5,
            leading=16,
            textColor=NAVY,
        ),
        "metric_note": ParagraphStyle(
            "DocMetricNote",
            parent=base["BodyText"],
            fontSize=6.8,
            leading=8.5,
            textColor=MUTED,
        ),
        "timeline_title": ParagraphStyle(
            "DocTimelineTitle",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.4,
            leading=11.5,
            textColor=NAVY,
        ),
        "timeline_body": ParagraphStyle(
            "DocTimelineBody",
            parent=base["BodyText"],
            fontSize=8.1,
            leading=11.2,
            textColor=INK,
        ),
        "formula": ParagraphStyle(
            "DocFormula",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.3,
            leading=10,
            textColor=colors.HexColor("#0B3B65"),
        ),
        "right": ParagraphStyle(
            "DocRight",
            parent=base["BodyText"],
            alignment=TA_RIGHT,
            fontSize=8,
            leading=10,
            textColor=INK,
        ),
        "center": ParagraphStyle(
            "DocCenter",
            parent=base["BodyText"],
            alignment=TA_CENTER,
            fontSize=8,
            leading=10,
            textColor=INK,
        ),
    }


def build_document(
    *,
    story: list[Any],
    context: DocumentContext,
    title: str,
    author: str | None = None,
    subject: str | None = None,
) -> bytes:
    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=38 * mm,
        bottomMargin=19 * mm,
        title=title,
        author=author or f"{settings.PRODUCT_NAME} by {settings.DEVELOPER_NAME}",
        subject=subject or title,
        creator=f"{settings.PRODUCT_NAME} by {settings.DEVELOPER_NAME}",
    )

    def draw(canvas, doc):
        draw_page_chrome(canvas, doc, context)

    document.build(story, onFirstPage=draw, onLaterPages=draw)
    return buffer.getvalue()


def hero_block(title: str, subtitle: str, reference: str, *, status: str | None = None, styles: dict[str, ParagraphStyle] | None = None) -> list[Any]:
    styles = styles or document_styles()
    right = Paragraph(
        f"<b>{humanize(status)}</b>" if status else "",
        ParagraphStyle(
            "HeroStatus",
            parent=styles["reference"],
            alignment=TA_RIGHT,
            textColor=GREEN if str(status or "").lower() in {"active", "approved", "paid", "completed", "signed", "succeeded"} else BLUE,
        ),
    )
    meta = Table(
        [[Paragraph(reference, styles["reference"]), right]],
        colWidths=[122 * mm, 52 * mm],
    )
    meta.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [
        Paragraph(title, styles["hero"]),
        meta,
        Spacer(1, 1.5 * mm),
        Paragraph(subtitle, styles["hero_subtitle"]),
    ]


def section(title: str, note: str | None = None, *, styles: dict[str, ParagraphStyle] | None = None) -> list[Any]:
    styles = styles or document_styles()
    items: list[Any] = [Paragraph(title, styles["section"])]
    if note:
        items.append(Paragraph(note, styles["section_note"]))
    return items


def _tone(tone: str) -> tuple[colors.Color, colors.Color]:
    return {
        "green": (SOFT_GREEN, GREEN),
        "amber": (SOFT_AMBER, AMBER),
        "red": (SOFT_RED, RED),
        "slate": (SOFT_SLATE, NAVY),
        "teal": (colors.HexColor("#EAFBF8"), TEAL),
    }.get(tone, (SOFT_BLUE, BLUE))


def metric_card(label: str, value: str, note: str | None = None, *, tone: str = "blue", width: float = 84 * mm, styles: dict[str, ParagraphStyle] | None = None) -> Table:
    styles = styles or document_styles()
    background, accent = _tone(tone)
    value_style = ParagraphStyle(
        f"MetricValue{tone}{id(value)}",
        parent=styles["metric_value"],
        textColor=accent,
    )
    rows = [
        [Paragraph(label.upper(), styles["metric_label"])],
        [Paragraph(value, value_style)],
    ]
    if note:
        rows.append([Paragraph(note, styles["metric_note"])])
    table = Table(rows, colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.7, accent),
        ("LINEBEFORE", (0, 0), (0, -1), 3.2, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def metric_grid(items: Sequence[tuple[str, str, str | None, str]], *, columns: int = 2, styles: dict[str, ParagraphStyle] | None = None) -> Table:
    styles = styles or document_styles()
    columns = max(1, min(columns, 4))
    gap = 4 * mm
    card_width = (CONTENT_WIDTH - gap * (columns - 1)) / columns
    rows: list[list[Any]] = []
    current: list[Any] = []
    for label, value, note, tone in items:
        current.append(metric_card(label, value, note, tone=tone, width=card_width, styles=styles))
        if len(current) == columns:
            rows.append(current)
            current = []
    if current:
        current.extend(["" for _ in range(columns - len(current))])
        rows.append(current)
    outer = Table(rows, colWidths=[card_width] * columns, hAlign="LEFT")
    outer.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), gap if columns > 1 else 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
    ]))
    return outer


def detail_card(title: str, pairs: Sequence[tuple[str, str]], *, tone: str = "slate", width: float = 84 * mm, styles: dict[str, ParagraphStyle] | None = None) -> Table:
    styles = styles or document_styles()
    background, accent = _tone(tone)
    contents: list[Any] = [Paragraph(title, styles["timeline_title"]), Spacer(1, 1.8 * mm)]
    for label, value in pairs:
        row = Table(
            [[Paragraph(label, styles["label"]), Paragraph(value, styles["right"]) ]],
            colWidths=[width * 0.42, width * 0.52],
        )
        row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 1.8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8),
            ("LINEBELOW", (0, 0), (-1, -1), 0.35, BORDER),
        ]))
        contents.append(row)
    table = Table([[contents]], colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.7, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def two_card_row(left: Any, right: Any) -> Table:
    gap = 5 * mm
    width = (CONTENT_WIDTH - gap) / 2
    table = Table([[left, right]], colWidths=[width, width])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
        ("RIGHTPADDING", (0, 0), (0, -1), gap),
        ("LEFTPADDING", (1, 0), (1, -1), 0),
        ("RIGHTPADDING", (1, 0), (1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return table


def callout(title: str, text: str, *, tone: str = "blue", styles: dict[str, ParagraphStyle] | None = None) -> Table:
    styles = styles or document_styles()
    background, accent = _tone(tone)
    table = Table(
        [[Paragraph(title, styles["timeline_title"]), Paragraph(text, styles["timeline_body"]) ]],
        colWidths=[42 * mm, 132 * mm],
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.75, accent),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def timeline_card(
    number: str,
    title: str,
    body: str,
    *,
    meta: str | None = None,
    status: str | None = None,
    tone: str = "blue",
    formula_lines: Iterable[str] | None = None,
    styles: dict[str, ParagraphStyle] | None = None,
) -> Table:
    styles = styles or document_styles()
    background, accent = _tone(tone)
    badge = Table([[Paragraph(number, ParagraphStyle(
        f"TimelineBadge{number}{id(title)}",
        parent=styles["center"],
        fontName="Helvetica-Bold",
        textColor=WHITE,
        fontSize=8.2,
        leading=10,
    ))]], colWidths=[10 * mm], rowHeights=[10 * mm])
    badge.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), accent),
        ("BOX", (0, 0), (-1, -1), 0.5, accent),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    header_text = title
    if status:
        header_text += f" <font color='{accent.hexval()}'><b>- {humanize(status)}</b></font>"
    content: list[Any] = [Paragraph(header_text, styles["timeline_title"])]
    if meta:
        content.append(Paragraph(meta, styles["body_small"]))
        content.append(Spacer(1, 1 * mm))
    content.append(Paragraph(body, styles["timeline_body"]))
    if formula_lines:
        content.append(Spacer(1, 1.5 * mm))
        for line in formula_lines:
            content.append(Paragraph(line, styles["formula"]))
    card = Table([[badge, content]], colWidths=[14 * mm, 158 * mm])
    card.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), background),
        ("BOX", (0, 0), (-1, -1), 0.65, BORDER),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, accent),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 7),
        ("RIGHTPADDING", (0, 0), (0, -1), 4),
        ("LEFTPADDING", (1, 0), (1, -1), 5),
        ("RIGHTPADDING", (1, 0), (1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return card


def progress_bar(label: str, value: float, *, note: str = "", tone: str = "blue", styles: dict[str, ParagraphStyle] | None = None) -> Table:
    styles = styles or document_styles()
    _, accent = _tone(tone)
    clamped = max(0.0, min(float(value), 100.0))
    total_width = 120 * mm
    filled = total_width * clamped / 100
    remaining = total_width - filled
    bar = Table([["", ""]], colWidths=[filled, remaining], rowHeights=[4 * mm])
    bar.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), accent),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#E7EDF4")),
        ("BOX", (0, 0), (-1, -1), 0.4, BORDER),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    row = Table(
        [[Paragraph(f"<b>{label}</b>", styles["body_small"]), bar, Paragraph(f"<b>{clamped:,.1f}%</b><br/>{note}", styles["right"]) ]],
        colWidths=[32 * mm, 120 * mm, 22 * mm],
    )
    row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return row


def generated_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("Generated %d %B %Y %H:%M UTC")
