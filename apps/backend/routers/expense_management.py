from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    assert_branch_scope,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.branch import CompanyBranch
from database.models.enums import PaymentMethod, TreasuryDayStatus, TreasuryDirection, TreasuryEntryType, UserRole
from database.models.treasury import BranchDailyLedger, BranchDailySubmission, BranchFundingTransfer, BranchOpeningSource, ExpenseCategory, TreasuryEntry
from database.schemas.treasury import (
    BranchDailyLedgerRead,
    BranchDailySubmissionListRead,
    BranchDailySubmissionRead,
    BranchFundingTransferCreate,
    BranchFundingTransferRead,
    DailySubmissionCreate,
    EntryDecisionCreate,
    ExpenseCategoryCreate,
    ExpenseCategoryRead,
    ExpenseCategoryUpdate,
    OpeningSourceCreate,
    OpeningSourceRead,
    PaymentMethodOption,
    ReopenDayCreate,
    FinancialIntegrityRepairRead,
    FinancialIntegrityReportRead,
    TreasuryDashboardRead,
    TreasuryEntryCreate,
    TreasuryEntryRead,
    TreasurySettingsRead,
    TreasurySettingsUpdate,
    TreasuryStatementRead,
    VoidEntryCreate,
    VoidOpeningSourceCreate,
)
from database.session import get_db
from services.branch_submission_report_service import ensure_branch_submission_pdf
from services.financial_integrity_service import build_financial_integrity_report, repair_financial_integrity
from services.treasury_service import (
    approve_treasury_entry,
    auto_open_due_ledgers,
    auto_submit_due_ledgers,
    build_dashboard,
    build_statement,
    create_manual_entry,
    create_opening_source,
    get_or_create_daily_ledger,
    get_or_create_settings,
    issue_branch_funding,
    local_business_date,
    payment_method_options,
    receive_branch_funding,
    recalculate_daily_ledger,
    reject_treasury_entry,
    reopen_daily_ledger,
    set_headquarters_branch,
    statement_csv,
    submit_daily_ledger,
    void_opening_source,
    void_treasury_entry,
)

router = APIRouter(prefix="/expense-management", tags=["Expense and Money Management"])

TREASURY_READ_ROLES = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.FINANCE_OFFICER,
    UserRole.COLLECTIONS_OFFICER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
    UserRole.RISK_MANAGER,
}
TREASURY_WRITE_ROLES = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.FINANCE_OFFICER,
}
TREASURY_TRANSFER_ROLES = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.FINANCE_OFFICER,
}
TREASURY_APPROVAL_ROLES = COMPANY_MANAGEMENT_ROLES | {UserRole.BRANCH_MANAGER}


def company_id_from(context: TenantContext) -> UUID:
    if not context.company_id:
        raise HTTPException(status_code=403, detail="An active company is required")
    return context.company_id


def scoped_branch_id(context: TenantContext, requested: UUID | None, db: Session) -> UUID:
    company_id = company_id_from(context)
    branch_id = requested or context.branch_id
    if not branch_id:
        branch_id = get_or_create_settings(db, company_id).headquarters_branch_id
    if not branch_id:
        raise HTTPException(status_code=409, detail="Select a branch or configure the headquarters branch")
    branch = db.get(CompanyBranch, branch_id)
    if not branch or branch.company_id != company_id:
        raise HTTPException(status_code=404, detail="Branch was not found in the active company")
    assert_branch_scope(context, branch_id)
    return branch_id


def ledger_with_details(db: Session, ledger_id: UUID) -> BranchDailyLedger:
    return (
        db.query(BranchDailyLedger)
        .options(
            joinedload(BranchDailyLedger.entries),
            joinedload(BranchDailyLedger.opening_sources),
            joinedload(BranchDailyLedger.submissions).joinedload(BranchDailySubmission.pdf_file),
        )
        .filter(BranchDailyLedger.id == ledger_id)
        .first()
    )


@router.get("/payment-methods", response_model=list[PaymentMethodOption])
def list_payment_methods(context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, TREASURY_READ_ROLES | {UserRole.LOAN_OFFICER})
    return payment_method_options()


@router.get("/settings", response_model=TreasurySettingsRead)
def get_settings(db: Session = Depends(get_db), context: TenantContext = Depends(get_tenant_context)):
    require_tenant_roles(context, TREASURY_READ_ROLES)
    settings = get_or_create_settings(db, company_id_from(context))
    db.commit()
    db.refresh(settings)
    return settings


@router.put("/settings", response_model=TreasurySettingsRead)
def update_settings(
    payload: TreasurySettingsUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    settings = get_or_create_settings(db, company_id_from(context))
    set_headquarters_branch(db, settings, payload.headquarters_branch_id)
    for field, value in payload.model_dump(exclude={"headquarters_branch_id"}).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings


@router.get("/expense-categories", response_model=list[ExpenseCategoryRead])
def list_expense_categories(
    include_inactive: bool = Query(False),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_READ_ROLES)
    query = db.query(ExpenseCategory).filter(ExpenseCategory.company_id == company_id_from(context))
    if not include_inactive:
        query = query.filter(ExpenseCategory.is_active.is_(True))
    return query.order_by(ExpenseCategory.name.asc()).all()


@router.post("/expense-categories", response_model=ExpenseCategoryRead, status_code=status.HTTP_201_CREATED)
def create_expense_category(
    payload: ExpenseCategoryCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    company_id = company_id_from(context)
    name = payload.name.strip()
    duplicate = db.query(ExpenseCategory.id).filter(
        ExpenseCategory.company_id == company_id,
        func.lower(ExpenseCategory.name) == name.lower(),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="An expense category with this name already exists")
    row = ExpenseCategory(company_id=company_id, name=name, description=(payload.description or "").strip() or None, is_active=payload.is_active)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.put("/expense-categories/{category_id}", response_model=ExpenseCategoryRead)
def update_expense_category(
    category_id: UUID,
    payload: ExpenseCategoryUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    row = db.get(ExpenseCategory, category_id)
    if not row or row.company_id != company_id_from(context):
        raise HTTPException(status_code=404, detail="Expense category was not found")
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and changes["name"] is not None:
        changes["name"] = changes["name"].strip()
    if "description" in changes:
        changes["description"] = (changes["description"] or "").strip() or None
    for field, value in changes.items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.get("/dashboard", response_model=TreasuryDashboardRead)
def dashboard(
    business_date: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_READ_ROLES)
    company_id = company_id_from(context)
    settings = get_or_create_settings(db, company_id)
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        branch_scope = context.branch_id
    else:
        branch_scope = branch_id
        if branch_scope:
            branch = db.get(CompanyBranch, branch_scope)
            if not branch or branch.company_id != company_id:
                raise HTTPException(status_code=404, detail="Branch was not found in the active company")
    result = build_dashboard(
        db,
        company_id,
        business_date or local_business_date(settings),
        branch_id=branch_scope,
    )
    db.commit()
    return result


@router.get("/days/current", response_model=BranchDailyLedgerRead)
def current_day(
    branch_id: UUID | None = Query(default=None),
    business_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_READ_ROLES)
    company_id = company_id_from(context)
    selected_branch = scoped_branch_id(context, branch_id, db)
    settings = get_or_create_settings(db, company_id)
    ledger = get_or_create_daily_ledger(
        db,
        company_id=company_id,
        branch_id=selected_branch,
        business_date=business_date or local_business_date(settings),
    )
    if ledger.status in {TreasuryDayStatus.OPEN, TreasuryDayStatus.REOPENED}:
        recalculate_daily_ledger(db, ledger)
    db.commit()
    return ledger_with_details(db, ledger.id)


@router.get("/days", response_model=list[BranchDailyLedgerRead])
def list_days(
    date_from: date,
    date_to: date,
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_READ_ROLES)
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="date_to must be on or after date_from")
    query = db.query(BranchDailyLedger).options(
        joinedload(BranchDailyLedger.opening_sources),
        joinedload(BranchDailyLedger.submissions).joinedload(BranchDailySubmission.pdf_file),
    ).filter(
        BranchDailyLedger.company_id == company_id_from(context),
        BranchDailyLedger.business_date >= date_from,
        BranchDailyLedger.business_date <= date_to,
    )
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        query = query.filter(BranchDailyLedger.branch_id == context.branch_id)
    elif branch_id:
        assert_branch_scope(context, branch_id)
        query = query.filter(BranchDailyLedger.branch_id == branch_id)
    return query.order_by(BranchDailyLedger.business_date.desc()).all()


@router.post("/opening-sources", response_model=OpeningSourceRead, status_code=status.HTTP_201_CREATED)
def add_opening_source(
    payload: OpeningSourceCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_WRITE_ROLES)
    branch_id = scoped_branch_id(context, payload.branch_id, db)
    if payload.source_type.value == "owner_contribution":
        require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    source = create_opening_source(
        db,
        company_id=company_id_from(context),
        branch_id=branch_id,
        user_id=context.user.id,
        payload=payload,
    )
    db.commit()
    db.refresh(source)
    return source


@router.post("/opening-sources/{source_id}/void", response_model=OpeningSourceRead)
def void_source(
    source_id: UUID,
    payload: VoidOpeningSourceCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES | {UserRole.BRANCH_MANAGER})
    source = db.get(BranchOpeningSource, source_id)
    if not source or source.company_id != company_id_from(context):
        raise HTTPException(status_code=404, detail="Opening source was not found")
    assert_branch_scope(context, source.branch_id)
    void_opening_source(db, source, user_id=context.user.id, reason=payload.reason)
    db.commit()
    db.refresh(source)
    return source


@router.post("/entries", response_model=TreasuryEntryRead, status_code=status.HTTP_201_CREATED)
def record_entry(
    payload: TreasuryEntryCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_WRITE_ROLES)
    branch_id = scoped_branch_id(context, payload.branch_id, db)
    if payload.entry_type == TreasuryEntryType.OWNER_CONTRIBUTION:
        raise HTTPException(status_code=422, detail="Record owner contributions under Opening balance sources, not daily money-in")
    entry = create_manual_entry(db, company_id=company_id_from(context), branch_id=branch_id, user_id=context.user.id, payload=payload)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/entries/{entry_id}/approve", response_model=TreasuryEntryRead)
def approve_entry(
    entry_id: UUID,
    payload: EntryDecisionCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_APPROVAL_ROLES)
    entry = db.get(TreasuryEntry, entry_id)
    if not entry or entry.company_id != company_id_from(context):
        raise HTTPException(status_code=404, detail="Expense was not found")
    assert_branch_scope(context, entry.branch_id)
    approve_treasury_entry(db, entry, user_id=context.user.id, reason=payload.reason)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/entries/{entry_id}/reject", response_model=TreasuryEntryRead)
def reject_entry(
    entry_id: UUID,
    payload: EntryDecisionCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_APPROVAL_ROLES)
    if not payload.reason or len(payload.reason.strip()) < 5:
        raise HTTPException(status_code=422, detail="A rejection reason of at least five characters is required")
    entry = db.get(TreasuryEntry, entry_id)
    if not entry or entry.company_id != company_id_from(context):
        raise HTTPException(status_code=404, detail="Expense was not found")
    assert_branch_scope(context, entry.branch_id)
    reject_treasury_entry(db, entry, user_id=context.user.id, reason=payload.reason)
    db.commit()
    db.refresh(entry)
    return entry


@router.post("/entries/{entry_id}/void", response_model=TreasuryEntryRead)
def void_entry(
    entry_id: UUID,
    payload: VoidEntryCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_APPROVAL_ROLES)
    entry = db.get(TreasuryEntry, entry_id)
    if not entry or entry.company_id != company_id_from(context):
        raise HTTPException(status_code=404, detail="Money movement was not found")
    assert_branch_scope(context, entry.branch_id)
    void_treasury_entry(db, entry, user_id=context.user.id, reason=payload.reason)
    db.commit()
    db.refresh(entry)
    return entry


@router.get("/submissions", response_model=BranchDailySubmissionListRead)
def list_submissions(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    automatic: bool | None = Query(default=None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_READ_ROLES)
    company_id = company_id_from(context)
    query = db.query(BranchDailySubmission).options(joinedload(BranchDailySubmission.pdf_file)).filter(
        BranchDailySubmission.company_id == company_id
    )
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        query = query.filter(BranchDailySubmission.branch_id == context.branch_id)
    elif branch_id:
        branch = db.get(CompanyBranch, branch_id)
        if not branch or branch.company_id != company_id:
            raise HTTPException(status_code=404, detail="Branch was not found in the active company")
        query = query.filter(BranchDailySubmission.branch_id == branch_id)
    if date_from:
        query = query.filter(BranchDailySubmission.business_date >= date_from)
    if date_to:
        query = query.filter(BranchDailySubmission.business_date <= date_to)
    if automatic is not None:
        query = query.filter(BranchDailySubmission.is_automatic.is_(automatic))
    total = query.count()
    items = query.order_by(
        BranchDailySubmission.business_date.desc(),
        BranchDailySubmission.sequence_number.desc(),
        BranchDailySubmission.submitted_at.desc(),
    ).offset(skip).limit(limit).all()
    return BranchDailySubmissionListRead(items=items, total=total, skip=skip, limit=limit)


@router.get("/submissions/{submission_id}", response_model=BranchDailySubmissionRead)
def get_submission(
    submission_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_READ_ROLES)
    row = db.query(BranchDailySubmission).options(joinedload(BranchDailySubmission.pdf_file)).filter(
        BranchDailySubmission.id == submission_id,
        BranchDailySubmission.company_id == company_id_from(context),
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Branch submission was not found")
    assert_branch_scope(context, row.branch_id)
    if not row.pdf_file_id:
        ensure_branch_submission_pdf(db, row)
        db.commit()
        row = db.query(BranchDailySubmission).options(joinedload(BranchDailySubmission.pdf_file)).filter(BranchDailySubmission.id == row.id).first()
    return row


@router.post("/submissions/{submission_id}/regenerate-pdf", response_model=BranchDailySubmissionRead)
def regenerate_submission_pdf(
    submission_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES | {UserRole.BRANCH_MANAGER, UserRole.FINANCE_OFFICER})
    row = db.query(BranchDailySubmission).filter(
        BranchDailySubmission.id == submission_id,
        BranchDailySubmission.company_id == company_id_from(context),
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Branch submission was not found")
    assert_branch_scope(context, row.branch_id)
    ensure_branch_submission_pdf(db, row, force=True)
    db.commit()
    return db.query(BranchDailySubmission).options(joinedload(BranchDailySubmission.pdf_file)).filter(BranchDailySubmission.id == row.id).first()


@router.post("/days/{ledger_id}/submit", response_model=BranchDailySubmissionRead)
def submit_day(
    ledger_id: UUID,
    payload: DailySubmissionCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_WRITE_ROLES)
    ledger = db.get(BranchDailyLedger, ledger_id)
    if not ledger or ledger.company_id != company_id_from(context):
        raise HTTPException(status_code=404, detail="Branch day was not found")
    assert_branch_scope(context, ledger.branch_id)
    submission = submit_daily_ledger(
        db,
        ledger,
        user_id=context.user.id,
        declared_closing_balance=payload.declared_closing_balance,
        notes=payload.notes,
        automatic=False,
    )
    db.commit()
    db.refresh(submission)
    return submission


@router.post("/days/{ledger_id}/reopen", response_model=BranchDailyLedgerRead)
def reopen_day(
    ledger_id: UUID,
    payload: ReopenDayCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    settings = get_or_create_settings(db, company_id_from(context))
    allowed = COMPANY_MANAGEMENT_ROLES | ({UserRole.BRANCH_MANAGER} if settings.allow_branch_reopen else set())
    require_tenant_roles(context, allowed)
    ledger = db.get(BranchDailyLedger, ledger_id)
    if not ledger or ledger.company_id != company_id_from(context):
        raise HTTPException(status_code=404, detail="Branch day was not found")
    assert_branch_scope(context, ledger.branch_id)
    reopen_daily_ledger(db, ledger, reason=payload.reason)
    db.commit()
    return ledger_with_details(db, ledger.id)


@router.post("/days/{ledger_id}/review", response_model=BranchDailyLedgerRead)
def review_day(
    ledger_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    ledger = db.get(BranchDailyLedger, ledger_id)
    if not ledger or ledger.company_id != company_id_from(context):
        raise HTTPException(status_code=404, detail="Branch day was not found")
    if ledger.status not in {TreasuryDayStatus.SUBMITTED, TreasuryDayStatus.AUTO_SUBMITTED}:
        raise HTTPException(status_code=409, detail="Only submitted branch days can be reviewed")
    ledger.status = TreasuryDayStatus.REVIEWED
    ledger.reviewed_at = datetime.now(timezone.utc)
    ledger.reviewed_by_user_id = context.user.id
    db.commit()
    return ledger_with_details(db, ledger.id)


@router.get("/transfers", response_model=list[BranchFundingTransferRead])
def list_transfers(
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_READ_ROLES)
    query = db.query(BranchFundingTransfer).filter(BranchFundingTransfer.company_id == company_id_from(context))
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        query = query.filter((BranchFundingTransfer.source_branch_id == context.branch_id) | (BranchFundingTransfer.target_branch_id == context.branch_id))
    if date_from:
        query = query.filter(BranchFundingTransfer.business_date >= date_from)
    if date_to:
        query = query.filter(BranchFundingTransfer.business_date <= date_to)
    return query.order_by(BranchFundingTransfer.business_date.desc(), BranchFundingTransfer.created_at.desc()).all()


@router.post("/transfers", response_model=BranchFundingTransferRead, status_code=status.HTTP_201_CREATED)
def create_transfer(
    payload: BranchFundingTransferCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_TRANSFER_ROLES)
    company_id = company_id_from(context)
    settings = get_or_create_settings(db, company_id)
    if context.role == UserRole.BRANCH_MANAGER and context.branch_id != settings.headquarters_branch_id:
        raise HTTPException(status_code=403, detail="Only the headquarters manager may issue branch funds")
    transfer = issue_branch_funding(
        db,
        company_id=company_id,
        target_branch_id=payload.target_branch_id,
        amount=payload.amount,
        payment_method=payload.payment_method,
        business_date=payload.business_date or local_business_date(settings),
        user_id=context.user.id,
        proof_reference=payload.proof_reference,
        proof_url=payload.proof_url,
        notes=payload.notes,
    )
    db.commit()
    db.refresh(transfer)
    return transfer


@router.post("/transfers/{transfer_id}/receive", response_model=BranchFundingTransferRead)
def receive_transfer(
    transfer_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_TRANSFER_ROLES)
    transfer = db.get(BranchFundingTransfer, transfer_id)
    if not transfer or transfer.company_id != company_id_from(context):
        raise HTTPException(status_code=404, detail="Branch funding transfer was not found")
    if context.role not in COMPANY_MANAGEMENT_ROLES:
        assert_branch_scope(context, transfer.target_branch_id)
    receive_branch_funding(db, transfer, context.user.id)
    db.commit()
    db.refresh(transfer)
    return transfer


@router.get("/integrity", response_model=FinancialIntegrityReportRead)
def financial_integrity(
    business_date: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_READ_ROLES)
    company_id = company_id_from(context)
    settings = get_or_create_settings(db, company_id)
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        branch_scope = context.branch_id
    else:
        branch_scope = branch_id
        if branch_scope:
            branch = db.get(CompanyBranch, branch_scope)
            if not branch or branch.company_id != company_id:
                raise HTTPException(status_code=404, detail="Branch was not found in the active company")
    return build_financial_integrity_report(
        db,
        company_id=company_id,
        business_date=business_date or local_business_date(settings),
        branch_id=branch_scope,
    )


@router.post("/integrity/repair", response_model=FinancialIntegrityRepairRead)
def repair_integrity(
    business_date: date | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    company_id = company_id_from(context)
    settings = get_or_create_settings(db, company_id)
    branch_scope = branch_id
    if branch_scope:
        branch = db.get(CompanyBranch, branch_scope)
        if not branch or branch.company_id != company_id:
            raise HTTPException(status_code=404, detail="Branch was not found in the active company")
    result = repair_financial_integrity(
        db,
        company_id=company_id,
        business_date=business_date or local_business_date(settings),
        branch_id=branch_scope,
    )
    db.commit()
    return result


@router.get("/statements", response_model=TreasuryStatementRead)
def statement(
    date_from: date,
    date_to: date,
    branch_id: UUID | None = Query(default=None),
    payment_methods: list[PaymentMethod] | None = Query(default=None),
    directions: list[TreasuryDirection] | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_READ_ROLES)
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="date_to must be on or after date_from")
    selected_branch = branch_id
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        selected_branch = context.branch_id
    elif selected_branch:
        assert_branch_scope(context, selected_branch)
    return build_statement(
        db,
        company_id=company_id_from(context),
        date_from=date_from,
        date_to=date_to,
        branch_id=selected_branch,
        methods=payment_methods,
        directions=directions,
    )


@router.get("/statements/export.csv")
def export_statement_csv(
    date_from: date,
    date_to: date,
    branch_id: UUID | None = Query(default=None),
    payment_methods: list[PaymentMethod] | None = Query(default=None),
    directions: list[TreasuryDirection] | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, TREASURY_READ_ROLES)
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="date_to must be on or after date_from")
    selected_branch = branch_id
    if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        selected_branch = context.branch_id
    elif selected_branch:
        assert_branch_scope(context, selected_branch)
    statement_data = build_statement(
        db,
        company_id=company_id_from(context),
        date_from=date_from,
        date_to=date_to,
        branch_id=selected_branch,
        methods=payment_methods,
        directions=directions,
    )
    branches = db.query(CompanyBranch).filter(CompanyBranch.company_id == company_id_from(context)).all()
    content = statement_csv(statement_data, {branch.id: branch.name for branch in branches})
    filename = f"loanhub-money-statement-{date_from}-{date_to}.csv"
    return Response(content=content, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/run-daily-cycle")
def run_daily_cycle(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    company_id = company_id_from(context)
    opened = auto_open_due_ledgers(db, company_id=company_id)
    submitted = auto_submit_due_ledgers(db, company_id=company_id)
    return {"opened_ledgers": opened, "submitted_ledgers": submitted}


@router.post("/auto-submit-due", include_in_schema=False)
def run_auto_submission(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    return {"submitted_ledgers": auto_submit_due_ledgers(db, company_id=company_id_from(context))}
