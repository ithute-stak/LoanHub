from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from database.models.accounting import AccountingAccount, JournalEntry, JournalLine
from database.models.enums import PaymentPurpose
from database.models.payment import PaymentTransaction
from database.models.treasury import TreasurySettings
from database.models.repayment import PaymentAllocation, RepaymentInstallment


COMPANY_CHART = [
    ("1000", "Cash on Hand", "asset", "debit"),
    ("1100", "Loans Receivable", "asset", "debit"),
    ("1200", "Accrued Interest Receivable", "asset", "debit"),
    ("2000", "Customer and Supplier Payables", "liability", "credit"),
    ("3000", "Owner Equity", "equity", "credit"),
    ("4000", "Interest Income", "revenue", "credit"),
    ("4100", "Processing Fee Income", "revenue", "credit"),
    ("4900", "Other Operating Income", "revenue", "credit"),
    ("5000", "Cash Handling Expense", "expense", "debit"),
    ("6100", "LoanHub Subscription Expense", "expense", "debit"),
    ("6200", "Marketplace Access Expense", "expense", "debit"),
    ("6300", "Refund and Adjustment Expense", "expense", "debit"),
    ("6400", "Assisted Borrower Account Opening Expense", "expense", "debit"),
    ("6500", "Operating Expenses", "expense", "debit"),
    ("6600", "Platform Fees and Charges", "expense", "debit"),
    ("3100", "Opening Balance and Retained Funds", "equity", "credit"),
]

PLATFORM_CHART = [
    ("1000", "Cash on Hand", "asset", "debit"),
    ("2000", "Tenant Settlement Payable", "liability", "credit"),
    ("3000", "Platform Equity", "equity", "credit"),
    ("4000", "Subscription Revenue", "revenue", "credit"),
    ("4100", "Marketplace Unlock Revenue", "revenue", "credit"),
    ("4200", "Transaction Fee Revenue", "revenue", "credit"),
    ("4300", "Borrower Service Fee Revenue", "revenue", "credit"),
    ("4400", "Assisted Borrower Account Opening Revenue", "revenue", "credit"),
    ("5000", "Cash Handling Expense", "expense", "debit"),
    ("5100", "Refund and Reversal Expense", "expense", "debit"),
]


def scope_key(company_id=None) -> tuple[str, str]:
    if company_id:
        return f"company:{company_id}", "company"
    return "platform", "platform"


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
    """Use the same operational branch fallback as treasury without a circular import."""
    if getattr(payment, "loan", None) is not None and getattr(payment.loan, "branch_id", None):
        return payment.loan.branch_id
    if getattr(payment, "cash_transaction", None) is not None and getattr(payment.cash_transaction, "branch_id", None):
        return payment.cash_transaction.branch_id
    if getattr(payment, "company_borrower_account", None) is not None and getattr(payment.company_borrower_account, "branch_id", None):
        return payment.company_borrower_account.branch_id
    if payment.company_id:
        settings = db.query(TreasurySettings).filter(TreasurySettings.company_id == payment.company_id).first()
        return settings.headquarters_branch_id if settings else None
    return None


def _chart_lock_id(scope: str) -> int:
    """Return a stable signed 64-bit PostgreSQL advisory-lock key."""
    digest = hashlib.sha256(f"loanhub:accounting-chart:{scope}".encode()).digest()
    value = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return value if value < (1 << 63) else value - (1 << 64)


def ensure_chart(db: Session, *, company_id=None) -> list[AccountingAccount]:
    """Create any missing system accounts exactly once for a ledger scope.

    Accounting pages may mount twice in React development mode and multiple API
    workers can receive the same bootstrap request concurrently.  The
    transaction-scoped advisory lock serialises chart creation for PostgreSQL,
    while the unique constraint remains the final database safeguard.
    """
    key, scope_type = scope_key(company_id)

    bind = db.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        db.execute(select(func.pg_advisory_xact_lock(_chart_lock_id(key))))

    existing = (
        db.query(AccountingAccount)
        .filter(AccountingAccount.scope_key == key)
        .order_by(AccountingAccount.code.asc())
        .all()
    )
    existing_codes = {account.code for account in existing}

    rows = COMPANY_CHART if company_id else PLATFORM_CHART
    for code, name, account_type, normal_balance in rows:
        if code in existing_codes:
            continue

        db.add(
            AccountingAccount(
                scope_key=key,
                scope_type=scope_type,
                company_id=company_id,
                code=code,
                name=name,
                account_type=account_type,
                normal_balance=normal_balance,
                is_system=True,
                is_active=True,
            )
        )

    db.flush()

    return (
        db.query(AccountingAccount)
        .filter(AccountingAccount.scope_key == key)
        .order_by(AccountingAccount.code.asc())
        .all()
    )


def account_by_code(db: Session, key: str, code: str) -> AccountingAccount:
    account = db.query(AccountingAccount).filter(
        AccountingAccount.scope_key == key,
        AccountingAccount.code == code,
        AccountingAccount.is_active.is_(True),
    ).first()
    if not account:
        raise HTTPException(status_code=409, detail=f"Accounting account {code} is unavailable")
    return account


def next_entry_number(db: Session, key: str) -> str:
    today = date.today().strftime("%Y%m")
    count = db.query(func.count(JournalEntry.id)).filter(JournalEntry.scope_key == key).scalar() or 0
    prefix = "PLT" if key == "platform" else "JRN"
    return f"{prefix}-{today}-{count + 1:06d}"


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
    from services.governance_control_service import ensure_accounting_period_open

    if not allow_closed_period:
        ensure_accounting_period_open(db, company_id=company_id, entry_date=entry_date)
    key, scope_type = scope_key(company_id)
    ensure_chart(db, company_id=company_id)

    total_debit = sum((Decimal(str(item.get("debit", 0))) for item in lines), Decimal("0"))
    total_credit = sum((Decimal(str(item.get("credit", 0))) for item in lines), Decimal("0"))
    if total_debit <= 0 or total_debit != total_credit:
        raise HTTPException(status_code=400, detail="Journal entry debits and credits must balance")

    account_ids = {item["account_id"] for item in lines}
    accounts = db.query(AccountingAccount).filter(
        AccountingAccount.id.in_(account_ids),
        AccountingAccount.scope_key == key,
        AccountingAccount.is_active.is_(True),
    ).all()
    if len(accounts) != len(account_ids):
        raise HTTPException(status_code=400, detail="One or more accounts are outside the selected ledger")

    entry = JournalEntry(
        scope_key=key,
        scope_type=scope_type,
        company_id=company_id,
        branch_id=branch_id,
        created_by_user_id=created_by_user_id,
        entry_number=next_entry_number(db, key),
        entry_date=entry_date,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        status=status_value,
        total_debit=total_debit,
        total_credit=total_credit,
    )
    if status_value == "posted":
        entry.posted_at = datetime.now(timezone.utc)
        entry.posted_by_user_id = created_by_user_id
    db.add(entry)
    db.flush()

    for item in lines:
        db.add(JournalLine(
            journal_entry_id=entry.id,
            account_id=item["account_id"],
            description=item.get("description"),
            debit=Decimal(str(item.get("debit", 0))),
            credit=Decimal(str(item.get("credit", 0))),
        ))
    db.flush()
    return entry


def _post_source_entry(
    db: Session,
    *,
    company_id,
    branch_id,
    source: PaymentTransaction,
    debit_code: str,
    credit_code: str,
    description: str,
) -> JournalEntry | None:
    key, _ = scope_key(company_id)
    existing = db.query(JournalEntry).filter(
        JournalEntry.scope_key == key,
        JournalEntry.reference_type == "payment_transaction",
        JournalEntry.reference_id == str(source.id),
    ).first()
    if existing:
        return existing

    ensure_chart(db, company_id=company_id)
    debit_account = account_by_code(db, key, debit_code)
    credit_account = account_by_code(db, key, credit_code)
    return create_entry(
        db,
        company_id=company_id,
        branch_id=branch_id,
        created_by_user_id=source.initiated_by_user_id,
        entry_date=accounting_business_date(db, company_id, source.completed_at or source.created_at),
        description=description,
        reference_type="payment_transaction",
        reference_id=str(source.id),
        status_value="posted",
        allow_closed_period=bool((source.provider_payload or {}).get("backdated_by_company_owner")),
        lines=[
            {"account_id": debit_account.id, "debit": source.amount, "credit": 0},
            {"account_id": credit_account.id, "debit": 0, "credit": source.amount},
        ],
    )




def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _loan_repayment_components(db: Session, payment: PaymentTransaction) -> tuple[Decimal, Decimal, Decimal]:
    """Return principal, interest and fee portions for a posted repayment."""
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
    principal = Decimal("0.00")
    interest = Decimal("0.00")
    fees = Decimal("0.00")
    rows = (
        db.query(PaymentAllocation, RepaymentInstallment)
        .join(RepaymentInstallment, RepaymentInstallment.id == PaymentAllocation.installment_id)
        .filter(PaymentAllocation.payment_id == payment.id)
        .all()
    )
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
    existing = _journal_for_reference(db, key, "payment_transaction", str(payment.id))
    if existing:
        return existing
    ensure_chart(db, company_id=payment.company_id)
    cash = account_by_code(db, key, "1000")
    receivable = account_by_code(db, key, "1100")
    interest_income = account_by_code(db, key, "4000")
    fee_income = account_by_code(db, key, "4100")
    principal, interest, fees = _loan_repayment_components(db, payment)
    lines = [{"account_id": cash.id, "debit": payment.amount, "credit": 0}]
    if principal:
        lines.append({"account_id": receivable.id, "debit": 0, "credit": principal})
    if interest:
        lines.append({"account_id": interest_income.id, "debit": 0, "credit": interest})
    if fees:
        lines.append({"account_id": fee_income.id, "debit": 0, "credit": fees})
    return create_entry(
        db,
        company_id=payment.company_id,
        branch_id=payment.loan.branch_id if payment.loan else None,
        created_by_user_id=payment.initiated_by_user_id,
        entry_date=accounting_business_date(db, payment.company_id, payment.completed_at or payment.created_at),
        description="Loan repayment received",
        reference_type="payment_transaction",
        reference_id=str(payment.id),
        status_value="posted",
        lines=lines,
    )

def record_payment_accounting(db: Session, payment: PaymentTransaction) -> None:
    if not payment.amount or payment.amount <= 0:
        return

    if payment.company_id:
        if payment.purpose == PaymentPurpose.LOAN_REPAYMENT:
            _post_company_loan_repayment(db, payment)
        company_map = {
            PaymentPurpose.LOAN_DISBURSEMENT: ("1100", "1000", "Loan disbursement"),
            PaymentPurpose.SUBSCRIPTION: ("6100", "1000", "LoanHub subscription payment"),
            PaymentPurpose.MARKETPLACE_UNLOCK: ("6200", "1000", "Marketplace request unlock"),
            PaymentPurpose.PLATFORM_FEE: ("6600", "1000", "LoanHub platform fee"),
            PaymentPurpose.PLATFORM_TRANSACTION_CHARGE: ("6600", "1000", "LoanHub transaction charge"),
            PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT: ("6600", "1000", "LoanHub platform claim settlement"),
            PaymentPurpose.REFUND: ("6300", "1000", "Customer refund"),
            PaymentPurpose.BUSINESS_PAYMENT: ("6500", "1000", "Business operating payment"),
            PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE: ("6400", "1000", "Assisted borrower account opening fee paid"),
        }
        mapping = company_map.get(payment.purpose)
        if mapping:
            _post_source_entry(
                db,
                company_id=payment.company_id,
                branch_id=accounting_payment_branch_id(db, payment),
                source=payment,
                debit_code=mapping[0],
                credit_code=mapping[1],
                description=mapping[2],
            )

    platform_map = {
        PaymentPurpose.SUBSCRIPTION: ("1000", "4000", "Subscription revenue received"),
        PaymentPurpose.MARKETPLACE_UNLOCK: ("1000", "4100", "Marketplace unlock revenue received"),
        PaymentPurpose.PLATFORM_FEE: ("1000", "4200", "Transaction fee revenue received"),
        PaymentPurpose.BORROW_REQUEST_FEE: ("1000", "4300", "Borrower request service fee received"),
        PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE: ("1000", "4400", "Assisted borrower account opening fee received"),
        PaymentPurpose.REFUND: ("5100", "1000", "Platform refund issued"),
    }
    platform_mapping = platform_map.get(payment.purpose)
    if platform_mapping:
        _post_source_entry(
            db,
            company_id=None,
            branch_id=None,
            source=payment,
            debit_code=platform_mapping[0],
            credit_code=platform_mapping[1],
            description=platform_mapping[2],
        )



COMPANY_PAYMENT_ACCOUNTING_PURPOSES = {
    PaymentPurpose.LOAN_REPAYMENT,
    PaymentPurpose.LOAN_DISBURSEMENT,
    PaymentPurpose.SUBSCRIPTION,
    PaymentPurpose.MARKETPLACE_UNLOCK,
    PaymentPurpose.PLATFORM_FEE,
    PaymentPurpose.PLATFORM_TRANSACTION_CHARGE,
    PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT,
    PaymentPurpose.REFUND,
    PaymentPurpose.BUSINESS_PAYMENT,
    PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE,
}


def company_payment_accounting_expected(payment: PaymentTransaction) -> bool:
    return bool(payment.company_id and payment.purpose in COMPANY_PAYMENT_ACCOUNTING_PURPOSES and payment.amount and payment.amount > 0)

def entry_query(db: Session, key: str):
    return db.query(JournalEntry).options(
        joinedload(JournalEntry.lines).joinedload(JournalLine.account)
    ).filter(JournalEntry.scope_key == key)


def record_reversal_accounting(db: Session, payment: PaymentTransaction) -> JournalEntry | None:
    """Post the exact compensating journal for a previously posted payment."""
    company_id = payment.company_id
    key, _ = scope_key(company_id)
    reference_id = f"reversal:{payment.id}"
    existing = db.query(JournalEntry).filter(
        JournalEntry.scope_key == key,
        JournalEntry.reference_type == "payment_reversal",
        JournalEntry.reference_id == reference_id,
    ).first()
    if existing:
        return existing

    # Prefer reversing the exact source journal. Loan repayments may contain
    # principal, interest and fee lines, so a generic two-line reversal would
    # overstate receivables and leave recognised income behind.
    original = _journal_for_reference(db, key, "payment_transaction", str(payment.id))
    if original and original.status == "posted":
        return create_entry(
            db,
            company_id=company_id,
            branch_id=original.branch_id,
            created_by_user_id=payment.initiated_by_user_id,
            entry_date=accounting_business_date(db, company_id),
            description=f"Reversal of {original.entry_number}: {original.description}",
            reference_type="payment_reversal",
            reference_id=reference_id,
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

    ensure_chart(db, company_id=company_id)
    if (
        company_id
        and payment.purpose == PaymentPurpose.LOAN_REPAYMENT
        and (payment.provider_payload or {}).get("early_settlement_id")
    ):
        principal, interest, fees = _loan_repayment_components(db, payment)
        receivable = account_by_code(db, key, "1100")
        interest_income = account_by_code(db, key, "4000")
        fee_income = account_by_code(db, key, "4100")
        cash = account_by_code(db, key, "1000")
        lines = [{"account_id": cash.id, "debit": 0, "credit": payment.amount}]
        if principal:
            lines.append({"account_id": receivable.id, "debit": principal, "credit": 0})
        if interest:
            lines.append({"account_id": interest_income.id, "debit": interest, "credit": 0})
        if fees:
            lines.append({"account_id": fee_income.id, "debit": fees, "credit": 0})
        return create_entry(
            db,
            company_id=company_id,
            branch_id=accounting_payment_branch_id(db, payment),
            created_by_user_id=payment.initiated_by_user_id,
            entry_date=accounting_business_date(db, company_id),
            description="Reversal of early loan settlement",
            reference_type="payment_reversal",
            reference_id=reference_id,
            status_value="posted",
            lines=lines,
        )
    if company_id:
        reversal_map = {
            PaymentPurpose.LOAN_REPAYMENT: ("1100", "1000", "Reversal of loan repayment"),
            PaymentPurpose.LOAN_DISBURSEMENT: ("1000", "1100", "Reversal of loan disbursement"),
            PaymentPurpose.SUBSCRIPTION: ("1000", "6100", "Reversal of LoanHub subscription payment"),
            PaymentPurpose.MARKETPLACE_UNLOCK: ("1000", "6200", "Reversal of marketplace request unlock"),
            PaymentPurpose.PLATFORM_FEE: ("1000", "6600", "Reversal of LoanHub platform fee"),
            PaymentPurpose.PLATFORM_TRANSACTION_CHARGE: ("1000", "6600", "Reversal of LoanHub transaction charge"),
            PaymentPurpose.PLATFORM_CLAIM_SETTLEMENT: ("1000", "6600", "Reversal of platform claim settlement"),
            PaymentPurpose.REFUND: ("1000", "6300", "Reversal of customer refund"),
            PaymentPurpose.BUSINESS_PAYMENT: ("1000", "6500", "Reversal of business operating payment"),
            PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE: ("1000", "6400", "Reversal of assisted borrower account fee"),
        }
        fallback = ("1000", "6300", f"Reversal of {payment.purpose.value.replace('_', ' ')}")
        branch_id = accounting_payment_branch_id(db, payment)
    else:
        reversal_map = {
            PaymentPurpose.SUBSCRIPTION: ("4000", "1000", "Reversal of subscription revenue"),
            PaymentPurpose.MARKETPLACE_UNLOCK: ("4100", "1000", "Reversal of marketplace unlock revenue"),
            PaymentPurpose.PLATFORM_FEE: ("4200", "1000", "Reversal of transaction fee revenue"),
            PaymentPurpose.BORROW_REQUEST_FEE: ("4300", "1000", "Reversal of borrower request service fee"),
            PaymentPurpose.ASSISTED_BORROWER_ACCOUNT_FEE: ("4400", "1000", "Reversal of assisted borrower account opening fee"),
            PaymentPurpose.REFUND: ("1000", "5100", "Reversal of platform refund"),
        }
        fallback = ("5100", "1000", f"Reversal of {payment.purpose.value.replace('_', ' ')}")
        branch_id = None

    debit_code, credit_code, description = reversal_map.get(payment.purpose, fallback)
    debit_account = account_by_code(db, key, debit_code)
    credit_account = account_by_code(db, key, credit_code)
    return create_entry(
        db,
        company_id=company_id,
        branch_id=branch_id,
        created_by_user_id=payment.initiated_by_user_id,
        entry_date=accounting_business_date(db, company_id),
        description=description,
        reference_type="payment_reversal",
        reference_id=reference_id,
        status_value="posted",
        lines=[
            {"account_id": debit_account.id, "debit": payment.amount, "credit": 0},
            {"account_id": credit_account.id, "debit": 0, "credit": payment.amount},
        ],
    )


def _journal_for_reference(db: Session, key: str, reference_type: str, reference_id: str) -> JournalEntry | None:
    return db.query(JournalEntry).filter(
        JournalEntry.scope_key == key,
        JournalEntry.reference_type == reference_type,
        JournalEntry.reference_id == reference_id,
    ).first()


def record_treasury_entry_accounting(db: Session, treasury_entry) -> JournalEntry | None:
    """Post one accounting journal for a posted manual treasury movement.

    Payment-backed loan movements already create journals through
    ``record_payment_accounting`` and are deliberately excluded here.
    """
    from database.models.enums import TreasuryDirection, TreasuryEntryApprovalStatus, TreasuryEntryType

    if treasury_entry.payment_transaction_id or treasury_entry.is_voided:
        return None
    if treasury_entry.approval_status not in {
        TreasuryEntryApprovalStatus.POSTED,
        TreasuryEntryApprovalStatus.APPROVED,
    }:
        return None
    key, _ = scope_key(treasury_entry.company_id)
    reference_id = str(treasury_entry.id)
    existing = _journal_for_reference(db, key, "treasury_entry", reference_id)
    if existing:
        return existing

    ensure_chart(db, company_id=treasury_entry.company_id)
    direction_in = treasury_entry.direction == TreasuryDirection.MONEY_IN
    if treasury_entry.entry_type == TreasuryEntryType.OWNER_CONTRIBUTION:
        debit_code, credit_code = "1000", "3000"
    elif treasury_entry.entry_type == TreasuryEntryType.EXPENSE:
        debit_code, credit_code = "6500", "1000"
    elif treasury_entry.entry_type == TreasuryEntryType.MANUAL_INCOME and direction_in:
        debit_code, credit_code = "1000", "4900"
    elif treasury_entry.entry_type == TreasuryEntryType.REFUND:
        debit_code, credit_code = ("6300", "1000") if not direction_in else ("1000", "6300")
    elif treasury_entry.entry_type == TreasuryEntryType.BRANCH_FUNDING:
        # Internal transfers are visible in the branch sub-ledger and treasury,
        # but do not create consolidated company income or expense.
        return None
    elif direction_in:
        debit_code, credit_code = "1000", "4900"
    else:
        debit_code, credit_code = "6300", "1000"

    debit_account = account_by_code(db, key, debit_code)
    credit_account = account_by_code(db, key, credit_code)
    return create_entry(
        db,
        company_id=treasury_entry.company_id,
        branch_id=treasury_entry.branch_id,
        created_by_user_id=treasury_entry.recorded_by_user_id,
        entry_date=accounting_business_date(db, treasury_entry.company_id, treasury_entry.occurred_at),
        description=f"Treasury: {treasury_entry.description}",
        reference_type="treasury_entry",
        reference_id=reference_id,
        status_value="posted",
        lines=[
            {"account_id": debit_account.id, "debit": treasury_entry.amount, "credit": 0},
            {"account_id": credit_account.id, "debit": 0, "credit": treasury_entry.amount},
        ],
    )


def record_opening_source_accounting(db: Session, source) -> JournalEntry | None:
    from database.models.enums import OpeningSourceType

    if source.is_voided or not source.is_confirmed or source.source_type in {
        OpeningSourceType.PREVIOUS_CLOSING,
        OpeningSourceType.HEADQUARTERS_FUNDING,
    }:
        return None
    key, _ = scope_key(source.company_id)
    reference_id = str(source.id)
    existing = _journal_for_reference(db, key, "opening_source", reference_id)
    if existing:
        return existing
    ensure_chart(db, company_id=source.company_id)
    credit_code = "3000" if source.source_type == OpeningSourceType.OWNER_CONTRIBUTION else "3100"
    debit_account = account_by_code(db, key, "1000")
    credit_account = account_by_code(db, key, credit_code)
    return create_entry(
        db,
        company_id=source.company_id,
        branch_id=source.branch_id,
        created_by_user_id=source.recorded_by_user_id,
        entry_date=source.daily_ledger.business_date,
        description=f"Opening source: {source.description}",
        reference_type="opening_source",
        reference_id=reference_id,
        status_value="posted",
        lines=[
            {"account_id": debit_account.id, "debit": source.amount, "credit": 0},
            {"account_id": credit_account.id, "debit": 0, "credit": source.amount},
        ],
    )


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
    reversal_reference = f"reversal:{reference_type}:{reference_id}"
    existing = _journal_for_reference(db, key, "treasury_reversal", reversal_reference)
    if existing:
        return existing
    return create_entry(
        db,
        company_id=company_id,
        branch_id=branch_id,
        created_by_user_id=user_id,
        entry_date=accounting_business_date(db, company_id),
        description=f"Reversal: {reason}",
        reference_type="treasury_reversal",
        reference_id=reversal_reference,
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
