"""Branded PDF for live LoanHub CDAS operation history, not a CDAS portal export."""
from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from services.document_branding_service import draw_brand_header, draw_brand_footer


def build_cdas_history_pdf(*, db, company, entries: list[dict], environment: str) -> bytes:
    """Render company-scoped live ledger entries with LoanHub's actual dual-logo header."""
    buffer = BytesIO()
    page_size = landscape(A4)
    width, height = page_size
    doc = SimpleDocTemplate(
        buffer, pagesize=page_size,
        leftMargin=18*mm, rightMargin=18*mm,
        topMargin=52*mm, bottomMargin=22*mm,
        title="LoanHub CDAS operations history",
    )
    heading = ParagraphStyle("cdasHeading", fontName="Helvetica-Bold", fontSize=10,
                             leading=13, textColor=colors.HexColor("#0F2742"), spaceAfter=8)
    body = ParagraphStyle("cdasBody", fontName="Helvetica", fontSize=7.2,
                          leading=10, textColor=colors.HexColor("#172033"))
    th = ParagraphStyle("cdasHead", parent=body, fontName="Helvetica-Bold", textColor=colors.white)
    note = ParagraphStyle("cdasNote", parent=body, fontSize=8, leading=12, spaceAfter=12)

    def p(value, style=body):
        return Paragraph(escape(str(value if value is not None else "—")), style)

    story = [
        Paragraph("CDAS operations and transaction ledger", heading),
        Paragraph(
            "Live LoanHub ledger data (not the CDAS provider portal's full Transaction History export). "
            "Rows may include attempts, pending results, failures and metered transactions. "
            "Do not interpret these records as current active deductions.", note),
        Paragraph(f"Environment: {escape(environment)}  |  Records in report: {len(entries)}", note),
    ]
    columns = ["Date / time", "Source", "Operation", "State", "Employee no.", "Reference", "Provider status"]
    col_widths = [38, 37, 39, 31, 31, 54, 31]
    total_width = width-36*mm
    widths = [n*total_width/sum(col_widths) for n in col_widths]
    rows = [[p(x, th) for x in columns]]
    for item in entries:
        timestamp = item.get("occurred_at")
        if hasattr(timestamp, "strftime"):
            timestamp = timestamp.strftime("%Y-%m-%d %H:%M")
        rows.append([p(timestamp), p(item.get("source")), p(item.get("operation_type")),
                     p(item.get("state")), p(item.get("employee_no")), p(item.get("reference_no")),
                     p(item.get("provider_status_code"))])
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#0F2742")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F4F7FB")]),
        ("LINEBELOW", (0,0), (-1,-1), .3, colors.HexColor("#D4DEE8")),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("TOPPADDING", (0,0), (-1,-1), 6),
        ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
    ]))
    story.append(table)

    def page(canvas, template):
        draw_brand_header(canvas, db=db, company=company,
                          title="CDAS OPERATIONS HISTORY", subtitle="Live LoanHub CDAS ledger",
                          width=width, height=height)
        draw_brand_footer(canvas, template, reference_text="CDAS-OPERATIONS",
                          note_text="LoanHub Document Studio | Confidential", width=width)

    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()
