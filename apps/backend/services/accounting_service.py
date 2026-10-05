from __future__ import annotations

"""LoanHub financial-accounting engine.

This module is intentionally built around the accounting flow taught in
Frank Wood's Business Accounting, 15th edition:

    source transaction -> books/journal -> ledger -> trial balance
    -> adjustments -> financial statements -> analysis

Operational modules do not invent their own accounting.  They call the
posting functions here, and every posting is double-entry, idempotent and
scoped to either a tenant company or the LoanHub platform.
"""

import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from database.models.accounting import AccountingAccount, JournalEntry, JournalLine
from database.models.enums import (
    PaymentDirection,
    PaymentPurpose,
    PaymentStatus,
    TreasuryDirection,
    TreasuryEntryApprovalStatus,
    TreasuryEntryType,
)
from database.models.payment import PaymentTransaction
from database.models.repayment import PaymentAllocation, RepaymentInstallment
from database.models.treasury import TreasurySettings


MONEY = Decimal("0.01")

# A lending-specific chart mapped to the five conventional financial-statement
# classes.  Control/adjustment accounts make the ledger useful beyond a simple
# cashbook and support receivables, payables, accruals, prepayments, depreciation,
# doubtful debts, suspense and VAT.
COMPANY_CHART = [
    ("1000", "Cash on Hand", "asset", "debit"),
    ("1010", "Bank", "asset", "debit"),
    ("1100", "Loans Receivable - Principal", "asset", "debit"),
    ("1110", "Interest Receivable", "asset", "debit"),
    ("1120", "Fees Receivable", "asset", "debit"),
    ("1200", "Trade Receivables", "asset", "debit"),
    ("1210", "Allowance for Doubtful Debts", "asset", "credit"),
    ("1300", "Inventory and Consumables", "asset", "debit"),
    ("1400", "Prepayments", "asset", "debit"),
    ("1500", "Property and Equipment", "asset", "debit"),
    ("1510", "Accumulated Depreciation", "asset", "credit"),
    ("1600", "VAT Receivable", "asset", "debit"),
    ("2000", "Trade Payables", "liability", "credit"),
    ("2100", "Accrued Expenses", "liability", "credit"),
    ("2200", "VAT Payable", "liability", "credit"),
    ("2300", "Customer Credits and Refunds Payable", "liability", "credit"),
    ("2400", "LoanHub and Provider Payables", "liability", "credit"),
    ("2990", "Suspense Account", "liability", "credit"),
    ("3000", "Owner Capital", "equity", "credit"),
    ("3100", "Retained Earnings / Opening Balance", "equity", "credit"),
    ("3200", "Drawings and Distributions", "equity", "debit"),
    ("4000", "Interest Income", "revenue", "credit"),
    ("4100", "Loan Fee Income", "revenue", "credit"),
    ("4200", "Penalty and Collection Income", "revenue", "credit"),
    ("4900", "Other Operating Income", "revenue", "credit"),
    ("5000", "Cost of Services", "expense", "debit"),
    ("5100", "Staff Costs", "expense", "debit"),
    ("5200", "Premises and Utilities", "expense", "debit"),
    ("5300", "Administration Expense", "expense", "debit"),
    ("5400", "Depreciation Expense", "expense", "debit"),
    ("5500", "Bad Debt Expense", "expense", "debit"),
    ("5600", "Bank and Payment Charges", "expense", "debit"),
    ("6100", "LoanHub Subscription Expense", "expense", "debit"),
    ("6200", "Marketplace Access Expense", "expense", "debit"),
    ("6300", "Refund and Adjustment Expense", "expense", "debit"),
    ("6400", "Assisted Borrower Account Opening Expense", "expense", "debit"),
    ("6500", "Other Operating Expenses", "expense", "debit"),
    ("6600", "Platform Fees and Charges", "expense", "debit"),
    ("6700", "Credit Bureau Expense", "expense", "debit"),
    ("6800", "CDAS Service Expense", "expense", "debit"),
]

PLATFORM_CHART = [
    ("1000", "Cash on Hand", "asset", "debit"),
    ("1010", "Bank", "asset", "debit"),
    ("1200", "Tenant Receivables", "asset", "debit"),
    ("1400", "Prepayments", "asset", "debit"),
    ("1500", "Property and Equipment", "asset", "debit"),
    ("1510", "Accumulated Depreciation", "asset", "credit"),
    ("2000", "Tenant Settlement Payable", "liability", "credit"),
    ("2100", "Accrued Expenses", "liability", "credit"),
    ("2990", "Suspense Account", "liability", "credit"),
    ("3000", "Platform Equity", "equity", "credit"),
    ("3100", "Retained Earnings / Opening Balance", "equity", "credit"),
    ("4000", "Subscription Revenue", "revenue", "credit"),
    ("4100", "Marketplace Unlock Revenue", "revenue", "credit"),
    ("4200", "Transaction Fee Revenue", "revenue", "credit"),
    ("4300", "Borrower Service Fee Revenue", "revenue", "credit"),
    ("4400", "Assisted Borrower Account Opening Revenue", "revenue", "credit"),
    ("4500", "Credit Bureau Revenue", "revenue", "credit"),
    ("4600", "CDAS Service Revenue", "revenue", "credit"),
    ("4900", "Other Operating Income", "revenue", "credit"),
    ("5000", "Cost of Services", "expense", "debit"),
    ("5100", "Refund and Reversal Expense", "expense", "debit"),
    ("5200", "Staff Costs", "expense", "debit"),
    ("5300", "Administration Expense", "expense", "debit"),
    ("5400", "Depreciation Expense", "expense", "debit"),
    ("5600", "Bank and Payment Charges", "expense", "debit"),
]


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def scope_key(company_id=None) -> tuple[str, str]:
    return (f"company:{company_id}", "company") if company_id else ("platform", "platform")


def accounting_business_date(db: Session, company_id, moment: datetime | None = None) -> date:
    stamp = moment or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    if not company_id:
        return stamp.date()
    settings = db.query(TreasurySettings).filter(TreasurySettings.company_id == company_id).first()
    timezone_name = settings.timezone if settings and settings.timezone else "Africa/Maseru"
    try:
        return stamp.astimezone(ZoneInfo(timezone_name)).date()
    except ZoneInfoNotFoundError:
        return stamp.date()


def accounting_payment_branch_id(db: Session, payment: PaymentTransaction):
    for obj_name in ("loan", "cash_transaction", "company_borrower_account"):
        obj = getattr(payment, obj_name, None)
        branch_id = getattr(obj, "branch_id", None) if obj is not None else None
        if branch_id:
            return branch_id
    if payment.company_id:
        settings = db.query(TreasurySettings).filter(TreasurySettings.company_id == payment.company_id).first()
        return settings.headquarters_branch_id if settings else None
    return None


def _chart_lock_id(scope: str) -> int:
    digest = hashlib.sha256(f"loanhub:accounting-chart:{scope}".encode()).digest()
    value = int.from_bytes(digest[:8], "big", signed=False)
    return value if value < (1 << 63) else value - (1 << 64)


def ensure_chart(db: Session, *, company_id=None) -> list[AccountingAccount]:
    key, scope_type = scope_key(company_id)
    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(_chart_lock_id(key))))

    existing = db.query(AccountingAccount).filter(AccountingAccount.scope_key == key).all()
    by_code = {row.code: row for row in existing}
    for code, name, account_type, normal_balance in (COMPANY_CHART if company_id else PLATFORM_CHART):
        account = by_code.get(code)
        if account:
            # Upgrade old system charts in place without changing user-created accounts.
            if account.is_system:
                account.name = name
                account.account_type = account_type
                account.normal_balance = normal_balance
                account.is_active = True
            continue
        db.add(AccountingAccount(
            scope_key=key,
            scope_type=scope_type,
            company_id=company_id,
            code=code,
            name=name,
            account_type=account_type,
            normal_balance=normal_balance,
            is_system=True,
            is_active=True,
        ))
    db.flush()
    return db.query(AccountingAccount).filter(
        AccountingAccount.scope_key == key
    ).order_by(AccountingAccount.code.asc()).all()


def account_by_code(db: Session, key: str, code: str) -> AccountingAccount:
    row = db.query(AccountingAccount).filter(
        AccountingAccount.scope_key == key,
        AccountingAccount.code == code,
        AccountingAccount.is_active.is_(True),
    ).first()
    if not row:
        raise HTTPException(status_code=409, detail=f"Accounting account {code} is unavailable")
    return row


def next_entry_number(db: Session, key: str) -> str:
    # Sequence generation remains deterministic inside the database transaction.
    period = date.today().strftime("%Y%m")
    count = db.query(func.count(JournalEntry.id)).filter(JournalEntry.scope_key == key).scalar() or 0
    prefix = "PLT" if key == "platform" else "JRN"
    return f"{prefix}-{period}-{count + 1:06d}"


def _journal_for_reference(db: Session, key: str, reference_type: str, reference_id: str) -> JournalEntry | None:
    return db.query(JournalEntry).filter(
        JournalEntry.scope_key == key,
        JournalEntry.reference_type == reference_type,
        JournalEntry.reference_id == reference_id,
    ).first()


def create_entry(
    db: Session,
    *,
    company_id=None,
    branch_id=None,
    created_by_user_id=None,
    entry_date: date,
    description: str,
    lines: list[dict],
    reference_type: str | None = None,
    reference_id: str | None = None,
    status_value: str = "draft",
    allow_closed_period: bool = False,
) -> JournalEntry:
    """Create a balanced journal entry.

    This is the only low-level posting primitive.  Each line must represent one
    side of double entry; no line may contain both a debit and a credit.
    """
    from services.governance_control_service import ensure_accounting_period_open

    if not allow_closed_period:
        ensure_accounting_period_open(db, company_id=company_id, entry_date=entry_date)

    key, scope_type = scope_key(company_id)
    ensure_chart(db, company_id=company_id)

    normalized = []
    for item in lines:
        debit = _money(item.get("debit"))
        credit = _money(item.get("credit"))
        if debit < 0 or credit < 0 or (debit > 0) == (credit > 0):
            raise HTTPException(status_code=422, detail="Each journal line must contain one positive debit or credit")
        normalized.append({**item, "debit": debit, "credit": credit})

    total_debit = sum((x["debit"] for x in normalized), Decimal("0.00"))
    total_credit = sum((x["credit"] for x in normalized), Decimal("0.00"))
    if total_debit <= 0 or total_debit != total_credit:
        raise HTTPException(status_code=422, detail="Journal entry debits and credits must be equal and greater than zero")

    account_ids = {x["account_id"] for x in normalized}
    accounts = db.query(AccountingAccount).filter(
        AccountingAccount.id.in_(account_ids),
        AccountingAccount.scope_key == key,
        AccountingAccount.is_active.is_(True),
    ).all()
    if len(accounts) != len(account_ids):
        raise HTTPException(status_code=422, detail="One or more journal accounts are outside the selected ledger")

    if reference_type and reference_id:
        existing = _journal_for_reference(db, key, reference_type, str(reference_id))
        if existing:
            return existing

    entry = JournalEntry(
        scope_key=key,
        scope_type=scope_type,
        company_id=company_id,
        branch_id=branch_id,
        created_by_user_id=created_by_user_id,
        posted_by_user_id=created_by_user_id if status_value == "posted" else None,
        entry_number=next_entry_number(db, key),
        entry_date=entry_date,
        description=description.strip(),
        reference_type=reference_type,
        reference_id=str(reference_id) if reference_id is not None else None,
        status=status_value,
        total_debit=total_debit,
        total_credit=total_credit,
        posted_at=datetime.now(timezone.utc) if status_value == "posted" else None,
    )
    db.add(entry)
    db.flush()
    for item in normalized:
        db.add(JournalLine(
            journal_entry_id=entry.id,
            account_id=item["account_id"],
            description=item.get("description"),
            debit=item["debit"],
            credit=item["credit"],
        ))
    db.flush()
    return entry


def post_codes(
    db: Session,
    *,
    company_id,
    branch_id,
    debit_code: str,
    credit_code: str,
    amount,
    description: str,
    reference_type: str,
    reference_id: str,
    user_id=None,
    entry_date: date | None = None,
    allow_closed_period: bool = False,
) -> JournalEntry:
    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    debit = account_by_code(db, key, debit_code)
    credit = account_by_code(db, key, credit_code)
    return create_entry(
        db,
        company_id=company_id,
        branch_id=branch_id,
        created_by_user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        status_value="posted",
        allow_closed_period=allow_closed_period,
        lines=[
            {"account_id": debit.id, "debit": _money(amount), "credit": 0},
            {"account_id": credit.id, "debit": 0, "credit": _money(amount)},
        ],
    )


def _loan_repayment_components(db: Session, payment: PaymentTransaction) -> tuple[Decimal, Decimal, Decimal]:
    settlement_id = (payment.provider_payload or {}).get("early_settlement_id")
    if settlement_id:
        from database.models.early_settlement import LoanEarlySettlement
        settlement = db.get(LoanEarlySettlement, UUID(str(settlement_id)))
        if settlement:
            return (
                _money(settlement.settlement_principal),
                _money(settlement.settlement_interest),
                _money(settlement.settlement_fees),
            )

    principal = interest = fees = Decimal("0.00")
    rows = db.query(PaymentAllocation, RepaymentInstallment).join(
        RepaymentInstallment, RepaymentInstallment.id == PaymentAllocation.installment_id
    ).filter(PaymentAllocation.payment_id == payment.id).all()
    for allocation, installment in rows:
        allocated = _money(allocation.amount)
        due = _money(installment.total_due)
        if due <= 0:
            principal += allocated
            continue
        principal += _money(allocated * _money(installment.principal_due) / due)
        interest += _money(allocated * _money(installment.interest_due) / due)
        fees += _money(allocated * _money(installment.fee_due) / due)

    difference = _money(payment.amount) - _money(principal + interest + fees)
    principal = _money(principal + difference)
    return _money(principal), _money(interest), _money(fees)


def _post_company_loan_repayment(db: Session, payment: PaymentTransaction) -> JournalEntry | None:
    key, _ = scope_key(payment.company_id)
    if _journal_for_reference(db, key, "payment_transaction", str(payment.id)):
        return _journal_for_reference(db, key, "payment_transaction", str(payment.id))

    ensure_chart(db, company_id=payment.company_id)
    cash = account_by_code(db, key, "1000")
    principal_receivable = account_by_code(db, key, "1100")
    interest_income = account_by_code(db, key, "4000")
    fee_income = account_by_code(db, key, "4100")
    principal, interest, fees = _loan_repayment_components(db, payment)

    lines = [{"account_id": cash.id, "debit": _money(payment.amount), "credit": 0}]
    if principal:
        lines.append({"account_id": principal_receivable.id, "debit": 0, "credit": principal})
    if interest:
        lines.append({"account_id": interest_income.id, "debit": 0, "credit": interest})
    if fees:
        lines.append({"account_id": fee_income.id, "debit": 0, "credit": fees})

    return create_entry(
        db,
        company_id=payment.company_id,
        branch_id=accounting_payment_branch_id(db, payment),
        created_by_user_id=payment.initiated_by_user_id,
        entry_date=accounting_business_date(db, payment.company_id, payment.completed_at or payment.created_at),
        description="Loan repayment: principal, interest and fees",
        reference_type="payment_transaction",
        reference_id=str(payment.id),
        status_value="posted",
        lines=lines,
    )


COMPANY_PAYMENT_RULES = {
    PaymentPurpose.LOAN_DISBURSEMENT: ("1100", "1000", "Loan principal advanced to borrower"),
    PaymentPurpose.SUBSCRIPTION: ("6100", "1000", "LoanHub subscription"),
    PaymentPurpose.MARKETPLACE_UNLOCK: ("6200", "1000", "Marketplace access"),
    PaymentPurpose.PLATFORM_FEE: ("6600", "1000", "LoanHub platform fee"),
    PaymentPurpose.PLATFORM_TRANSACTION_CHARGE: ("6600", "1000", "LoanHub transaction charge"),
    PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT: ("2400", "1000", "Settlement of LoanHub/provider payable"),
    PaymentPurpose.REFUND: ("6300", "1000", "Customer refund"),
    PaymentPurpose.BUSINESS_PAYMENT: ("6500", "1000", "Business operating payment"),
    PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE: ("6400", "1000", "Assisted borrower account opening fee"),
}

PLATFORM_PAYMENT_RULES = {
    PaymentPurpose.SUBSCRIPTION: ("1000", "4000", "Subscription revenue"),
    PaymentPurpose.MARKETPLACE_UNLOCK: ("1000", "4100", "Marketplace unlock revenue"),
    PaymentPurpose.PLATFORM_FEE: ("1000", "4200", "Platform fee revenue"),
    PaymentPurpose.PLATFORM_TRANSACTION_CHARGE: ("1000", "4200", "Transaction charge revenue"),
    PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT: ("1000", "1200", "Tenant receivable settlement"),
    PaymentPurpose.BORROW_REQUEST_FEE: ("1000", "4300", "Borrower request service fee"),
    PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE: ("1000", "4400", "Assisted borrower account opening revenue"),
    PaymentPurpose.REFUND: ("5100", "1000", "Platform refund"),
}


def record_payment_accounting(db: Session, payment: PaymentTransaction) -> None:
    """Apply financial accounting to every successful LoanHub payment.

    Unknown money movements are not silently ignored: they post to suspense,
    making the exception visible to finance staff while preserving balanced
    books and a complete audit trail.
    """
    if payment.status not in {PaymentStatus.SUCCEEDED, getattr(PaymentStatus, "PROCESSING", PaymentStatus.SUCCEEDED)}:
        return
    amount = _money(payment.amount)
    if amount <= 0:
        return

    when = accounting_business_date(db, payment.company_id, payment.completed_at or payment.created_at)
    backdated = bool((payment.provider_payload or {}).get("backdated_by_company_owner"))

    if payment.company_id:
        if payment.purpose == PaymentPurpose.LOAN_REPAYMENT:
            _post_company_loan_repayment(db, payment)
        else:
            debit_code, credit_code, description = COMPANY_PAYMENT_RULES.get(
                payment.purpose,
                ("2990", "1000", f"Unclassified outbound payment: {payment.purpose.value}")
                if payment.direction == PaymentDirection.OUTBOUND
                else ("1000", "2990", f"Unclassified inbound payment: {payment.purpose.value}"),
            )
            post_codes(
                db,
                company_id=payment.company_id,
                branch_id=accounting_payment_branch_id(db, payment),
                debit_code=debit_code,
                credit_code=credit_code,
                amount=amount,
                description=description,
                reference_type="payment_transaction",
                reference_id=str(payment.id),
                user_id=payment.initiated_by_user_id,
                entry_date=when,
                allow_closed_period=backdated,
            )

    rule = PLATFORM_PAYMENT_RULES.get(payment.purpose)
    if rule:
        post_codes(
            db,
            company_id=None,
            branch_id=None,
            debit_code=rule[0],
            credit_code=rule[1],
            amount=amount,
            description=rule[2],
            reference_type="payment_transaction",
            reference_id=str(payment.id),
            user_id=payment.initiated_by_user_id,
            entry_date=accounting_business_date(db, None, payment.completed_at or payment.created_at),
            allow_closed_period=backdated,
        )


COMPANY_PAYMENT_ACCOUNTING_PURPOSES = set(PaymentPurpose)


def company_payment_accounting_expected(payment: PaymentTransaction) -> bool:
    return bool(payment.company_id and payment.amount and _money(payment.amount) > 0)


def entry_query(db: Session, key: str):
    return db.query(JournalEntry).options(
        joinedload(JournalEntry.lines).joinedload(JournalLine.account)
    ).filter(JournalEntry.scope_key == key)


def reverse_reference_accounting(
    db: Session,
    *,
    company_id,
    branch_id,
    reference_type: str,
    reference_id: str,
    user_id,
    reason: str,
) -> JournalEntry | None:
    key, _ = scope_key(company_id)
    original = _journal_for_reference(db, key, reference_type, reference_id)
    if not original or original.status != "posted":
        return None
    reversal_ref = f"reversal:{reference_type}:{reference_id}"
    existing = _journal_for_reference(db, key, "accounting_reversal", reversal_ref)
    if existing:
        return existing
    return create_entry(
        db,
        company_id=company_id,
        branch_id=branch_id or original.branch_id,
        created_by_user_id=user_id,
        entry_date=accounting_business_date(db, company_id),
        description=f"Reversal: {reason}",
        reference_type="accounting_reversal",
        reference_id=reversal_ref,
        status_value="posted",
        lines=[
            {
                "account_id": line.account_id,
                "debit": line.credit,
                "credit": line.debit,
                "description": f"Reverse {original.entry_number}",
            }
            for line in original.lines
        ],
    )


def record_reversal_accounting(db: Session, payment: PaymentTransaction) -> JournalEntry | None:
    company_result = None
    if payment.company_id:
        company_result = reverse_reference_accounting(
            db,
            company_id=payment.company_id,
            branch_id=accounting_payment_branch_id(db, payment),
            reference_type="payment_transaction",
            reference_id=str(payment.id),
            user_id=payment.initiated_by_user_id,
            reason=f"payment {payment.id}",
        )
    # A platform journal may also exist for tenant/platform fees.
    platform_key, _ = scope_key(None)
    if _journal_for_reference(db, platform_key, "payment_transaction", str(payment.id)):
        reverse_reference_accounting(
            db,
            company_id=None,
            branch_id=None,
            reference_type="payment_transaction",
            reference_id=str(payment.id),
            user_id=payment.initiated_by_user_id,
            reason=f"payment {payment.id}",
        )
    return company_result


def record_treasury_entry_accounting(db: Session, treasury_entry) -> JournalEntry | None:
    if treasury_entry.payment_transaction_id or treasury_entry.is_voided:
        return None
    if treasury_entry.approval_status not in {
        TreasuryEntryApprovalStatus.POSTED,
        TreasuryEntryApprovalStatus.APPROVED,
    }:
        return None

    if treasury_entry.entry_type == TreasuryEntryType.BRANCH_FUNDING:
        return None  # internal transfer; no consolidated income/expense

    direction_in = treasury_entry.direction == TreasuryDirection.MONEY_IN
    if treasury_entry.entry_type == TreasuryEntryType.OWNER_CONTRIBUTION:
        rule = ("1000", "3000")
    elif treasury_entry.entry_type == TreasuryEntryType.EXPENSE:
        rule = ("6500", "1000")
    elif treasury_entry.entry_type == TreasuryEntryType.MANUAL_INCOME and direction_in:
        rule = ("1000", "4900")
    elif treasury_entry.entry_type == TreasuryEntryType.REFUND:
        rule = ("6300", "1000") if not direction_in else ("1000", "2300")
    elif direction_in:
        rule = ("1000", "2990")
    else:
        rule = ("2990", "1000")

    return post_codes(
        db,
        company_id=treasury_entry.company_id,
        branch_id=treasury_entry.branch_id,
        debit_code=rule[0],
        credit_code=rule[1],
        amount=treasury_entry.amount,
        description=f"Treasury: {treasury_entry.description}",
        reference_type="treasury_entry",
        reference_id=str(treasury_entry.id),
        user_id=treasury_entry.recorded_by_user_id,
        entry_date=accounting_business_date(db, treasury_entry.company_id, treasury_entry.occurred_at),
    )


def record_opening_source_accounting(db: Session, source) -> JournalEntry | None:
    from database.models.enums import OpeningSourceType

    if source.is_voided or not source.is_confirmed or source.source_type in {
        OpeningSourceType.PREVIOUS_CLOSING,
        OpeningSourceType.HEADQUARTERS_FUNDING,
    }:
        return None
    credit = "3000" if source.source_type == OpeningSourceType.OWNER_CONTRIBUTION else "3100"
    return post_codes(
        db,
        company_id=source.company_id,
        branch_id=source.branch_id,
        debit_code="1000",
        credit_code=credit,
        amount=source.amount,
        description=f"Opening source: {source.description}",
        reference_type="opening_source",
        reference_id=str(source.id),
        user_id=source.recorded_by_user_id,
        entry_date=source.daily_ledger.business_date,
    )


def post_expense(
    db: Session,
    *,
    company_id,
    branch_id,
    amount,
    expense_account_code: str,
    description: str,
    reference_id: str,
    user_id,
    paid_now: bool = True,
    entry_date: date | None = None,
) -> JournalEntry:
    """Native expense posting replacing the old standalone expense module.

    Paid expense: Dr Expense / Cr Cash.
    Accrued expense: Dr Expense / Cr Accrued Expenses.
    """
    code = expense_account_code or "6500"
    if not code.startswith(("5", "6")):
        raise HTTPException(status_code=422, detail="Expense postings must use an expense account")
    return post_codes(
        db,
        company_id=company_id,
        branch_id=branch_id,
        debit_code=code,
        credit_code="1000" if paid_now else "2100",
        amount=amount,
        description=description,
        reference_type="expense",
        reference_id=reference_id,
        user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
    )


def record_credit_bureau_invoice_accrual(db: Session, invoice) -> None:
    amount = _money(invoice.amount_due)
    if amount <= 0:
        return
    post_codes(db, company_id=invoice.company_id, branch_id=None, debit_code="6700", credit_code="2400",
               amount=amount, description=f"Credit Bureau invoice {invoice.invoice_number}",
               reference_type="credit_bureau_invoice", reference_id=str(invoice.id),
               entry_date=invoice.issued_at.date())
    post_codes(db, company_id=None, branch_id=None, debit_code="1200", credit_code="4500",
               amount=amount, description=f"Credit Bureau revenue {invoice.invoice_number}",
               reference_type="credit_bureau_invoice", reference_id=str(invoice.id),
               entry_date=invoice.issued_at.date())


def record_credit_bureau_invoice_payment(db: Session, invoice) -> None:
    amount = _money(invoice.amount_due)
    if amount <= 0:
        return
    when = (invoice.paid_at or datetime.now(timezone.utc)).date()
    post_codes(db, company_id=invoice.company_id, branch_id=None, debit_code="2400", credit_code="1000",
               amount=amount, description=f"Credit Bureau invoice payment {invoice.invoice_number}",
               reference_type="credit_bureau_invoice_payment", reference_id=str(invoice.id), entry_date=when)
    post_codes(db, company_id=None, branch_id=None, debit_code="1000", credit_code="1200",
               amount=amount, description=f"Credit Bureau invoice receipt {invoice.invoice_number}",
               reference_type="credit_bureau_invoice_payment", reference_id=str(invoice.id), entry_date=when)


def record_cdas_invoice_accrual(db: Session, invoice) -> None:
    amount = _money(invoice.amount_due)
    if amount <= 0:
        return
    post_codes(db, company_id=invoice.company_id, branch_id=None, debit_code="6800", credit_code="2400",
               amount=amount, description=f"CDAS invoice {invoice.invoice_number}",
               reference_type="cdas_invoice", reference_id=str(invoice.id), entry_date=invoice.issued_at.date())
    post_codes(db, company_id=None, branch_id=None, debit_code="1200", credit_code="4600",
               amount=amount, description=f"CDAS revenue {invoice.invoice_number}",
               reference_type="cdas_invoice", reference_id=str(invoice.id), entry_date=invoice.issued_at.date())


def record_cdas_invoice_payment(db: Session, invoice) -> None:
    amount = _money(invoice.amount_due)
    if amount <= 0:
        return
    when = (invoice.paid_at or datetime.now(timezone.utc)).date()
    post_codes(db, company_id=invoice.company_id, branch_id=None, debit_code="2400", credit_code="1000",
               amount=amount, description=f"CDAS invoice payment {invoice.invoice_number}",
               reference_type="cdas_invoice_payment", reference_id=str(invoice.id), entry_date=when)
    post_codes(db, company_id=None, branch_id=None, debit_code="1000", credit_code="1200",
               amount=amount, description=f"CDAS invoice receipt {invoice.invoice_number}",
               reference_type="cdas_invoice_payment", reference_id=str(invoice.id), entry_date=when)


def record_cdas_transaction_refund(db: Session, transaction) -> None:
    amount = _money(transaction.amount)
    if amount <= 0:
        return
    when = (transaction.refunded_at or datetime.now(timezone.utc)).date()
    post_codes(db, company_id=transaction.company_id, branch_id=None, debit_code="1000", credit_code="6800",
               amount=amount, description=f"CDAS transaction refund {transaction.transaction_reference}",
               reference_type="cdas_transaction_refund", reference_id=str(transaction.id), entry_date=when)
    post_codes(db, company_id=None, branch_id=None, debit_code="4600", credit_code="1000",
               amount=amount, description=f"CDAS revenue reversal {transaction.transaction_reference}",
               reference_type="cdas_transaction_refund", reference_id=str(transaction.id), entry_date=when)


def ledger_rows(db: Session, key: str, account_id, *, from_date=None, to_date=None, branch_id=None):
    query = db.query(JournalLine, JournalEntry).join(
        JournalEntry, JournalEntry.id == JournalLine.journal_entry_id
    ).filter(
        JournalLine.account_id == account_id,
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
    )
    if from_date:
        query = query.filter(JournalEntry.entry_date >= from_date)
    if to_date:
        query = query.filter(JournalEntry.entry_date <= to_date)
    if branch_id:
        query = query.filter(JournalEntry.branch_id == branch_id)
    return query.order_by(JournalEntry.entry_date.asc(), JournalEntry.created_at.asc()).all()


def post_depreciation_adjustment(
    db: Session, *, company_id, branch_id, amount, description: str,
    reference_id: str, user_id, entry_date: date | None = None,
) -> JournalEntry:
    """Chapter 21 treatment: Dr depreciation expense / Cr accumulated depreciation."""
    return post_codes(
        db, company_id=company_id, branch_id=branch_id,
        debit_code="5400", credit_code="1510", amount=amount,
        description=description, reference_type="depreciation_adjustment",
        reference_id=reference_id, user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
    )


def post_accrual_adjustment(
    db: Session, *, company_id, branch_id, amount, expense_account_code: str,
    description: str, reference_id: str, user_id, entry_date: date | None = None,
) -> JournalEntry:
    """Chapter 22 treatment: Dr expense / Cr accrued expenses."""
    if not expense_account_code.startswith(("5", "6")):
        raise HTTPException(status_code=422, detail="Accruals must debit an expense account")
    return post_codes(
        db, company_id=company_id, branch_id=branch_id,
        debit_code=expense_account_code, credit_code="2100", amount=amount,
        description=description, reference_type="accrual_adjustment",
        reference_id=reference_id, user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
    )


def post_prepayment_adjustment(
    db: Session, *, company_id, branch_id, amount, expense_account_code: str,
    description: str, reference_id: str, user_id, entry_date: date | None = None,
) -> JournalEntry:
    """Chapter 22 treatment: Dr prepayments / Cr expense."""
    if not expense_account_code.startswith(("5", "6")):
        raise HTTPException(status_code=422, detail="Prepayments must credit an expense account")
    return post_codes(
        db, company_id=company_id, branch_id=branch_id,
        debit_code="1400", credit_code=expense_account_code, amount=amount,
        description=description, reference_type="prepayment_adjustment",
        reference_id=reference_id, user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
    )


def post_doubtful_debt_allowance(
    db: Session, *, company_id, branch_id, amount, direction: str,
    description: str, reference_id: str, user_id, entry_date: date | None = None,
) -> JournalEntry:
    """Chapter 19 allowance movement.

    Increase: Dr bad debt expense / Cr allowance.
    Decrease: Dr allowance / Cr bad debt expense.
    """
    if direction not in {"increase", "decrease"}:
        raise HTTPException(status_code=422, detail="Allowance direction must be increase or decrease")
    debit_code, credit_code = ("5500", "1210") if direction == "increase" else ("1210", "5500")
    return post_codes(
        db, company_id=company_id, branch_id=branch_id,
        debit_code=debit_code, credit_code=credit_code, amount=amount,
        description=description, reference_type="doubtful_debt_allowance",
        reference_id=reference_id, user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
    )


def cash_flow_statement(
    db: Session, *, company_id, from_date: date, to_date: date, branch_id=None,
) -> dict:
    """Summarise posted cash/bank movements into the book's three IAS 7 sections.

    LoanHub's policy layer classifies fixed-asset movements as investing,
    owner/equity funding as financing, and the remaining cash movements as
    operating. This keeps the accounting textbook's three-section structure
    while making classification explicit in code.
    """
    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    cash_ids = {
        account_by_code(db, key, "1000").id,
        account_by_code(db, key, "1010").id,
    }
    rows = db.query(JournalEntry).options(
        joinedload(JournalEntry.lines).joinedload(JournalLine.account)
    ).filter(
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date >= from_date,
        JournalEntry.entry_date <= to_date,
    )
    if branch_id:
        rows = rows.filter(JournalEntry.branch_id == branch_id)

    sections = {"operating": Decimal("0.00"), "investing": Decimal("0.00"), "financing": Decimal("0.00")}
    details = []
    for entry in rows.order_by(JournalEntry.entry_date.asc()).all():
        cash_movement = Decimal("0.00")
        counterpart_codes = set()
        for line in entry.lines:
            if line.account_id in cash_ids:
                cash_movement += _money(line.debit) - _money(line.credit)
            elif line.account is not None:
                counterpart_codes.add(line.account.code)
        if not cash_movement:
            continue
        if counterpart_codes & {"1500", "1510"}:
            section = "investing"
        elif counterpart_codes & {"3000", "3100", "3200"}:
            section = "financing"
        else:
            section = "operating"
        sections[section] += cash_movement
        details.append({
            "entry_id": str(entry.id),
            "entry_number": entry.entry_number,
            "entry_date": entry.entry_date.isoformat(),
            "description": entry.description,
            "section": section,
            "amount": float(cash_movement),
        })

    net_change = sum(sections.values(), Decimal("0.00"))
    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "operating_activities": float(sections["operating"]),
        "investing_activities": float(sections["investing"]),
        "financing_activities": float(sections["financing"]),
        "net_change_in_cash": float(net_change),
        "details": details,
    }
