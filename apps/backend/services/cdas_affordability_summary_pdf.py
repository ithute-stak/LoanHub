"""Consolidated summary of stored CDAS affordability assessments.

Produces a management-only report without contacting CDAS. Entries are taken
from tenant-scoped persisted assessment snapshots, never from caller-supplied data.
"""
from __future__ import annotations

from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
from services.document_branding_service import draw_brand_header, draw_brand_footer


def build_government_affordability_summary_pdf(*, db, company, rows: list[dict], generated_at: str) -> bytes:
    buffer = BytesIO()
    width, height = landscape(A4)
    document = SimpleDocTemplate(
        buffer, pagesize=landscape(A4), leftMargin=16 * mm,
        rightMargin=16 * mm, topMargin=52 * mm, bottomMargin=22 * mm,
        title="LoanHub Government Employee Affordability Summary",
    )
    body = ParagraphStyle("summaryBody", fontName="Helvetica", fontSize=7.4,
                          leading=10, textColor=colors.HexColor("#14263D"))
    title = ParagraphStyle("summaryTitle", parent=body, fontName="Helvetica-Bold",
                           fontSize=12, leading=16, spaceAfter=8)
    head = ParagraphStyle("summaryHead", parent=body, fontName="Helvetica-Bold",
                          textColor=colors.white)
    def p(value, style=body):
        return Paragraph(escape(str(value if value is not None else "—")), style)

    story = [
        Paragraph("GOVERNMENT EMPLOYEE AFFORDABILITY — ASSESSMENT HISTORY", title),
        Paragraph("Confidential management summary of saved LoanHub assessments. "
                  "Not a live CDAS statement, loan approval, or payroll mandate.", body),
        Paragraph("Generated at: " + escape(generated_at), body),
    ]
    cells = [[p(x, head) for x in ("Reference", "Assessed at", "Employee no.", "CDAS capacity",
                                    "Policy limit", "Proposed instalment", "Outcome")]]
    for item in rows:
        cells.append([p(item.get(k)) for k in (
            "reference", "assessed_at", "employee_number", "cdas_capacity",
            "maximum_affordable_installment", "proposed_installment", "decision",
        )])
    if not rows:
        cells.append([p("No saved assessments in selected scope")] + [p("") for _ in range(6)])
    widths = [41, 43, 35, 34, 34, 41, 29]
    scale = (width - 32 * mm) / sum(widths)
    table = Table(cells, colWidths=[w * scale for w in widths], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F2742")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7FB")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D4DEE8")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)

    def page(canvas, template):
        draw_brand_header(
            canvas, db=db, company=company, title="AFFORDABILITY MANAGEMENT SUMMARY",
            subtitle="Saved LoanHub assessments | Confidential", width=width, height=height,
        )
        draw_brand_footer(
            canvas, template, reference_text="CDAS-AFFORDABILITY-SUMMARY",
            note_text="LoanHub | Confidential", width=width,
        )
    document.build(story, onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()
