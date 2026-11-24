import csv
import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from core.access_control import PERFORMANCE_ROLES, TRANSPARENCY_ROLES, TenantContext, get_user_context, require_tenant_roles
from database.models.enums import UserRole, LoanStatus
from database.models.client_loan_company import ClientCompanyLoan
from database.models.borrower import Borrower
from database.models.user import User
from database.models.branch import CompanyBranch
from database.models.reporting import GeneratedReport, ReportSchedule
from database.schemas.reporting import (
    GeneratedReportRead,
    ReportGenerateCreate,
    ReportScheduleCreate,
    ReportScheduleRead,
    ReportScheduleUpdate,
    ReportSummaryRead,
)
from database.session import get_db
from services.reporting_service import collect_metrics, generate_report, next_run_for_frequency


router = APIRouter(prefix="/reports", tags=["Reports"])
REPORT_ROLES = PERFORMANCE_ROLES | TRANSPARENCY_ROLES | {UserRole.FINANCE_OFFICER}


def require_reports(context: TenantContext):
    if not context.is_platform_admin:
        require_tenant_roles(context, REPORT_ROLES)


def resolve_scope(context: TenantContext, scope_type: str, company_id, branch_id):
    if context.is_platform_admin:
        if scope_type == "platform":
            return None, None
        if not company_id:
            raise HTTPException(status_code=400, detail="Select a company for company or branch reports")
        return company_id, branch_id
    if not context.company_id:
        raise HTTPException(status_code=403, detail="Company report access is required")
    selected_branch = branch_id
    if context.branch_id and context.role not in {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN}:
        selected_branch = context.branch_id
    return context.company_id, selected_branch




@router.get("/daily-issuance")
def daily_issuance_expected_returns(
    period_start: date = Query(...),
    period_end: date = Query(...),
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    include_details: bool = False,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Tenant-scoped disbursement snapshot; optional borrower-level register."""
    require_reports(context)
    if (period_end < period_start or (period_end - period_start).days > 1095
            or period_end == date.max):
        raise HTTPException(status_code=400, detail="Invalid reporting date range")
    if (not context.is_platform_admin and company_id is not None
            and company_id != context.company_id):
        raise HTTPException(status_code=403, detail="Cross-company reporting is not allowed")
    # A platform administrator must explicitly select a tenant. Never aggregate
    # all tenants in a financial report.
    if (not context.is_platform_admin and context.branch_id is None
            and context.role not in {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN}):
        raise HTTPException(status_code=403, detail="A branch assignment is required for this report")
    if (not context.is_platform_admin and context.branch_id is not None
            and context.role not in {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN}
            and branch_id is not None and branch_id != context.branch_id):
        raise HTTPException(status_code=403, detail="Cross-branch reporting is not allowed")
    company_id, branch_id = resolve_scope(context, "company", company_id, branch_id)
    if company_id is None:
        raise HTTPException(status_code=400, detail="Company selection is required")
    loan = ClientCompanyLoan
    rows = (
        db.query(
            func.date(loan.disbursed_at).label("issue_date"),
            func.count(loan.id).label("loans_issued"),
            func.sum(loan.principal_amount).label("principal_issued"),
            func.sum(loan.total_repayable).label("expected_contractual_return"),
        )
        .filter(
            loan.company_id == company_id,
            loan.disbursed_at >= datetime.combine(period_start, time.min),
            loan.disbursed_at < datetime.combine(period_end + timedelta(days=1), time.min),
            loan.status.notin_([LoanStatus.CANCELLED, LoanStatus.REJECTED]),
        )
    )
    if branch_id is not None:
        rows = rows.filter(loan.branch_id == branch_id)
    results = (
        rows.group_by(func.date(loan.disbursed_at))
        .order_by(func.date(loan.disbursed_at).desc())
        .all()
    )
    def money(value):
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))

    daily = [
        {
            "date": str(row.issue_date),
            "loans_issued": row.loans_issued,
            "principal_issued": str(money(row.principal_issued)),
            "expected_contractual_return": str(money(row.expected_contractual_return)),
            "expected_return_above_principal": str(
                money(row.expected_contractual_return) - money(row.principal_issued)
            ),
        }
        for row in results
    ]
    principal = sum((Decimal(item["principal_issued"]) for item in daily), Decimal("0.00"))
    expected = sum((Decimal(item["expected_contractual_return"]) for item in daily), Decimal("0.00"))
    details = []
    if include_details:
        # The same tenant, branch, disbursement-time and status filters used
        # for the aggregate govern the confidential borrower-level register.
        # Limit expanded reporting to a quarter to bound response size.
        if (period_end - period_start).days > 92:
            raise HTTPException(status_code=400, detail="Detailed loan register supports up to 93 calendar days. Narrow the date range.")
        detail_query = (
            db.query(ClientCompanyLoan)
            .options(
                joinedload(ClientCompanyLoan.borrower)
                    .joinedload(Borrower.user).joinedload(User.person),
                joinedload(ClientCompanyLoan.branch),
                joinedload(ClientCompanyLoan.disbursed_by).joinedload(User.person),
            )
            .filter(
                loan.company_id == company_id,
                loan.disbursed_at >= datetime.combine(period_start, time.min),
                loan.disbursed_at < datetime.combine(period_end + timedelta(days=1), time.min),
                loan.status.notin_([LoanStatus.CANCELLED, LoanStatus.REJECTED]),
            )
        )
        if branch_id is not None:
            detail_query = detail_query.filter(loan.branch_id == branch_id)
        loans = detail_query.order_by(loan.disbursed_at.asc(), loan.id.asc()).all()
        for item in loans:
            borrower_person = getattr(getattr(item.borrower, "user", None), "person", None)
            officer_person = getattr(item.disbursed_by, "person", None) if item.disbursed_by else None
            principal_value = money(item.principal_amount)
            # Top-ups use net cash to borrower, not the larger new principal.
            # Cash settlement/paid-out totals are recorded separately for review.
            cash_value = money(item.top_up_cash_amount if item.is_top_up else item.principal_amount)
            details.append({
                "date": item.disbursed_at.date().isoformat(),
                "time": item.disbursed_at.strftime("%H:%M"),
                "loan_reference": item.loan_reference,
                "folio_number": item.folio_number,
                "client_name": borrower_person.full_name if borrower_person else "Name unavailable",
                "branch": item.branch.name if item.branch else "Unassigned",
                "disbursed_by": officer_person.full_name if officer_person else "Not recorded",
                "is_top_up": bool(item.is_top_up),
                "principal_issued": str(principal_value),
                "cash_to_borrower": str(cash_value),
                "top_up_settlement": str(money(item.top_up_settlement_amount if item.is_top_up else 0)),
                "expected_contractual_return": str(money(item.total_repayable)),
                "installments": item.repayment_period,
                "installment_amount": str(money(item.installment_amount)),
                "first_payment_due": item.first_payment_due.isoformat() if item.first_payment_due else None,
            })
        # If the detailed and aggregate queries disagree due to a concurrent
        # disbursement, do not silently publish an unreconciled report.
        if (len(details) != sum(row["loans_issued"] for row in daily)
                or sum((Decimal(item["principal_issued"]) for item in details), Decimal("0.00")) != principal):
            raise HTTPException(status_code=409, detail="Issuance changed while preparing the register. Refresh the report.")

    return {
        "company_id": str(company_id),
        "branch_id": str(branch_id) if branch_id else None,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "basis": "current_contractual_snapshot",
        "date_basis": "disbursed_at_database_timezone",
        "totals": {
            "loans_issued": sum(item["loans_issued"] for item in daily),
            "principal_issued": str(principal),
            "expected_contractual_return": str(expected),
            "expected_return_above_principal": str(expected - principal),
        },
        "daily": daily,
        "details": details,
        "cash_to_borrowers": str(sum((Decimal(item["cash_to_borrower"]) for item in details), Decimal("0.00"))) if include_details else None,
    }




@router.get("/daily-issuance.csv")
def export_daily_issuance_csv(
    period_start: date = Query(...),
    period_end: date = Query(...),
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Export exactly the same authorized and scoped daily report as CSV."""
    report = daily_issuance_expected_returns(
        period_start=period_start,
        period_end=period_end,
        company_id=company_id,
        branch_id=branch_id,
        include_details=True,
        db=db,
        context=context,
    )
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["LoanHub Daily Issuance and Expected Contractual Returns"])
    writer.writerow(["Basis", report["basis"]])
    writer.writerow(["Notice", "Principal is not necessarily cash disbursed; expected returns are not guaranteed collections."])
    writer.writerow(["Period", report["period_start"], report["period_end"]])
    writer.writerow(["Date", "Loans issued", "Principal issued (M)", "Expected contractual return (M)", "Expected return above principal (M)"])
    for item in report["daily"]:
        writer.writerow([
            item["date"], item["loans_issued"], item["principal_issued"],
            item["expected_contractual_return"], item["expected_return_above_principal"],
        ])
    writer.writerow([
        "TOTAL", report["totals"]["loans_issued"],
        report["totals"]["principal_issued"],
        report["totals"]["expected_contractual_return"],
        report["totals"]["expected_return_above_principal"],
    ])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=loanhub-daily-issuance.csv",
            "Cache-Control": "no-store",
        },
    )




@router.get("/daily-issuance.pdf")
def export_daily_issuance_pdf(
    period_start: date = Query(...),
    period_end: date = Query(...),
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Read-only PDF export; authorization and amounts match the JSON report."""
    from xml.sax.saxutils import escape

    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, Spacer, Table, TableStyle

    from database.models.company import LoanCompany
    from services.pdf_design_system import (
        BORDER, NAVY, SOFT_SLATE, DocumentContext, build_document,
        callout, document_styles, hero_block, metric_grid, section,
    )

    # Keep the existing authorized query as the single source of report amounts.
    report = daily_issuance_expected_returns(
        period_start=period_start,
        period_end=period_end,
        company_id=company_id,
        branch_id=branch_id,
        include_details=True,
        db=db,
        context=context,
    )
    # Resolve branding only for the tenant already authorized by the report.
    authorized_company_id = report.get("company_id")
    company = (
        db.query(LoanCompany).filter(LoanCompany.id == UUID(authorized_company_id)).first()
        if authorized_company_id else None
    )
    styles = document_styles()
    reference = f"DAILY-ISSUANCE-{report['period_start']}-{report['period_end']}"
    totals = report["totals"]
    story = hero_block(
        "Daily loan issuance and expected returns",
        f"Reporting period: {escape(report['period_start'])} to {escape(report['period_end'])}",
        reference,
        styles=styles,
    )
    story.append(Spacer(1, 5 * mm))
    story.append(metric_grid([
        ("Loans issued", str(totals["loans_issued"]), "Disbursed loans in period", "blue"),
        ("Principal issued", f"M {Decimal(totals['principal_issued']):,.2f}", "Recorded principal", "teal"),
        ("Expected contractual return", f"M {Decimal(totals['expected_contractual_return']):,.2f}", "Current contractual snapshot", "green"),
        ("Above principal", f"M {Decimal(totals['expected_return_above_principal']):,.2f}", "Difference, not collected income", "slate"),
    ], styles=styles))
    story.extend(section("Daily breakdown", styles=styles))
    cell = ParagraphStyle(
        "DailyIssuanceCell", fontName="Helvetica", fontSize=7.3,
        leading=10, textColor=NAVY,
    )
    header = ParagraphStyle(
        "DailyIssuanceHeader", parent=cell, fontName="Helvetica-Bold",
        textColor=colors.white,
    )
    def p(value, style=cell):
        return Paragraph(escape(str(value)), style)

    data = [[p(label, header) for label in (
        "Date", "Loans", "Principal (M)", "Expected return (M)", "Above principal (M)",
    )]]
    for row in report["daily"]:
        data.append([
            p(row["date"]), p(row["loans_issued"]),
            p(f"{Decimal(row['principal_issued']):,.2f}"),
            p(f"{Decimal(row['expected_contractual_return']):,.2f}"),
            p(f"{Decimal(row['expected_return_above_principal']):,.2f}"),
        ])
    data.append([
        p("TOTAL"), p(totals["loans_issued"]),
        p(f"{Decimal(totals['principal_issued']):,.2f}"),
        p(f"{Decimal(totals['expected_contractual_return']):,.2f}"),
        p(f"{Decimal(totals['expected_return_above_principal']):,.2f}"),
    ])
    table = Table(
        data, colWidths=[30 * mm, 19 * mm, 39 * mm, 44 * mm, 42 * mm],
        repeatRows=1, hAlign="LEFT",
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("BACKGROUND", (0, -1), (-1, -1), SOFT_SLATE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, SOFT_SLATE]),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.7, BORDER),
        ("LINEBELOW", (0, -1), (-1, -1), 0.7, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(table)
    story.append(Spacer(1, 5 * mm))
    story.append(callout(
        "Reporting basis",
        "Current contractual snapshot, not an immutable origination forecast. "
        "Principal may differ from actual cash disbursed, especially for top-ups. "
        "Expected returns are contractual amounts, not guaranteed collections.",
        tone="amber", styles=styles,
    ))
    content = build_document(
        story=story,
        context=DocumentContext(
            db=db, company=company,
            title="Daily issuance and expected returns",
            reference=reference,
        ),
        title="LoanHub | Daily loan issuance and expected returns",
    )
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=loanhub-daily-issuance.pdf",
            "Cache-Control": "no-store",
        },
    )



@router.get("/daily-issuance.xlsx")
def export_daily_issuance_xlsx(
    period_start: date = Query(...),
    period_end: date = Query(...),
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Native spreadsheet export using the same tenant-scoped reporting query."""
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    from openpyxl.utils import get_column_letter

    report = daily_issuance_expected_returns(
        period_start=period_start,
        period_end=period_end,
        company_id=company_id,
        branch_id=branch_id,
        include_details=True,
        db=db,
        context=context,
    )
    book = Workbook()
    sheet = book.active
    sheet.title = "Daily Issuance"
    sheet.append(["LoanHub | Daily Issuance and Expected Returns"])
    sheet.append(["Period", report["period_start"], report["period_end"]])
    sheet.append(["Basis", report["basis"]])
    sheet.append(["Note", "Principal is not necessarily cash disbursed; expected returns are not guaranteed collections."])
    sheet.append(["Date basis", report.get("date_basis", "disbursed_at_database_timezone")])
    sheet.append([])
    sheet.append(["Date", "Loans issued", "Principal (M)", "Expected return (M)", "Above principal (M)"])
    for item in report["daily"]:
        sheet.append([
            item["date"], item["loans_issued"], Decimal(item["principal_issued"]),
            Decimal(item["expected_contractual_return"]),
            Decimal(item["expected_return_above_principal"]),
        ])
    totals = report["totals"]
    sheet.append([
        "TOTAL", totals["loans_issued"], Decimal(totals["principal_issued"]),
        Decimal(totals["expected_contractual_return"]),
        Decimal(totals["expected_return_above_principal"]),
    ])
    for cell in sheet[6]:
        cell.fill = PatternFill("solid", fgColor="17365D")
        cell.font = Font(color="FFFFFF", bold=True)
    for cell in sheet[sheet.max_row]:
        cell.font = Font(bold=True)
    for row in sheet.iter_rows(min_row=7, min_col=3, max_col=5):
        for cell in row:
            cell.number_format = '#,##0.00'
    for column, width in enumerate([22, 20, 23, 26, 25], start=1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    sheet.freeze_panes = "A7"
    sheet.auto_filter.ref = f"A6:E{sheet.max_row}"
    output = io.BytesIO()
    book.save(output)
    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": "attachment; filename=loanhub-daily-issuance.xlsx",
            "Cache-Control": "no-store",
        },
    )


@router.get("/summary", response_model=ReportSummaryRead)
def report_summary(
    scope_type: str = "company",
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    period_start: date = Query(default_factory=lambda: date.today().replace(day=1)),
    period_end: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_reports(context)
    company_id, branch_id = resolve_scope(context, scope_type, company_id, branch_id)
    return ReportSummaryRead(
        scope_type=scope_type,
        company_id=company_id,
        branch_id=branch_id,
        period_start=period_start,
        period_end=period_end,
        metrics=collect_metrics(
            db,
            period_start=period_start,
            period_end=period_end,
            company_id=company_id,
            branch_id=branch_id,
        ),
    )


@router.get("", response_model=list[GeneratedReportRead])
def list_reports(
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    report_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_reports(context)
    query = db.query(GeneratedReport).options(joinedload(GeneratedReport.file))
    if context.is_platform_admin:
        if company_id:
            query = query.filter(GeneratedReport.company_id == company_id)
    else:
        query = query.filter(GeneratedReport.company_id == context.company_id)
        if context.branch_id and context.role not in {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN}:
            query = query.filter(GeneratedReport.branch_id == context.branch_id)
    if branch_id:
        query = query.filter(GeneratedReport.branch_id == branch_id)
    if report_type:
        query = query.filter(GeneratedReport.report_type == report_type)
    return query.order_by(GeneratedReport.generated_at.desc()).offset(skip).limit(limit).all()


@router.post("/generate", response_model=GeneratedReportRead, status_code=status.HTTP_201_CREATED)
def generate_now(
    payload: ReportGenerateCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_reports(context)
    company_id, branch_id = resolve_scope(
        context,
        payload.scope_type,
        payload.company_id,
        payload.branch_id,
    )
    report = generate_report(
        db,
        report_type=payload.report_type,
        output_format=payload.output_format,
        scope_type=payload.scope_type,
        period_start=payload.period_start,
        period_end=payload.period_end,
        company_id=company_id,
        branch_id=branch_id,
        generated_by_user_id=context.user.id,
    )
    db.commit()
    return db.query(GeneratedReport).options(joinedload(GeneratedReport.file)).filter(GeneratedReport.id == report.id).first()


@router.get("/schedules", response_model=list[ReportScheduleRead])
def list_schedules(
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_reports(context)
    query = db.query(ReportSchedule)
    if context.is_platform_admin:
        if company_id:
            query = query.filter(ReportSchedule.company_id == company_id)
    else:
        query = query.filter(ReportSchedule.company_id == context.company_id)
    return query.order_by(ReportSchedule.created_at.desc()).all()


@router.post("/schedules", response_model=ReportScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ReportScheduleCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_reports(context)
    company_id, branch_id = resolve_scope(context, payload.scope_type, payload.company_id, payload.branch_id)
    schedule = ReportSchedule(
        scope_type=payload.scope_type,
        company_id=company_id,
        branch_id=branch_id,
        created_by_user_id=context.user.id,
        name=payload.name.strip(),
        report_type=payload.report_type,
        frequency=payload.frequency,
        output_format=payload.output_format,
        recipients=payload.recipients,
        is_active=payload.is_active,
        next_run_at=next_run_for_frequency(payload.frequency),
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.patch("/schedules/{schedule_id}", response_model=ReportScheduleRead)
def update_schedule(
    schedule_id: UUID,
    payload: ReportScheduleUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_reports(context)
    schedule = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    if not context.is_platform_admin and schedule.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company report access is not allowed")
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(schedule, field, value)
    if payload.frequency:
        schedule.next_run_at = next_run_for_frequency(payload.frequency)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_reports(context)
    schedule = db.query(ReportSchedule).filter(ReportSchedule.id == schedule_id).first()
    if not schedule:
        raise HTTPException(status_code=404, detail="Report schedule not found")
    if not context.is_platform_admin and schedule.company_id != context.company_id:
        raise HTTPException(status_code=403, detail="Cross-company report access is not allowed")
    db.delete(schedule)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
