from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session, joinedload

from core.access_control import PERFORMANCE_ROLES, TRANSPARENCY_ROLES, TenantContext, get_user_context, require_tenant_roles
from database.models.enums import UserRole
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
