from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    TenantContext,
    get_user_context,
    require_tenant_roles,
)
from database.models.accounting import AccountingAccount, JournalEntry, JournalLine
from database.models.branch import CompanyBranch
from database.models.enums import UserRole
from database.schemas.accounting import (
    AccountingAccountCreate,
    AccountingAccountRead,
    AccountingAccountUpdate,
    AccountingDashboardRead,
    ExpensePostCreate,
    FinancialStatementLine,
    FinancialStatementRead,
    JournalEntryCreate,
    JournalEntryRead,
    LedgerLineRead,
    LedgerRead,
    TrialBalanceLine,
    TrialBalanceRead,
)
from database.session import get_db
from services.accounting_service import (
    accounting_business_date,
    create_entry,
    ensure_chart,
    entry_query,
    ledger_rows,
    post_expense,
    scope_key,
)


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


def resolve_branch_scope(db: Session, context: TenantContext, company_id: UUID | None, branch_id: UUID | None):
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
    rows = ensure_chart(db, company_id=selected_company_id)
    db.commit()
    return rows


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
    query = entry_query(db, key).filter(JournalEntry.id == entry_id)
    if selected_branch_id:
        query = query.filter(JournalEntry.branch_id == selected_branch_id)
    entry = query.first()
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


@router.post("/expenses", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def record_expense(
    payload: ExpensePostCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Replacement for the old expense module: expenses are accounting entries."""
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company for company expenses")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, payload.branch_id)
    reference = payload.external_reference or str(uuid4())
    entry = post_expense(
        db,
        company_id=selected_company_id,
        branch_id=selected_branch_id,
        amount=payload.amount,
        expense_account_code=payload.expense_account_code,
        description=payload.description,
        reference_id=reference,
        user_id=context.user.id,
        paid_now=payload.paid_now,
        entry_date=payload.entry_date,
    )
    db.commit()
    return entry_query(db, entry.scope_key).filter(JournalEntry.id == entry.id).first()


def trial_balance_data(db: Session, key: str, from_date=None, to_date=None, branch_id: UUID | None = None):
    query = db.query(
        AccountingAccount.id,
        AccountingAccount.code,
        AccountingAccount.name,
        AccountingAccount.account_type,
        AccountingAccount.normal_balance,
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).outerjoin(JournalLine, JournalLine.account_id == AccountingAccount.id).outerjoin(
        JournalEntry, JournalEntry.id == JournalLine.journal_entry_id
    ).filter(AccountingAccount.scope_key == key)

    # Keep empty chart accounts visible; filters on JournalEntry therefore need
    # to tolerate NULL rows from the outer join.
    query = query.filter((JournalEntry.id.is_(None)) | (JournalEntry.status == "posted"))
    if from_date:
        query = query.filter((JournalEntry.id.is_(None)) | (JournalEntry.entry_date >= from_date))
    if to_date:
        query = query.filter((JournalEntry.id.is_(None)) | (JournalEntry.entry_date <= to_date))
    if branch_id:
        query = query.filter((JournalEntry.id.is_(None)) | (JournalEntry.branch_id == branch_id))

    rows = query.group_by(
        AccountingAccount.id,
        AccountingAccount.code,
        AccountingAccount.name,
        AccountingAccount.account_type,
        AccountingAccount.normal_balance,
    ).order_by(AccountingAccount.code).all()

    lines = []
    for account_id, code, name, account_type, normal_balance, debit, credit in rows:
        debit, credit = Decimal(debit), Decimal(credit)
        balance = debit - credit if normal_balance == "debit" else credit - debit
        lines.append(TrialBalanceLine(
            account_id=account_id,
            code=code,
            name=name,
            account_type=account_type,
            debit=debit,
            credit=credit,
            balance=balance,
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
    ensure_chart(db, company_id=selected_company_id)
    db.commit()
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


@router.get("/ledger/{account_id}", response_model=LedgerRead)
def account_ledger(
    account_id: UUID,
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
    account = db.query(AccountingAccount).filter(
        AccountingAccount.id == account_id,
        AccountingAccount.scope_key == key,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Accounting account not found")

    opening = Decimal("0.00")
    if from_date:
        opening_q = db.query(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
            JournalLine.account_id == account_id,
            JournalEntry.scope_key == key,
            JournalEntry.status == "posted",
            JournalEntry.entry_date < from_date,
        )
        if selected_branch_id:
            opening_q = opening_q.filter(JournalEntry.branch_id == selected_branch_id)
        debit, credit = opening_q.first()
        opening = Decimal(debit) - Decimal(credit)
        if account.normal_balance == "credit":
            opening = -opening

    running = opening
    lines = []
    for journal_line, entry in ledger_rows(
        db, key, account_id, from_date=from_date, to_date=to_date, branch_id=selected_branch_id
    ):
        movement = Decimal(journal_line.debit) - Decimal(journal_line.credit)
        if account.normal_balance == "credit":
            movement = -movement
        running += movement
        lines.append(LedgerLineRead(
            entry_id=entry.id,
            entry_number=entry.entry_number,
            entry_date=entry.entry_date,
            description=journal_line.description or entry.description,
            reference_type=entry.reference_type,
            reference_id=entry.reference_id,
            debit=Decimal(journal_line.debit),
            credit=Decimal(journal_line.credit),
            running_balance=running,
        ))
    return LedgerRead(
        account=account,
        from_date=from_date,
        to_date=to_date,
        opening_balance=opening,
        closing_balance=running,
        lines=lines,
    )


def statement(db: Session, *, key: str, statement_name: str, account_types: set[str], from_date, to_date, branch_id=None):
    lines = trial_balance_data(db, key, from_date, to_date, branch_id)
    sections: dict[str, list[FinancialStatementLine]] = {}
    totals: dict[str, Decimal] = {}
    for line in lines:
        if line.account_type not in account_types:
            continue
        amount = line.balance
        sections.setdefault(line.account_type, []).append(
            FinancialStatementLine(code=line.code, name=line.name, amount=amount)
        )
        totals[line.account_type] = totals.get(line.account_type, Decimal("0")) + amount

    if statement_name == "income_statement":
        totals["net_profit"] = totals.get("revenue", Decimal("0")) - totals.get("expense", Decimal("0"))
    elif statement_name == "statement_of_financial_position":
        totals["net_assets"] = totals.get("asset", Decimal("0")) - totals.get("liability", Decimal("0"))
        totals["equity_check"] = totals["net_assets"] - totals.get("equity", Decimal("0"))
    return FinancialStatementRead(
        statement=statement_name,
        from_date=from_date,
        to_date=to_date,
        sections=sections,
        totals=totals,
    )


@router.get("/income-statement", response_model=FinancialStatementRead)
@router.get("/profit-and-loss", response_model=FinancialStatementRead, include_in_schema=False)
def income_statement(
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
    return statement(
        db, key=key, statement_name="income_statement",
        account_types={"revenue", "expense"}, from_date=from_date, to_date=to_date,
        branch_id=selected_branch_id,
    )


@router.get("/statement-of-financial-position", response_model=FinancialStatementRead)
@router.get("/balance-sheet", response_model=FinancialStatementRead, include_in_schema=False)
def statement_of_financial_position(
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
    return statement(
        db, key=key, statement_name="statement_of_financial_position",
        account_types={"asset", "liability", "equity"}, from_date=None, to_date=to_date,
        branch_id=selected_branch_id,
    )


@router.get("/dashboard", response_model=AccountingDashboardRead)
def accounting_dashboard(
    company_id: UUID | None = None,
    as_of: date = Query(default_factory=date.today),
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    key, _ = scope_key(selected_company_id)
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    lines = trial_balance_data(db, key, None, as_of, selected_branch_id)
    by_code = {line.code: line.balance for line in lines}
    totals = {}
    for line in lines:
        totals[line.account_type] = totals.get(line.account_type, Decimal("0")) + line.balance
    total_debit = sum((line.debit for line in lines), Decimal("0"))
    total_credit = sum((line.credit for line in lines), Decimal("0"))
    revenue = totals.get("revenue", Decimal("0"))
    expenses = totals.get("expense", Decimal("0"))
    return AccountingDashboardRead(
        as_of=as_of,
        cash_and_bank=by_code.get("1000", Decimal("0")) + by_code.get("1010", Decimal("0")),
        loans_receivable=by_code.get("1100", Decimal("0")) + by_code.get("1110", Decimal("0")) + by_code.get("1120", Decimal("0")),
        total_assets=totals.get("asset", Decimal("0")),
        total_liabilities=totals.get("liability", Decimal("0")),
        equity=totals.get("equity", Decimal("0")),
        revenue=revenue,
        expenses=expenses,
        net_profit=revenue - expenses,
        trial_balance_difference=total_debit - total_credit,
    )


@router.get("/ratios")
def accounting_ratios(
    company_id: UUID | None = None,
    as_of: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Basic financial-analysis ratios derived from posted ledger balances."""
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    key, _ = scope_key(selected_company_id)
    lines = trial_balance_data(db, key, None, as_of)
    totals = {}
    by_code = {line.code: line.balance for line in lines}
    for line in lines:
        totals[line.account_type] = totals.get(line.account_type, Decimal("0")) + line.balance
    assets = totals.get("asset", Decimal("0"))
    liabilities = totals.get("liability", Decimal("0"))
    equity = totals.get("equity", Decimal("0"))
    revenue = totals.get("revenue", Decimal("0"))
    expenses = totals.get("expense", Decimal("0"))
    profit = revenue - expenses
    liquid = by_code.get("1000", Decimal("0")) + by_code.get("1010", Decimal("0"))
    receivables = by_code.get("1100", Decimal("0")) + by_code.get("1110", Decimal("0")) + by_code.get("1120", Decimal("0"))

    def ratio(n, d):
        return None if not d else (n / d).quantize(Decimal("0.0001"))

    return {
        "as_of": as_of,
        "net_profit_margin": ratio(profit, revenue),
        "return_on_assets": ratio(profit, assets),
        "debt_to_equity": ratio(liabilities, equity),
        "cash_to_liabilities": ratio(liquid, liabilities),
        "loan_receivables_to_assets": ratio(receivables, assets),
    }
