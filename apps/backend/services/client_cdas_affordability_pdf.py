"""Render a tenant-branded, point-in-time CDAS affordability assessment."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from services.document_branding_service import draw_brand_header, draw_brand_footer


def build_client_cdas_affordability_pdf(
    *, db, company, client_name: str, client_reference: str,
    employee_no: str, employee: dict, affordability: Decimal,
    deductions: list[dict], assessed_at: datetime, reference: str,
    environment: str,
) -> bytes:
    """Only the server-side CDAS response, never browser-entered amounts, enters this report."""
    buffer = BytesIO()
    width, height = A4
    document = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=53 * mm, bottomMargin=24 * mm,
        title="CDAS employee affordability assessment",
    )
    body = ParagraphStyle("cdas-assessment-body", fontName="Helvetica", fontSize=9,
                          leading=13, textColor=colors.HexColor("#162A40"))
    heading = ParagraphStyle("cdas-assessment-title", parent=body, fontName="Helvetica-Bold",
                             fontSize=13, leading=18, spaceAfter=10)
    small = ParagraphStyle("cdas-assessment-small", parent=body, fontSize=8, leading=11,
                           spaceAfter=8)
    strong = ParagraphStyle("cdas-assessment-bold", parent=body, fontName="Helvetica-Bold")
    table_header = ParagraphStyle("cdas-assessment-header", parent=small, fontName="Helvetica-Bold",
                                  textColor=colors.white)

    def p(value, style=body):
        return Paragraph(escape(str(value if value is not None else "Not supplied")), style)

    def money(value):
        return "M {:,.2f}".format(Decimal(str(value)).quantize(Decimal("0.01")))

    story = [
        p("Government employee affordability assessment", heading),
        p("Assessment reference: " + reference, strong),
        p("Assessment date (UTC): " + assessed_at.strftime("%Y-%m-%d %H:%M:%S") +
          "  |  CDAS environment: " + environment, small),
        Spacer(1, 5 * mm),
    ]
    identity = [
        ["LoanHub client", client_name],
        ["Client account", client_reference],
        ["CDAS employee number", employee_no],
        ["CDAS employee name", " ".join(str(employee.get(key) or "").strip()
                                      for key in ("Name", "Surname")).strip() or "Not supplied"],
        ["Department", employee.get("Department") or "Not supplied"],
        ["Date of birth", employee.get("DOB") or "Not supplied"],
    ]
    id_rows = [[p(label, strong), p(value)] for label, value in identity]
    id_table = Table(id_rows, colWidths=[48 * mm, 124 * mm], hAlign="LEFT")
    id_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#F2F6FA"), colors.white]),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#D9E2EC")),
    ]))
    story.extend([
        id_table, Spacer(1, 8 * mm),
        p("CDAS available affordability", strong),
        p(money(affordability), heading),
        p("Provider-reported available affordability at the time above. This is not a loan "
          "approval or authority to register payroll deductions. The deduction list below is "
          "informational; do not subtract it again from the provider-reported affordability.", small),
        Spacer(1, 5 * mm),
        p("Existing third-party deductions reported by CDAS", strong),
    ])
    rows = [[p(value, table_header) for value in ("Agency / description", "Status", "Amount")]]
    for row in deductions:
        agency = next((row.get(key) for key in ("AgencyName", "DeductionName", "DeductionTypeName",
                                               "ItemCode", "LoanPolicyName") if row.get(key)), "Not supplied")
        status = row.get("Status") or row.get("DeductionStatusName") or row.get("DeductionStatus") or "Not supplied"
        amount = next((row.get(key) for key in ("DeductionAmount", "Amount", "MonthlyDeduction")
                       if row.get(key) is not None), None)
        try:
            amount_text = money(amount) if amount is not None else "Not supplied"
        except (ValueError, TypeError, ArithmeticError):
            amount_text = "Not supplied"
        rows.append([p(agency, small), p(status, small), p(amount_text, small)])
    if len(rows) == 1:
        rows.append([p("No deductions returned by CDAS", small), p("—", small), p("—", small)])
    table = Table(rows, colWidths=[90 * mm, 42 * mm, 40 * mm], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#103554")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6FA")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#D9E2EC")),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 7 * mm),
                  p("Confidential borrower document. This is a point-in-time snapshot. "
                    "Reassess through CDAS before a new credit decision.", small)])

    def decorate(canvas, template):
        draw_brand_header(canvas, db=db, company=company,
                          title="CDAS AFFORDABILITY REPORT", subtitle="Employee payroll assessment",
                          width=width, height=height)
        draw_brand_footer(canvas, template, reference_text=reference,
                          note_text="LoanHub | Confidential borrower assessment", width=width)

    document.build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()
