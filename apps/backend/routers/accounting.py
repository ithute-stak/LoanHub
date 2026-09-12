from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, FINANCE_ROLES, TenantContext, get_user_context, require_tenant_roles
from database.models.enums import UserRole
from database.models.accounting import AccountingAccount, JournalEntry, JournalLine
from database.models.branch import CompanyBranch
from database.schemas.accounting import (
    AccountingAccountCreate,
    AccountingAccountRead,
    AccountingAccountUpdate,
    FinancialStatementLine,
    FinancialStatementRead,
    JournalEntryCreate,
    JournalEntryRead,
    TrialBalanceLine,
    TrialBalanceRead,
)
from database.session import get_db
from services.accounting_service import create_entry, ensure_chart, entry_query, scope_key


router = APIRouter(prefix="/accounting", tags=["Accounting"])
READ_ROLES = FINANCE_ROLES | {UserRole.AUDITOR, UserRole.COMPLIANCE_OFFICER}


def resolve_scope(context: TenantContext, company_id: UUID | None):
    if context.is_platform_admin:
        return company_id
    if not context.company_id:
        raise HTTPException(status_code=403, detail="Company accounting access is required")
    return context.company_id


def require_read(context: TenantContext):
    if not context.is_platform_admin:
        require_tenant_roles(context, READ_ROLES)


def require_write(context: TenantContext):
    if not context.is_platform_admin:
        require_tenant_roles(context, FINANCE_ROLES)


def resolve_branch_scope(
    db: Session,
    context: TenantContext,
    company_id: UUID | None,
    branch_id: UUID | None,
) -> UUID | None:
    if context.is_platform_admin:
        selected = branch_id
    elif context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES:
        selected = context.branch_id
    else:
        selected = branch_id
    if selected and company_id:
        branch = db.get(CompanyBranch, selected)
        if not branch or branch.company_id != company_id:
            raise HTTPException(status_code=404, detail="Branch was not found in the active company")
    return selected


@router.post("/bootstrap", response_model=list[AccountingAccountRead])
def bootstrap_chart(
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    accounts = ensure_chart(db, company_id=selected_company_id)
    db.commit()
    return accounts


@router.get("/accounts", response_model=list[AccountingAccountRead])
def list_accounts(
    company_id: UUID | None = None,
    include_inactive: bool = False,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    key, _ = scope_key(selected_company_id)
    ensure_chart(db, company_id=selected_company_id)
    db.commit()
    query = db.query(AccountingAccount).filter(AccountingAccount.scope_key == key)
    if not include_inactive:
        query = query.filter(AccountingAccount.is_active.is_(True))
    return query.order_by(AccountingAccount.code.asc()).all()


@router.post("/accounts", response_model=AccountingAccountRead, status_code=status.HTTP_201_CREATED)
def create_account(
    payload: AccountingAccountCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    key, scope_type = scope_key(selected_company_id)
    account = AccountingAccount(
        scope_key=key,
        scope_type=scope_type,
        company_id=selected_company_id,
        branch_id=payload.branch_id,
        parent_id=payload.parent_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        account_type=payload.account_type,
        normal_balance=payload.normal_balance,
        description=payload.description,
        is_system=False,
        is_active=True,
    )
    db.add(account)
    try:
        db.commit()
        db.refresh(account)
        return account
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="This account code already exists") from error


@router.patch("/accounts/{account_id}", response_model=AccountingAccountRead)
def update_account(
    account_id: UUID,
    payload: AccountingAccountUpdate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    key, _ = scope_key(selected_company_id)
    account = db.query(AccountingAccount).filter(
        AccountingAccount.id == account_id,
        AccountingAccount.scope_key == key,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Accounting account not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    db.commit()
    db.refresh(account)
    return account


@router.get("/journal-entries", response_model=list[JournalEntryRead])
def list_entries(
    company_id: UUID | None = None,
    status_filter: str | None = Query(None, alias="status"),
    from_date: date | None = None,
    to_date: date | None = None,
    branch_id: UUID | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    key, _ = scope_key(selected_company_id)
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    query = entry_query(db, key)
    if selected_branch_id:
        query = query.filter(JournalEntry.branch_id == selected_branch_id)
    if status_filter:
        query = query.filter(JournalEntry.status == status_filter)
    if from_date:
        query = query.filter(JournalEntry.entry_date >= from_date)
    if to_date:
        query = query.filter(JournalEntry.entry_date <= to_date)
    return query.order_by(JournalEntry.entry_date.desc(), JournalEntry.created_at.desc()).offset(skip).limit(limit).all()


@router.post("/journal-entries", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def add_entry(
    payload: JournalEntryCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, payload.branch_id)
    entry = create_entry(
        db,
        company_id=selected_company_id,
        branch_id=selected_branch_id,
        created_by_user_id=context.user.id,
        entry_date=payload.entry_date,
        description=payload.description,
        reference_type=payload.reference_type,
        reference_id=payload.reference_id,
        lines=[item.model_dump() for item in payload.lines],
    )
    db.commit()
    return entry_query(db, entry.scope_key).filter(JournalEntry.id == entry.id).first()


@router.post("/journal-entries/{entry_id}/post", response_model=JournalEntryRead)
def post_entry(
    entry_id: UUID,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    key, _ = scope_key(selected_company_id)
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, None)
    entry_query_scoped = entry_query(db, key).filter(JournalEntry.id == entry_id)
    if selected_branch_id:
        entry_query_scoped = entry_query_scoped.filter(JournalEntry.branch_id == selected_branch_id)
    entry = entry_query_scoped.first()
    if not entry:
        raise HTTPException(status_code=404, detail="Journal entry not found")
    if entry.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft entries can be posted")
    if entry.created_by_user_id == context.user.id:
        raise HTTPException(status_code=409, detail="Maker/checker control: the journal creator cannot post it")
    from services.governance_control_service import ensure_accounting_period_open

    ensure_accounting_period_open(db, company_id=selected_company_id, entry_date=entry.entry_date)
    entry.status = "posted"
    entry.posted_by_user_id = context.user.id
    entry.posted_at = datetime.now(timezone.utc)
    db.commit()
    return entry_query(db, key).filter(JournalEntry.id == entry.id).first()


def trial_balance_data(db: Session, key: str, from_date=None, to_date=None, branch_id: UUID | None = None):
    query = db.query(
        AccountingAccount.id,
        AccountingAccount.code,
        AccountingAccount.name,
        AccountingAccount.account_type,
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalLine, JournalLine.account_id == AccountingAccount.id).join(
        JournalEntry, JournalEntry.id == JournalLine.journal_entry_id
    ).filter(
        AccountingAccount.scope_key == key,
        JournalEntry.status == "posted",
    )
    if from_date:
        query = query.filter(JournalEntry.entry_date >= from_date)
    if to_date:
        query = query.filter(JournalEntry.entry_date <= to_date)
    if branch_id:
        query = query.filter(JournalEntry.branch_id == branch_id)
    rows = query.group_by(
        AccountingAccount.id,
        AccountingAccount.code,
        AccountingAccount.name,
        AccountingAccount.account_type,
    ).order_by(AccountingAccount.code).all()
    lines = []
    for account_id, code, name, account_type, debit, credit in rows:
        debit = Decimal(debit)
        credit = Decimal(credit)
        lines.append(TrialBalanceLine(
            account_id=account_id,
            code=code,
            name=name,
            account_type=account_type,
            debit=debit,
            credit=credit,
            balance=debit - credit,
        ))
    return lines


@router.get("/trial-balance", response_model=TrialBalanceRead)
def trial_balance(
    company_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    key, _ = scope_key(selected_company_id)
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    lines = trial_balance_data(db, key, from_date, to_date, selected_branch_id)
    return TrialBalanceRead(
        from_date=from_date,
        to_date=to_date,
        lines=lines,
        total_debit=sum((line.debit for line in lines), Decimal("0")),
        total_credit=sum((line.credit for line in lines), Decimal("0")),
    )


def statement(
    db: Session,
    *,
    key: str,
    statement_name: str,
    account_types: set[str],
    from_date: date | None,
    to_date: date,
    branch_id: UUID | None = None,
):
    lines = trial_balance_data(db, key, from_date, to_date, branch_id)
    sections: dict[str, list[FinancialStatementLine]] = {}
    totals: dict[str, Decimal] = {}
    for line in lines:
        if line.account_type not in account_types:
            continue
        amount = line.credit - line.debit if line.account_type in {"revenue", "liability", "equity"} else line.debit - line.credit
        sections.setdefault(line.account_type, []).append(
            FinancialStatementLine(code=line.code, name=line.name, amount=amount)
        )
        totals[line.account_type] = totals.get(line.account_type, Decimal("0")) + amount
    if statement_name == "profit_and_loss":
        totals["net_profit"] = totals.get("revenue", Decimal("0")) - totals.get("expense", Decimal("0"))
    return FinancialStatementRead(
        statement=statement_name,
        from_date=from_date,
        to_date=to_date,
        sections=sections,
        totals=totals,
    )


@router.get("/profit-and-loss", response_model=FinancialStatementRead)
def profit_and_loss(
    company_id: UUID | None = None,
    from_date: date | None = None,
    to_date: date = Query(default_factory=date.today),
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    key, _ = scope_key(selected_company_id)
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    return statement(db, key=key, statement_name="profit_and_loss", account_types={"revenue", "expense"}, from_date=from_date, to_date=to_date, branch_id=selected_branch_id)


@router.get("/balance-sheet", response_model=FinancialStatementRead)
def balance_sheet(
    company_id: UUID | None = None,
    to_date: date = Query(default_factory=date.today),
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    key, _ = scope_key(selected_company_id)
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    return statement(db, key=key, statement_name="balance_sheet", account_types={"asset", "liability", "equity"}, from_date=None, to_date=to_date, branch_id=selected_branch_id)
