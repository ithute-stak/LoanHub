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
from database.models.governance_control import ApprovalRequest, BankStatementLine
from database.models.reconciliation import ReconciliationBatch
from database.schemas.accounting import (
    AccountingAccountCreate,
    AccountingAccountRead,
    AccountingAccountUpdate,
    AccountingDashboardRead,
    AccrualAdjustmentCreate,
    DepreciationAdjustmentCreate,
    DoubtfulDebtAllowanceCreate,
    ExpensePostCreate,
    FinancialStatementLine,
    FixedAssetCreate,
    FixedAssetDepreciationRun,
    ElectronicClearingSettlementCreate,
    FixedAssetDisposeCreate,
    FixedAssetRead,
    FinancialStatementRead,
    JournalEntryCreate,
    JournalEntryRead,
    LedgerLineRead,
    LedgerRead,
    LoanWriteOffCreate,
    WrittenOffLoanRecoveryCreate,
    PrepaymentAdjustmentCreate,
    PeriodAdjustmentReversalCreate,
    TrialBalanceLine,
    TrialBalanceRead,
    SuspenseCorrectionCreate,
    VatTransactionCreate,
)
from database.session import get_db
from services.accounting_service import (
    accounting_business_date,
    asset_payload,
    bank_settlement_chain,
    create_fixed_asset,
    calculate_fixed_asset_depreciation,
    create_entry,
    ensure_chart,
    entry_query,
    cash_flow_statement,
    fixed_asset_query,
    ledger_rows,
    loan_receivables_control_reconciliation,
    post_accrual_adjustment,
    post_depreciation_adjustment,
    post_doubtful_debt_allowance,
    post_expense,
    post_prepayment_adjustment,
    reverse_period_adjustment,
    post_vat_transaction,
    post_suspense_correction,
    post_fixed_asset_depreciation,
    post_loan_write_off,
    record_written_off_loan_recovery,
    dispose_fixed_asset,
    electronic_clearing_aging,
    electronic_clearing_reconciliation,
    depreciate_all_fixed_assets_for_period,
    period_close_pack,
    record_electronic_clearing_settlement,
    scope_key,
    transaction_accounting_coverage,
    validate_postable_entry,
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
    validate_postable_entry(db, entry)
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
        # Trial-balance balances stay on the conventional debit-minus-credit basis.
        # Statement presentation converts credit-balance classes later. This preserves
        # contra-assets (e.g. accumulated depreciation) as negative assets instead of
        # incorrectly adding them to gross assets.
        balance = debit - credit
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
        if line.account_type in {"liability", "equity", "revenue"}:
            amount = -line.balance
        else:
            amount = line.balance
        sections.setdefault(line.account_type, []).append(
            FinancialStatementLine(code=line.code, name=line.name, amount=amount)
        )
        totals[line.account_type] = totals.get(line.account_type, Decimal("0")) + amount

    if statement_name == "income_statement":
        totals["net_profit"] = totals.get("revenue", Decimal("0")) - totals.get("expense", Decimal("0"))
    elif statement_name == "statement_of_financial_position":
        # Revenue and expense accounts represent profit that has increased or
        # decreased equity even before a formal year-end transfer to retained
        # earnings is posted. Present that unclosed result explicitly so the
        # statement satisfies Assets = Liabilities + Equity.
        pnl_lines = trial_balance_data(db, key, None, to_date, branch_id)
        cumulative_revenue = sum(
            (-line.balance for line in pnl_lines if line.account_type == "revenue"),
            Decimal("0"),
        )
        cumulative_expense = sum(
            (line.balance for line in pnl_lines if line.account_type == "expense"),
            Decimal("0"),
        )
        current_earnings = cumulative_revenue - cumulative_expense
        sections["current_earnings"] = [
            FinancialStatementLine(
                code="CURRENT-EARNINGS",
                name="Cumulative unclosed profit / (loss)",
                amount=current_earnings,
            )
        ]
        totals["current_earnings"] = current_earnings
        totals["total_equity"] = totals.get("equity", Decimal("0")) + current_earnings
        totals["net_assets"] = totals.get("asset", Decimal("0")) - totals.get("liability", Decimal("0"))
        totals["equity_check"] = totals["net_assets"] - totals["total_equity"]
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
    def presented(line):
        return -line.balance if line.account_type in {"liability", "equity", "revenue"} else line.balance

    by_code = {line.code: presented(line) for line in lines}
    totals = {}
    for line in lines:
        totals[line.account_type] = totals.get(line.account_type, Decimal("0")) + presented(line)
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
        equity=totals.get("equity", Decimal("0")) + (revenue - expenses),
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
    def presented(line):
        return -line.balance if line.account_type in {"liability", "equity", "revenue"} else line.balance

    totals = {}
    by_code = {line.code: presented(line) for line in lines}
    for line in lines:
        totals[line.account_type] = totals.get(line.account_type, Decimal("0")) + presented(line)
    assets = totals.get("asset", Decimal("0"))
    liabilities = totals.get("liability", Decimal("0"))
    book_equity = totals.get("equity", Decimal("0"))
    revenue = totals.get("revenue", Decimal("0"))
    expenses = totals.get("expense", Decimal("0"))
    profit = revenue - expenses
    equity = book_equity + profit
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


@router.post("/adjustments/depreciation", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def depreciation_adjustment(
    payload: DepreciationAdjustmentCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    branch = resolve_branch_scope(db, context, selected_company_id, payload.branch_id)
    entry = post_depreciation_adjustment(
        db, company_id=selected_company_id, branch_id=branch, amount=payload.amount,
        description=payload.description, reference_id=payload.reference_id or str(uuid4()),
        user_id=context.user.id, entry_date=payload.entry_date,
    )
    db.commit()
    return entry_query(db, entry.scope_key).filter(JournalEntry.id == entry.id).first()


@router.post("/adjustments/accrual", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def accrual_adjustment(
    payload: AccrualAdjustmentCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    branch = resolve_branch_scope(db, context, selected_company_id, payload.branch_id)
    entry = post_accrual_adjustment(
        db, company_id=selected_company_id, branch_id=branch, amount=payload.amount,
        expense_account_code=payload.expense_account_code, description=payload.description,
        reference_id=payload.reference_id or str(uuid4()), user_id=context.user.id,
        entry_date=payload.entry_date,
    )
    db.commit()
    return entry_query(db, entry.scope_key).filter(JournalEntry.id == entry.id).first()


@router.post("/adjustments/prepayment", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def prepayment_adjustment(
    payload: PrepaymentAdjustmentCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    branch = resolve_branch_scope(db, context, selected_company_id, payload.branch_id)
    entry = post_prepayment_adjustment(
        db, company_id=selected_company_id, branch_id=branch, amount=payload.amount,
        expense_account_code=payload.expense_account_code, description=payload.description,
        reference_id=payload.reference_id or str(uuid4()), user_id=context.user.id,
        entry_date=payload.entry_date,
    )
    db.commit()
    return entry_query(db, entry.scope_key).filter(JournalEntry.id == entry.id).first()


@router.post("/adjustments/doubtful-debt-allowance", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def doubtful_debt_allowance_adjustment(
    payload: DoubtfulDebtAllowanceCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    branch = resolve_branch_scope(db, context, selected_company_id, payload.branch_id)
    entry = post_doubtful_debt_allowance(
        db, company_id=selected_company_id, branch_id=branch, amount=payload.amount,
        direction=payload.direction, description=payload.description,
        reference_id=payload.reference_id or str(uuid4()), user_id=context.user.id,
        entry_date=payload.entry_date,
    )
    db.commit()
    return entry_query(db, entry.scope_key).filter(JournalEntry.id == entry.id).first()


@router.get("/cash-flow")
def statement_of_cash_flows(
    company_id: UUID | None = None,
    from_date: date = Query(...),
    to_date: date = Query(...),
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")
    return cash_flow_statement(
        db, company_id=selected_company_id, from_date=from_date, to_date=to_date,
        branch_id=selected_branch_id,
    )


@router.post("/vat/transactions", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def post_vat(
    payload: VatTransactionCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    branch = resolve_branch_scope(db, context, selected_company_id, payload.branch_id)
    entry = post_vat_transaction(
        db,
        company_id=selected_company_id,
        branch_id=branch,
        transaction_type=payload.transaction_type,
        net_amount=payload.net_amount,
        vat_amount=payload.vat_amount,
        account_code=payload.account_code,
        settlement_account_code=payload.settlement_account_code,
        vat_registered=payload.vat_registered,
        description=payload.description,
        reference_id=payload.reference_id or str(uuid4()),
        user_id=context.user.id,
        entry_date=payload.entry_date,
    )
    db.commit()
    return entry_query(db, entry.scope_key).filter(JournalEntry.id == entry.id).first()


@router.get("/period-close-checklist")
def period_close_checklist(
    company_id: UUID | None = None,
    to_date: date = Query(default_factory=date.today),
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Control-oriented close checklist before a period can be locked/closed."""
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    key, _ = scope_key(selected_company_id)
    ensure_chart(db, company_id=selected_company_id)
    db.flush()

    lines = trial_balance_data(db, key, None, to_date, selected_branch_id)
    total_debit = sum((line.debit for line in lines), Decimal("0"))
    total_credit = sum((line.credit for line in lines), Decimal("0"))
    suspense = next((line.balance for line in lines if line.code == "2990"), Decimal("0"))

    drafts = db.query(JournalEntry.id).filter(
        JournalEntry.company_id == selected_company_id,
        JournalEntry.entry_date <= to_date,
        JournalEntry.status == "draft",
    )
    unmatched_bank = db.query(BankStatementLine.id).filter(
        BankStatementLine.company_id == selected_company_id,
        BankStatementLine.transaction_date <= to_date,
        BankStatementLine.status == "unmatched",
    )
    approvals = db.query(ApprovalRequest.id).filter(
        ApprovalRequest.company_id == selected_company_id,
        ApprovalRequest.status == "pending",
    )
    open_reconciliations = db.query(ReconciliationBatch.id).filter(
        ReconciliationBatch.company_id == selected_company_id,
        ReconciliationBatch.period_end <= to_date,
        ReconciliationBatch.status != "closed",
    )
    if selected_branch_id:
        drafts = drafts.filter(JournalEntry.branch_id == selected_branch_id)
        unmatched_bank = unmatched_bank.filter(BankStatementLine.branch_id == selected_branch_id)
        approvals = approvals.filter(
            (ApprovalRequest.branch_id == selected_branch_id) | (ApprovalRequest.branch_id.is_(None))
        )
        open_reconciliations = open_reconciliations.filter(
            (ReconciliationBatch.branch_id == selected_branch_id) | (ReconciliationBatch.branch_id.is_(None))
        )

    checks = {
        "trial_balance_balanced": total_debit == total_credit,
        "suspense_cleared": suspense == 0,
        "draft_journals_cleared": drafts.count() == 0,
        "bank_lines_reconciled": unmatched_bank.count() == 0,
        "pending_financial_approvals_cleared": approvals.count() == 0,
        "reconciliation_batches_closed": open_reconciliations.count() == 0,
    }
    return {
        "as_of": to_date,
        "branch_id": str(selected_branch_id) if selected_branch_id else None,
        "ready_to_close": all(checks.values()),
        "checks": checks,
        "amounts": {
            "total_debit": total_debit,
            "total_credit": total_credit,
            "trial_balance_difference": total_debit - total_credit,
            "suspense_balance": suspense,
        },
        "counts": {
            "draft_journals": drafts.count(),
            "unmatched_bank_lines": unmatched_bank.count(),
            "pending_approvals": approvals.count(),
            "open_reconciliation_batches": open_reconciliations.count(),
        },
    }


@router.post("/suspense/corrections", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def suspense_correction(
    payload: SuspenseCorrectionCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Correct an identified posting error through an auditable journal, never by deleting history."""
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    branch = resolve_branch_scope(db, context, selected_company_id, payload.branch_id)
    entry = post_suspense_correction(
        db,
        company_id=selected_company_id,
        branch_id=branch,
        amount=payload.amount,
        target_account_code=payload.target_account_code,
        target_side=payload.target_side,
        description=payload.description,
        reference_id=payload.reference_id or str(uuid4()),
        user_id=context.user.id,
        entry_date=payload.entry_date,
    )
    db.commit()
    return entry_query(db, entry.scope_key).filter(JournalEntry.id == entry.id).first()


@router.get("/assets", response_model=list[FixedAssetRead])
def list_fixed_assets(
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    include_disposed: bool = True,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    query = fixed_asset_query(db, company_id=selected_company_id, branch_id=selected_branch_id)
    if not include_disposed:
        query = query.filter_by(status="active")
    return [asset_payload(row) for row in query.order_by("reference").all()]


@router.post("/assets", response_model=FixedAssetRead, status_code=status.HTTP_201_CREATED)
def register_fixed_asset(
    payload: FixedAssetCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, payload.branch_id)
    asset = create_fixed_asset(
        db,
        company_id=selected_company_id,
        branch_id=selected_branch_id,
        reference=payload.reference,
        name=payload.name,
        description=payload.description,
        acquisition_date=payload.acquisition_date,
        cost=payload.cost,
        residual_value=payload.residual_value,
        useful_life_years=payload.useful_life_years,
        depreciation_method=payload.depreciation_method,
        depreciation_rate=payload.depreciation_rate,
        location=payload.location,
        serial_number=payload.serial_number,
        assigned_to=payload.assigned_to,
        user_id=context.user.id,
        settlement_account_code=payload.settlement_account_code,
        post_acquisition=payload.post_acquisition,
    )
    db.commit()
    db.refresh(asset)
    return asset_payload(asset)


@router.get("/assets/{asset_id}", response_model=FixedAssetRead)
def fixed_asset_detail(
    asset_id: UUID,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, None)
    asset = fixed_asset_query(db, company_id=selected_company_id, branch_id=selected_branch_id).filter_by(id=asset_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Fixed asset not found")
    return asset_payload(asset)


@router.post("/assets/{asset_id}/depreciate")
def depreciate_fixed_asset(
    asset_id: UUID,
    payload: FixedAssetDepreciationRun,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, None)
    asset = fixed_asset_query(db, company_id=selected_company_id, branch_id=selected_branch_id).filter_by(id=asset_id).with_for_update().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Fixed asset not found")
    amount = calculate_fixed_asset_depreciation(asset, period_start=payload.period_start, period_end=payload.period_end)
    entry = post_fixed_asset_depreciation(
        db, asset=asset, period_start=payload.period_start, period_end=payload.period_end,
        user_id=context.user.id,
    )
    db.commit()
    db.refresh(asset)
    return {
        "asset": asset_payload(asset),
        "depreciation_amount": amount,
        "journal_entry_id": str(entry.id) if entry else None,
    }


@router.post("/assets/{asset_id}/dispose")
def dispose_registered_fixed_asset(
    asset_id: UUID,
    payload: FixedAssetDisposeCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, None)
    asset = fixed_asset_query(db, company_id=selected_company_id, branch_id=selected_branch_id).filter_by(id=asset_id).with_for_update().first()
    if not asset:
        raise HTTPException(status_code=404, detail="Fixed asset not found")
    entry = dispose_fixed_asset(
        db,
        asset=asset,
        disposal_date=payload.disposal_date,
        proceeds=payload.proceeds,
        settlement_account_code=payload.settlement_account_code,
        description=payload.description,
        user_id=context.user.id,
    )
    db.commit()
    db.refresh(asset)
    return {"asset": asset_payload(asset), "journal_entry_id": str(entry.id)}


@router.get("/controls/loan-receivables")
def loan_receivables_control(
    company_id: UUID | None = None,
    as_of: date = Query(default_factory=date.today),
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    return loan_receivables_control_reconciliation(
        db,
        company_id=selected_company_id,
        as_of=as_of,
        branch_id=selected_branch_id,
    )


@router.post("/write-offs/loans", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def write_off_loan_receivable(
    payload: LoanWriteOffCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    entry = post_loan_write_off(
        db,
        company_id=selected_company_id,
        loan_id=payload.loan_id,
        write_off_date=payload.write_off_date,
        description=payload.description,
        user_id=context.user.id,
    )
    db.commit()
    return entry_query(db, entry.scope_key).filter(JournalEntry.id == entry.id).first()


@router.get("/period-close-pack")
def accounting_period_close_pack(
    from_date: date = Query(...),
    to_date: date = Query(...),
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    return period_close_pack(
        db,
        company_id=selected_company_id,
        period_start=from_date,
        period_end=to_date,
        branch_id=selected_branch_id,
    )


@router.post("/assets/depreciate-period")
def depreciate_assets_for_period(
    payload: FixedAssetDepreciationRun,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    result = depreciate_all_fixed_assets_for_period(
        db,
        company_id=selected_company_id,
        period_start=payload.period_start,
        period_end=payload.period_end,
        branch_id=selected_branch_id,
        user_id=context.user.id,
    )
    db.commit()
    return result


@router.post("/adjustments/{entry_id}/reverse", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def reverse_adjustment_next_period(
    entry_id: UUID,
    payload: PeriodAdjustmentReversalCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    entry = reverse_period_adjustment(
        db,
        company_id=selected_company_id,
        journal_entry_id=entry_id,
        reversal_date=payload.reversal_date,
        description=payload.description,
        user_id=context.user.id,
    )
    db.commit()
    return entry_query(db, entry.scope_key).filter(JournalEntry.id == entry.id).first()


@router.get("/statement-of-changes-in-equity")
def statement_of_changes_in_equity(
    company_id: UUID | None = None,
    from_date: date = Query(...),
    to_date: date = Query(...),
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    key, _ = scope_key(selected_company_id)
    ensure_chart(db, company_id=selected_company_id)
    db.flush()

    opening_lines = trial_balance_data(db, key, None, from_date.fromordinal(from_date.toordinal() - 1), selected_branch_id)
    period_lines = trial_balance_data(db, key, from_date, to_date, selected_branch_id)

    def presented(line):
        return -line.balance if line.account_type in {"liability", "equity", "revenue"} else line.balance

    opening_equity = sum((presented(line) for line in opening_lines if line.account_type == "equity"), Decimal("0"))
    opening_profit = (
        sum((presented(line) for line in opening_lines if line.account_type == "revenue"), Decimal("0"))
        - sum((presented(line) for line in opening_lines if line.account_type == "expense"), Decimal("0"))
    )
    period_profit = (
        sum((presented(line) for line in period_lines if line.account_type == "revenue"), Decimal("0"))
        - sum((presented(line) for line in period_lines if line.account_type == "expense"), Decimal("0"))
    )

    by_code = {line.code: presented(line) for line in period_lines}
    owner_capital_movement = by_code.get("3000", Decimal("0"))
    retained_earnings_movement = by_code.get("3100", Decimal("0"))
    distributions = -by_code.get("3200", Decimal("0"))
    opening_total_equity = opening_equity + opening_profit
    closing_total_equity = opening_total_equity + owner_capital_movement + retained_earnings_movement + period_profit - distributions

    return {
        "from_date": from_date,
        "to_date": to_date,
        "branch_id": str(selected_branch_id) if selected_branch_id else None,
        "opening_equity": opening_total_equity,
        "owner_capital_movement": owner_capital_movement,
        "retained_earnings_adjustments": retained_earnings_movement,
        "profit_or_loss_for_period": period_profit,
        "drawings_and_distributions": distributions,
        "closing_equity": closing_total_equity,
    }


@router.get("/controls/transaction-coverage")
def accounting_transaction_coverage(
    from_date: date = Query(...),
    to_date: date = Query(...),
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    return transaction_accounting_coverage(
        db,
        company_id=selected_company_id,
        from_date=from_date,
        to_date=to_date,
        branch_id=selected_branch_id,
    )


@router.post("/recoveries/written-off-loans", response_model=JournalEntryRead, status_code=status.HTTP_201_CREATED)
def recover_written_off_loan(
    payload: WrittenOffLoanRecoveryCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    entry = record_written_off_loan_recovery(
        db,
        company_id=selected_company_id,
        loan_id=payload.loan_id,
        amount=payload.amount,
        recovery_date=payload.recovery_date,
        payment_method=payload.payment_method,
        proof_reference=payload.proof_reference,
        description=payload.description,
        user_id=context.user.id,
    )
    db.commit()
    return entry_query(db, entry.scope_key).filter(JournalEntry.id == entry.id).first()


@router.get("/controls/electronic-clearing")
def electronic_clearing_control(
    as_of: date = Query(...),
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    return electronic_clearing_reconciliation(
        db,
        company_id=selected_company_id,
        as_of=as_of,
        branch_id=selected_branch_id,
    )


@router.post("/controls/electronic-clearing/settlements", status_code=status.HTTP_201_CREATED)
def post_electronic_clearing_settlement(
    payload: ElectronicClearingSettlementCreate,
    company_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_write(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, payload.branch_id)
    result = record_electronic_clearing_settlement(
        db,
        company_id=selected_company_id,
        branch_id=selected_branch_id,
        settlement_date=payload.settlement_date,
        amount=payload.amount,
        direction=payload.direction,
        provider_reference=payload.provider_reference,
        proof_reference=payload.proof_reference,
        notes=payload.notes,
        user_id=context.user.id,
    )
    db.commit()
    return result


@router.get("/controls/electronic-clearing/aging")
def electronic_clearing_aging_control(
    as_of: date = Query(...),
    stale_after_days: int = Query(default=5, ge=0, le=365),
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    return electronic_clearing_aging(
        db,
        company_id=selected_company_id,
        as_of=as_of,
        branch_id=selected_branch_id,
        stale_after_days=stale_after_days,
    )


@router.get("/controls/bank-settlement-chain")
def bank_settlement_chain_control(
    from_date: date = Query(...),
    to_date: date = Query(...),
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    require_read(context)
    selected_company_id = resolve_scope(context, company_id)
    if not selected_company_id:
        raise HTTPException(status_code=422, detail="Select a company")
    selected_branch_id = resolve_branch_scope(db, context, selected_company_id, branch_id)
    return bank_settlement_chain(
        db,
        company_id=selected_company_id,
        from_date=from_date,
        to_date=to_date,
        branch_id=selected_branch_id,
    )
