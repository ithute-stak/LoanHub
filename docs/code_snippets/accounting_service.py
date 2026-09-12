from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from database.models.accounting import AccountingAccount, JournalEntry, JournalLine
from database.models.enums import PaymentPurpose
from database.models.payment import PaymentTransaction


COMPANY_CHART = [
    ("1000", "Mobile Money and Cash", "asset", "debit"),
    ("1100", "Loans Receivable", "asset", "debit"),
    ("1200", "Accrued Interest Receivable", "asset", "debit"),
    ("2000", "Customer and Supplier Payables", "liability", "credit"),
    ("3000", "Owner Equity", "equity", "credit"),
    ("4000", "Interest Income", "revenue", "credit"),
    ("4100", "Processing Fee Income", "revenue", "credit"),
    ("5000", "Payment Provider Fees", "expense", "debit"),
    ("6100", "LoanHub Subscription Expense", "expense", "debit"),
    ("6200", "Marketplace Access Expense", "expense", "debit"),
    ("6300", "Refund and Adjustment Expense", "expense", "debit"),
]

PLATFORM_CHART = [
    ("1000", "Mobile Money and Bank", "asset", "debit"),
    ("2000", "Tenant Settlement Payable", "liability", "credit"),
    ("3000", "Platform Equity", "equity", "credit"),
    ("4000", "Subscription Revenue", "revenue", "credit"),
    ("4100", "Marketplace Unlock Revenue", "revenue", "credit"),
    ("4200", "Transaction Fee Revenue", "revenue", "credit"),
    ("5000", "Payment Provider Expense", "expense", "debit"),
    ("5100", "Refund and Reversal Expense", "expense", "debit"),
]


def scope_key(company_id=None) -> tuple[str, str]:
    if company_id:
        return f"company:{company_id}", "company"
    return "platform", "platform"


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
) -> JournalEntry:
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
        entry_date=(source.completed_at or datetime.now(timezone.utc)).date(),
        description=description,
        reference_type="payment_transaction",
        reference_id=str(source.id),
        status_value="posted",
        lines=[
            {"account_id": debit_account.id, "debit": source.amount, "credit": 0},
            {"account_id": credit_account.id, "debit": 0, "credit": source.amount},
        ],
    )


def record_payment_accounting(db: Session, payment: PaymentTransaction) -> None:
    if not payment.amount or payment.amount <= 0:
        return

    if payment.company_id:
        company_map = {
            PaymentPurpose.LOAN_DISBURSEMENT: ("1100", "1000", "Loan disbursement"),
            PaymentPurpose.LOAN_REPAYMENT: ("1000", "1100", "Loan repayment received"),
            PaymentPurpose.SUBSCRIPTION: ("6100", "1000", "LoanHub subscription payment"),
            PaymentPurpose.MARKETPLACE_UNLOCK: ("6200", "1000", "Marketplace request unlock"),
            PaymentPurpose.PLATFORM_FEE: ("5000", "1000", "LoanHub transaction fee"),
            PaymentPurpose.REFUND: ("6300", "1000", "Customer refund"),
        }
        mapping = company_map.get(payment.purpose)
        if mapping:
            _post_source_entry(
                db,
                company_id=payment.company_id,
                branch_id=None,
                source=payment,
                debit_code=mapping[0],
                credit_code=mapping[1],
                description=mapping[2],
            )

    platform_map = {
        PaymentPurpose.SUBSCRIPTION: ("1000", "4000", "Subscription revenue received"),
        PaymentPurpose.MARKETPLACE_UNLOCK: ("1000", "4100", "Marketplace unlock revenue received"),
        PaymentPurpose.PLATFORM_FEE: ("1000", "4200", "Transaction fee revenue received"),
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


def entry_query(db: Session, key: str):
    return db.query(JournalEntry).options(
        joinedload(JournalEntry.lines).joinedload(JournalLine.account)
    ).filter(JournalEntry.scope_key == key)
