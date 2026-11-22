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
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Read-only daily disbursement and CURRENT contractual repayment snapshot."""
    require_reports(context)
    if period_end < period_start or (period_end - period_start).days > 1095:
        raise HTTPException(status_code=400, detail="Invalid reporting date range")
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
        db=db,
        context=context,
    )
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(["LoanHub Daily Issuance and Expected Contractual Returns"])
    writer.writerow(["Basis", report["basis"]])
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
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    report = daily_issuance_expected_returns(
        period_start=period_start,
        period_end=period_end,
        company_id=company_id,
        branch_id=branch_id,
        db=db,
        context=context,
    )
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output, pagesize=landscape(A4), leftMargin=30,
        rightMargin=30, topMargin=30, bottomMargin=30,
    )
    styles = getSampleStyleSheet()
    story = [
        Paragraph("LoanHub | Daily Loan Issuance and Expected Returns", styles["Title"]),
        Paragraph(
            f"Period: {report['period_start']} to {report['period_end']}",
            styles["Normal"],
        ),
        Paragraph(
            "Basis: current contractual snapshot; not an immutable origination forecast. "
            "Principal is not necessarily actual cash disbursed (particularly for top-ups). "
            "Expected returns are contractual amounts, not guaranteed collections.",
            styles["Normal"],
        ),
        Spacer(1, 14),
    ]
    data = [[
        "Date", "Loans", "Principal (M)", "Expected return (M)", "Above principal (M)",
    ]]
    for row in report["daily"]:
        data.append([
            row["date"], str(row["loans_issued"]), row["principal_issued"],
            row["expected_contractual_return"], row["expected_return_above_principal"],
        ])
    totals = report["totals"]
    data.append([
        "TOTAL", str(totals["loans_issued"]), totals["principal_issued"],
        totals["expected_contractual_return"], totals["expected_return_above_principal"],
    ])
    table = Table(data, repeatRows=1, colWidths=[110, 65, 140, 155, 155])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17365D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#E8EFF7")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
    ]))
    story.append(table)
    document.build(story)
    return Response(
        content=output.getvalue(),
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=loanhub-daily-issuance.pdf",
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
