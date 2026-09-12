from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import (
    FINANCE_ROLES,
    HR_ROLES,
    PERFORMANCE_ROLES,
    TenantContext,
    assert_branch_scope,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.branch import CompanyBranch
from database.models.employee import EmployeeProfile
from database.models.enums import UserRole
from database.models.hrms import (
    HRAsset,
    HRAssetAssignment,
    HRAttendanceEvent,
    HRCandidate,
    HRDepartment,
    HRLeaveRequest,
    HRLeaveType,
    HRPayrollEntry,
    HRPayrollRun,
    HRPosition,
    HRShift,
    HRTrainingEnrollment,
    HRTrainingProgram,
    HRVacancy,
)
from database.schemas.hrms import (
    HRAssetAssignmentCreate,
    HRAssetAssignmentRead,
    HRAssetCreate,
    HRAssetRead,
    HRAttendanceEventCreate,
    HRAttendanceEventRead,
    HRCandidateCreate,
    HRCandidateRead,
    HRDashboardSummary,
    HRDepartmentCreate,
    HRDepartmentRead,
    HRLeaveDecision,
    HRLeaveRequestCreate,
    HRLeaveRequestRead,
    HRLeaveTypeCreate,
    HRLeaveTypeRead,
    HRPayrollEntryRead,
    HRPayrollRunCreate,
    HRPayrollRunRead,
    HRPayrollStatusUpdate,
    HRPositionCreate,
    HRPositionRead,
    HRSelfServiceSummary,
    HRShiftCreate,
    HRShiftRead,
    HRTrainingEnrollmentCreate,
    HRTrainingEnrollmentRead,
    HRTrainingProgramCreate,
    HRTrainingProgramRead,
    HRVacancyCreate,
    HRVacancyRead,
)
from database.session import get_db


router = APIRouter(prefix="/hr", tags=["Human Resource Management"])
HR_VIEW_ROLES = HR_ROLES | PERFORMANCE_ROLES | {UserRole.AUDITOR}
PAYROLL_ROLES = FINANCE_ROLES | {UserRole.HR_MANAGER}
PAYROLL_TRANSITIONS = {
    "draft": {"calculated"},
    "calculated": {"draft", "under_review"},
    "under_review": {"calculated", "approved"},
    "approved": {"paid"},
    "paid": {"locked"},
    "locked": set(),
}


def _require_company(context: TenantContext) -> UUID:
    if context.is_platform_admin or not context.company_id:
        raise HTTPException(status_code=400, detail="An active company context is required")
    return context.company_id


def _apply_branch_scope(query, model, context: TenantContext):
    if context.branch_id and context.role not in {UserRole.COMPANY_OWNER, UserRole.COMPANY_ADMIN}:
        branch_column = getattr(model, "branch_id", None)
        if branch_column is not None:
            query = query.filter(branch_column == context.branch_id)
    return query


def _employee_or_404(db: Session, context: TenantContext, employee_id: UUID) -> EmployeeProfile:
    company_id = _require_company(context)
    employee = (
        db.query(EmployeeProfile)
        .filter(EmployeeProfile.id == employee_id, EmployeeProfile.company_id == company_id)
        .first()
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Employee profile was not found")
    assert_branch_scope(context, employee.branch_id)
    return employee


def _company_record_or_404(db: Session, model, record_id: UUID, company_id: UUID):
    record = db.query(model).filter(model.id == record_id, model.company_id == company_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="HR record was not found")
    return record


def _commit_unique(db: Session, detail: str):
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=detail) from error


@router.get("/dashboard", response_model=HRDashboardSummary)
def get_hr_dashboard(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    today = date.today()

    employee_query = db.query(EmployeeProfile).filter(EmployeeProfile.company_id == company_id)
    employee_query = _apply_branch_scope(employee_query, EmployeeProfile, context)
    total_employees = employee_query.count()
    active_employees = employee_query.filter(EmployeeProfile.employment_status == "active").count()

    present_employee_ids = {
        row[0]
        for row in _apply_branch_scope(
            db.query(HRAttendanceEvent.employee_id).filter(
                HRAttendanceEvent.company_id == company_id,
                func.date(HRAttendanceEvent.occurred_at) == today,
                HRAttendanceEvent.event_type == "clock_in",
            ),
            HRAttendanceEvent,
            context,
        ).distinct().all()
    }

    employees_on_leave = _apply_branch_scope(
        db.query(HRLeaveRequest).filter(
            HRLeaveRequest.company_id == company_id,
            HRLeaveRequest.status == "approved",
            HRLeaveRequest.start_date <= today,
            HRLeaveRequest.end_date >= today,
        ),
        HRLeaveRequest,
        context,
    ).count()

    pending_leave = _apply_branch_scope(
        db.query(HRLeaveRequest).filter(
            HRLeaveRequest.company_id == company_id,
            HRLeaveRequest.status == "pending",
        ),
        HRLeaveRequest,
        context,
    ).count()

    latest_payroll = _apply_branch_scope(
        db.query(HRPayrollRun).filter(HRPayrollRun.company_id == company_id),
        HRPayrollRun,
        context,
    ).order_by(HRPayrollRun.period_end.desc()).first()

    return HRDashboardSummary(
        total_employees=total_employees,
        active_employees=active_employees,
        employees_present_today=len(present_employee_ids),
        employees_absent_today=max(active_employees - len(present_employee_ids) - employees_on_leave, 0),
        employees_on_leave_today=employees_on_leave,
        pending_leave_requests=pending_leave,
        open_vacancies=_apply_branch_scope(
            db.query(HRVacancy).filter(HRVacancy.company_id == company_id, HRVacancy.status == "published"),
            HRVacancy,
            context,
        ).count(),
        active_training_programs=_apply_branch_scope(
            db.query(HRTrainingProgram).filter(
                HRTrainingProgram.company_id == company_id,
                HRTrainingProgram.status.in_(["planned", "active"]),
            ),
            HRTrainingProgram,
            context,
        ).count(),
        assigned_assets=_apply_branch_scope(
            db.query(HRAsset).filter(HRAsset.company_id == company_id, HRAsset.status == "assigned"),
            HRAsset,
            context,
        ).count(),
        payroll_status=latest_payroll.status if latest_payroll else None,
        payroll_net_total=latest_payroll.net_total if latest_payroll else Decimal("0"),
        departments=db.query(HRDepartment).filter(HRDepartment.company_id == company_id, HRDepartment.is_active.is_(True)).count(),
        branches=db.query(CompanyBranch).filter(CompanyBranch.company_id == company_id, CompanyBranch.is_active.is_(True)).count(),
    )


@router.get("/departments", response_model=list[HRDepartmentRead])
def list_departments(
    active_only: bool = False,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    query = db.query(HRDepartment).filter(HRDepartment.company_id == company_id)
    query = _apply_branch_scope(query, HRDepartment, context)
    if active_only:
        query = query.filter(HRDepartment.is_active.is_(True))
    return query.order_by(HRDepartment.name.asc()).all()


@router.post("/departments", response_model=HRDepartmentRead, status_code=status.HTTP_201_CREATED)
def create_department(
    payload: HRDepartmentCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    branch_id = payload.branch_id or context.branch_id
    assert_branch_scope(context, branch_id)
    department = HRDepartment(company_id=company_id, **payload.model_dump(exclude={"branch_id"}), branch_id=branch_id)
    db.add(department)
    _commit_unique(db, "A department with this code already exists")
    db.refresh(department)
    return department


@router.get("/positions", response_model=list[HRPositionRead])
def list_positions(
    department_id: UUID | None = None,
    active_only: bool = False,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    query = db.query(HRPosition).filter(HRPosition.company_id == company_id)
    if department_id:
        query = query.filter(HRPosition.department_id == department_id)
    if active_only:
        query = query.filter(HRPosition.is_active.is_(True))
    return query.order_by(HRPosition.title.asc()).all()


@router.post("/positions", response_model=HRPositionRead, status_code=status.HTTP_201_CREATED)
def create_position(
    payload: HRPositionCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    position = HRPosition(company_id=company_id, **payload.model_dump())
    db.add(position)
    _commit_unique(db, "A position with this code already exists")
    db.refresh(position)
    return position


@router.get("/shifts", response_model=list[HRShiftRead])
def list_shifts(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    query = _apply_branch_scope(db.query(HRShift).filter(HRShift.company_id == company_id), HRShift, context)
    return query.order_by(HRShift.name.asc()).all()


@router.post("/shifts", response_model=HRShiftRead, status_code=status.HTTP_201_CREATED)
def create_shift(
    payload: HRShiftCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    branch_id = payload.branch_id or context.branch_id
    assert_branch_scope(context, branch_id)
    shift = HRShift(company_id=company_id, **payload.model_dump(exclude={"branch_id"}), branch_id=branch_id)
    db.add(shift)
    _commit_unique(db, "A shift with this code already exists")
    db.refresh(shift)
    return shift


@router.get("/attendance/events", response_model=list[HRAttendanceEventRead])
def list_attendance_events(
    attendance_date: date | None = None,
    employee_id: UUID | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    query = db.query(HRAttendanceEvent).filter(HRAttendanceEvent.company_id == company_id)
    query = _apply_branch_scope(query, HRAttendanceEvent, context)
    if attendance_date:
        query = query.filter(func.date(HRAttendanceEvent.occurred_at) == attendance_date)
    if employee_id:
        _employee_or_404(db, context, employee_id)
        query = query.filter(HRAttendanceEvent.employee_id == employee_id)
    return query.order_by(HRAttendanceEvent.occurred_at.desc()).limit(limit).all()


@router.post("/attendance/events", response_model=HRAttendanceEventRead, status_code=status.HTTP_201_CREATED)
def record_attendance_event(
    payload: HRAttendanceEventCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    employee = _employee_or_404(db, context, payload.employee_id)
    event = HRAttendanceEvent(
        company_id=company_id,
        branch_id=employee.branch_id,
        occurred_at=payload.occurred_at or datetime.now(timezone.utc),
        **payload.model_dump(exclude={"occurred_at"}),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("/leave/types", response_model=list[HRLeaveTypeRead])
def list_leave_types(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    return db.query(HRLeaveType).filter(HRLeaveType.company_id == company_id).order_by(HRLeaveType.name.asc()).all()


@router.post("/leave/types", response_model=HRLeaveTypeRead, status_code=status.HTTP_201_CREATED)
def create_leave_type(
    payload: HRLeaveTypeCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    leave_type = HRLeaveType(company_id=company_id, **payload.model_dump())
    db.add(leave_type)
    _commit_unique(db, "A leave type with this code already exists")
    db.refresh(leave_type)
    return leave_type


@router.get("/leave/requests", response_model=list[HRLeaveRequestRead])
def list_leave_requests(
    request_status: str | None = Query(default=None, alias="status"),
    employee_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    query = _apply_branch_scope(
        db.query(HRLeaveRequest).filter(HRLeaveRequest.company_id == company_id),
        HRLeaveRequest,
        context,
    )
    if request_status:
        query = query.filter(HRLeaveRequest.status == request_status)
    if employee_id:
        _employee_or_404(db, context, employee_id)
        query = query.filter(HRLeaveRequest.employee_id == employee_id)
    return query.order_by(HRLeaveRequest.created_at.desc()).all()


@router.post("/leave/requests", response_model=HRLeaveRequestRead, status_code=status.HTTP_201_CREATED)
def create_leave_request(
    payload: HRLeaveRequestCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    employee = _employee_or_404(db, context, payload.employee_id)
    leave_type = _company_record_or_404(db, HRLeaveType, payload.leave_type_id, company_id)
    if not leave_type.is_active:
        raise HTTPException(status_code=409, detail="The selected leave type is inactive")
    days_requested = Decimal((payload.end_date - payload.start_date).days + 1)
    request = HRLeaveRequest(
        company_id=company_id,
        branch_id=employee.branch_id,
        days_requested=days_requested,
        **payload.model_dump(),
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


@router.patch("/leave/requests/{request_id}/decision", response_model=HRLeaveRequestRead)
def decide_leave_request(
    request_id: UUID,
    payload: HRLeaveDecision,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    request = _company_record_or_404(db, HRLeaveRequest, request_id, company_id)
    assert_branch_scope(context, request.branch_id)
    if request.status not in {"pending", "approved"}:
        raise HTTPException(status_code=409, detail="This leave request can no longer be changed")
    request.status = payload.decision
    request.manager_comment = payload.comment
    request.decided_by_user_id = context.user.id
    request.decided_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(request)
    return request


@router.get("/payroll/runs", response_model=list[HRPayrollRunRead])
def list_payroll_runs(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, PAYROLL_ROLES)
    company_id = _require_company(context)
    query = _apply_branch_scope(db.query(HRPayrollRun).filter(HRPayrollRun.company_id == company_id), HRPayrollRun, context)
    return query.order_by(HRPayrollRun.period_end.desc()).all()


@router.post("/payroll/runs", response_model=HRPayrollRunRead, status_code=status.HTTP_201_CREATED)
def create_payroll_run(
    payload: HRPayrollRunCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, PAYROLL_ROLES)
    company_id = _require_company(context)
    branch_id = payload.branch_id or context.branch_id
    assert_branch_scope(context, branch_id)
    run = HRPayrollRun(company_id=company_id, **payload.model_dump(exclude={"branch_id"}), branch_id=branch_id)
    db.add(run)
    _commit_unique(db, "A payroll run already exists for this company and period")
    db.refresh(run)
    return run


@router.post("/payroll/runs/{run_id}/calculate", response_model=HRPayrollRunRead)
def calculate_payroll_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, PAYROLL_ROLES)
    company_id = _require_company(context)
    run = _company_record_or_404(db, HRPayrollRun, run_id, company_id)
    assert_branch_scope(context, run.branch_id)
    if run.status not in {"draft", "calculated"}:
        raise HTTPException(status_code=409, detail="Only draft or calculated payroll can be recalculated")

    employee_query = db.query(EmployeeProfile).filter(
        EmployeeProfile.company_id == company_id,
        EmployeeProfile.employment_status == "active",
    )
    if run.branch_id:
        employee_query = employee_query.filter(EmployeeProfile.branch_id == run.branch_id)
    employees = employee_query.all()

    db.query(HRPayrollEntry).filter(HRPayrollEntry.payroll_run_id == run.id).delete(synchronize_session=False)
    gross_total = Decimal("0")
    net_total = Decimal("0")
    for employee in employees:
        basic = Decimal(employee.base_salary or 0)
        gross = basic
        net = gross
        db.add(
            HRPayrollEntry(
                payroll_run_id=run.id,
                company_id=company_id,
                employee_id=employee.id,
                basic_salary=basic,
                gross_salary=gross,
                net_salary=net,
                components={"calculation": "foundation_basic_salary_only"},
            )
        )
        gross_total += gross
        net_total += net

    run.gross_total = gross_total
    run.deduction_total = Decimal("0")
    run.net_total = net_total
    run.status = "calculated"
    db.commit()
    db.refresh(run)
    return run


@router.get("/payroll/runs/{run_id}/entries", response_model=list[HRPayrollEntryRead])
def list_payroll_entries(
    run_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, PAYROLL_ROLES)
    company_id = _require_company(context)
    run = _company_record_or_404(db, HRPayrollRun, run_id, company_id)
    assert_branch_scope(context, run.branch_id)
    return db.query(HRPayrollEntry).filter(HRPayrollEntry.payroll_run_id == run.id).all()


@router.patch("/payroll/runs/{run_id}/status", response_model=HRPayrollRunRead)
def transition_payroll_run(
    run_id: UUID,
    payload: HRPayrollStatusUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, PAYROLL_ROLES)
    company_id = _require_company(context)
    run = _company_record_or_404(db, HRPayrollRun, run_id, company_id)
    assert_branch_scope(context, run.branch_id)
    if payload.status not in PAYROLL_TRANSITIONS.get(run.status, set()):
        raise HTTPException(status_code=409, detail=f"Payroll cannot move from {run.status} to {payload.status}")
    run.status = payload.status
    now = datetime.now(timezone.utc)
    if payload.status == "approved":
        run.approved_by_user_id = context.user.id
        run.approved_at = now
    if payload.status == "locked":
        run.locked_at = now
    db.commit()
    db.refresh(run)
    return run


@router.get("/recruitment/vacancies", response_model=list[HRVacancyRead])
def list_vacancies(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    query = _apply_branch_scope(db.query(HRVacancy).filter(HRVacancy.company_id == company_id), HRVacancy, context)
    return query.order_by(HRVacancy.created_at.desc()).all()


@router.post("/recruitment/vacancies", response_model=HRVacancyRead, status_code=status.HTTP_201_CREATED)
def create_vacancy(
    payload: HRVacancyCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    branch_id = payload.branch_id or context.branch_id
    assert_branch_scope(context, branch_id)
    vacancy = HRVacancy(
        company_id=company_id,
        branch_id=branch_id,
        published_at=datetime.now(timezone.utc) if payload.status == "published" else None,
        **payload.model_dump(exclude={"branch_id"}),
    )
    db.add(vacancy)
    db.commit()
    db.refresh(vacancy)
    return vacancy


@router.get("/recruitment/candidates", response_model=list[HRCandidateRead])
def list_candidates(
    vacancy_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    query = db.query(HRCandidate).filter(HRCandidate.company_id == company_id)
    if vacancy_id:
        _company_record_or_404(db, HRVacancy, vacancy_id, company_id)
        query = query.filter(HRCandidate.vacancy_id == vacancy_id)
    return query.order_by(HRCandidate.created_at.desc()).all()


@router.post("/recruitment/candidates", response_model=HRCandidateRead, status_code=status.HTTP_201_CREATED)
def create_candidate(
    payload: HRCandidateCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    if payload.vacancy_id:
        _company_record_or_404(db, HRVacancy, payload.vacancy_id, company_id)
    candidate = HRCandidate(company_id=company_id, **payload.model_dump())
    db.add(candidate)
    db.commit()
    db.refresh(candidate)
    return candidate


@router.get("/training/programs", response_model=list[HRTrainingProgramRead])
def list_training_programs(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    query = _apply_branch_scope(
        db.query(HRTrainingProgram).filter(HRTrainingProgram.company_id == company_id),
        HRTrainingProgram,
        context,
    )
    return query.order_by(HRTrainingProgram.start_date.desc().nullslast()).all()


@router.post("/training/programs", response_model=HRTrainingProgramRead, status_code=status.HTTP_201_CREATED)
def create_training_program(
    payload: HRTrainingProgramCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    branch_id = payload.branch_id or context.branch_id
    assert_branch_scope(context, branch_id)
    program = HRTrainingProgram(company_id=company_id, branch_id=branch_id, **payload.model_dump(exclude={"branch_id"}))
    db.add(program)
    db.commit()
    db.refresh(program)
    return program


@router.post(
    "/training/programs/{program_id}/enrollments",
    response_model=HRTrainingEnrollmentRead,
    status_code=status.HTTP_201_CREATED,
)
def enroll_employee(
    program_id: UUID,
    payload: HRTrainingEnrollmentCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    program = _company_record_or_404(db, HRTrainingProgram, program_id, company_id)
    assert_branch_scope(context, program.branch_id)
    _employee_or_404(db, context, payload.employee_id)
    enrollment = HRTrainingEnrollment(program_id=program.id, company_id=company_id, employee_id=payload.employee_id)
    db.add(enrollment)
    _commit_unique(db, "This employee is already enrolled in the training programme")
    db.refresh(enrollment)
    return enrollment


@router.get("/assets", response_model=list[HRAssetRead])
def list_assets(
    asset_status: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_VIEW_ROLES)
    company_id = _require_company(context)
    query = _apply_branch_scope(db.query(HRAsset).filter(HRAsset.company_id == company_id), HRAsset, context)
    if asset_status:
        query = query.filter(HRAsset.status == asset_status)
    return query.order_by(HRAsset.name.asc()).all()


@router.post("/assets", response_model=HRAssetRead, status_code=status.HTTP_201_CREATED)
def create_asset(
    payload: HRAssetCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    branch_id = payload.branch_id or context.branch_id
    assert_branch_scope(context, branch_id)
    asset = HRAsset(company_id=company_id, branch_id=branch_id, **payload.model_dump(exclude={"branch_id"}))
    db.add(asset)
    _commit_unique(db, "An asset with this tag already exists")
    db.refresh(asset)
    return asset


@router.post("/assets/{asset_id}/assignments", response_model=HRAssetAssignmentRead, status_code=status.HTTP_201_CREATED)
def assign_asset(
    asset_id: UUID,
    payload: HRAssetAssignmentCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, HR_ROLES)
    company_id = _require_company(context)
    asset = _company_record_or_404(db, HRAsset, asset_id, company_id)
    assert_branch_scope(context, asset.branch_id)
    _employee_or_404(db, context, payload.employee_id)
    if asset.status != "available":
        raise HTTPException(status_code=409, detail="Only available assets can be assigned")
    assignment = HRAssetAssignment(
        asset_id=asset.id,
        company_id=company_id,
        assigned_at=datetime.now(timezone.utc),
        **payload.model_dump(),
    )
    asset.status = "assigned"
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment


@router.get("/self-service/summary", response_model=HRSelfServiceSummary)
def self_service_summary(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    company_id = _require_company(context)
    if not context.staff:
        raise HTTPException(status_code=403, detail="Employee self-service requires a company staff membership")
    employee = db.query(EmployeeProfile).filter(EmployeeProfile.staff_id == context.staff.id).first()
    if not employee:
        return HRSelfServiceSummary(
            employee_id=None,
            employee_number=None,
            employment_status=None,
            job_title=None,
            department=None,
            pending_leave_requests=0,
            current_assets=0,
            upcoming_training=0,
            latest_payroll_period=None,
        )
    latest_payroll = (
        db.query(HRPayrollRun)
        .join(HRPayrollEntry, HRPayrollEntry.payroll_run_id == HRPayrollRun.id)
        .filter(
            HRPayrollRun.company_id == company_id,
            HRPayrollEntry.employee_id == employee.id,
            HRPayrollRun.status.in_(["approved", "paid", "locked"]),
        )
        .order_by(HRPayrollRun.period_end.desc())
        .first()
    )
    return HRSelfServiceSummary(
        employee_id=employee.id,
        employee_number=employee.employee_number,
        employment_status=employee.employment_status,
        job_title=employee.job_title,
        department=employee.department,
        pending_leave_requests=db.query(HRLeaveRequest).filter(
            HRLeaveRequest.company_id == company_id,
            HRLeaveRequest.employee_id == employee.id,
            HRLeaveRequest.status == "pending",
        ).count(),
        current_assets=db.query(HRAssetAssignment).filter(
            HRAssetAssignment.company_id == company_id,
            HRAssetAssignment.employee_id == employee.id,
            HRAssetAssignment.status == "assigned",
        ).count(),
        upcoming_training=db.query(HRTrainingEnrollment).join(
            HRTrainingProgram, HRTrainingProgram.id == HRTrainingEnrollment.program_id
        ).filter(
            HRTrainingEnrollment.company_id == company_id,
            HRTrainingEnrollment.employee_id == employee.id,
            HRTrainingProgram.status.in_(["planned", "active"]),
        ).count(),
        latest_payroll_period=latest_payroll.period_key if latest_payroll else None,
    )
