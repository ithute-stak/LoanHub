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
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from database.models.accounting import AccountingAccount, JournalEntry, JournalLine
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_operating_system import CompanyOperatingRecord
from database.models.lending_operations import CollectionCase
from database.models.credit_loss_provisioning import CreditLossProvisionRun
from database.models.governance_control import AccountingPeriod, ApprovalRequest, BankStatementLine
from database.models.reconciliation import ReconciliationBatch, ReconciliationLine
from database.models.enums import (
    PaymentDirection,
    PaymentMethod,
    PaymentPurpose,
    PaymentStatus,
    InstallmentStatus,
    TreasuryDirection,
    TreasuryEntryApprovalStatus,
    TreasuryEntryType,
)
from database.models.payment import PaymentTransaction
from database.models.repayment import PaymentAllocation, RepaymentInstallment
from database.models.treasury import TreasuryEntry, TreasurySettings


MONEY = Decimal("0.01")
ELECTRONIC_CLEARING_STALE_DAYS = 5
CASH_EQUIVALENT_CODES = {"1000", "1010"}


def settlement_account_code(payment_method) -> str:
    """Map a payment/treasury channel to the ledger account holding the funds."""
    value = str(getattr(payment_method, "value", payment_method) or "").strip().lower()
    if value == PaymentMethod.CASH.value:
        return "1000"
    if value == PaymentMethod.BANK.value:
        return "1010"
    if value in {"electronic", "gateway", "wallet"}:
        return "1020"
    return "1020"

# A lending-specific chart mapped to the five conventional financial-statement
# classes.  Control/adjustment accounts make the ledger useful beyond a simple
# cashbook and support receivables, payables, accruals, prepayments, depreciation,
# doubtful debts, suspense and VAT.
COMPANY_CHART = [
    ("1000", "Cash on Hand", "asset", "debit"),
    ("1010", "Bank", "asset", "debit"),
    ("1020", "Electronic Payment Clearing", "asset", "debit"),
    ("1100", "Loans Receivable - Principal", "asset", "debit"),
    ("1110", "Interest Receivable", "asset", "debit"),
    ("1120", "Fees Receivable", "asset", "debit"),
    ("1150", "Allowance for Credit Losses", "asset", "credit"),
    ("1200", "Trade Receivables", "asset", "debit"),
    ("1210", "Allowance for Doubtful Debts", "asset", "credit"),
    ("1220", "Accrued Income", "asset", "debit"),
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
    ("2500", "Loan Notes Payable", "liability", "credit"),
    ("2600", "Corporation Tax Payable", "liability", "credit"),
    ("2990", "Suspense Account", "liability", "credit"),
    ("3000", "Owner Capital", "equity", "credit"),
    ("3100", "Retained Earnings / Opening Balance", "equity", "credit"),
    ("3200", "Drawings and Distributions", "equity", "debit"),
    ("3300", "Ordinary Share Capital", "equity", "credit"),
    ("3310", "Share Premium", "equity", "credit"),
    ("3320", "Revaluation Reserve", "equity", "credit"),
    ("3330", "General Reserve", "equity", "credit"),
    ("4000", "Interest Income", "revenue", "credit"),
    ("4100", "Loan Fee Income", "revenue", "credit"),
    ("4200", "Penalty and Collection Income", "revenue", "credit"),
    ("4300", "Recoveries of Written-off Loans", "revenue", "credit"),
    ("4900", "Other Operating Income", "revenue", "credit"),
    ("4910", "Gain on Disposal of Property and Equipment", "revenue", "credit"),
    ("5000", "Cost of Services", "expense", "debit"),
    ("5100", "Staff Costs", "expense", "debit"),
    ("5200", "Premises and Utilities", "expense", "debit"),
    ("5300", "Administration Expense", "expense", "debit"),
    ("5400", "Depreciation Expense", "expense", "debit"),
    ("5500", "Bad Debt Expense", "expense", "debit"),
    ("5510", "Credit Loss Provision Expense", "expense", "debit"),
    ("5600", "Bank and Payment Charges", "expense", "debit"),
    ("6100", "LoanHub Subscription Expense", "expense", "debit"),
    ("6200", "Marketplace Access Expense", "expense", "debit"),
    ("6300", "Refund and Adjustment Expense", "expense", "debit"),
    ("6400", "Assisted Borrower Account Opening Expense", "expense", "debit"),
    ("6500", "Other Operating Expenses", "expense", "debit"),
    ("6510", "Loss on Disposal of Property and Equipment", "expense", "debit"),
    ("6600", "Platform Fees and Charges", "expense", "debit"),
    ("6700", "Credit Bureau Expense", "expense", "debit"),
    ("6800", "CDAS Service Expense", "expense", "debit"),
    ("6900", "Corporation Tax Expense", "expense", "debit"),
]

PLATFORM_CHART = [
    ("1000", "Cash on Hand", "asset", "debit"),
    ("1010", "Bank", "asset", "debit"),
    ("1020", "Electronic Payment Clearing", "asset", "debit"),
    ("1200", "Tenant Receivables", "asset", "debit"),
    ("1220", "Accrued Income", "asset", "debit"),
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

    # Historical LoanHub builds used 6700 for credit-loss provision expense.
    # Preserve those journal meanings when upgrading the chart: first reuse the
    # old system account as 5510 when possible, then move only legacy provision
    # journal lines if both accounts already exist. This is an idempotent chart
    # migration; debit/credit amounts and journal identities are unchanged.
    if company_id:
        legacy_6700 = by_code.get("6700")
        provision_5510 = by_code.get("5510")
        if (
            legacy_6700
            and legacy_6700.is_system
            and "credit loss" in str(legacy_6700.name or "").lower()
            and provision_5510 is None
        ):
            legacy_6700.code = "5510"
            legacy_6700.name = "Credit Loss Provision Expense"
            legacy_6700.account_type = "expense"
            legacy_6700.normal_balance = "debit"
            db.flush()
            by_code.pop("6700", None)
            by_code["5510"] = legacy_6700
            provision_5510 = legacy_6700

        if legacy_6700 and provision_5510 and legacy_6700.id != provision_5510.id:
            legacy_provision_journals = db.query(JournalEntry.id).filter(
                JournalEntry.scope_key == key,
                JournalEntry.reference_type == "credit_loss_provision_run",
            )
            db.query(JournalLine).filter(
                JournalLine.account_id == legacy_6700.id,
                JournalLine.journal_entry_id.in_(legacy_provision_journals),
            ).update(
                {JournalLine.account_id: provision_5510.id},
                synchronize_session=False,
            )

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


ALLOWED_JOURNAL_STATUSES = {"draft", "posted"}


def _validate_normalized_journal_lines(lines: list[dict]) -> tuple[Decimal, Decimal]:
    """Enforce the Chapter 2 double-entry invariants on a journal payload.

    A journal needs at least two lines, must affect at least two accounts, each
    line must be one-sided, and the total debit must equal the total credit.
    """
    if len(lines) < 2:
        raise HTTPException(status_code=422, detail="A journal entry requires at least two lines")

    account_ids = {item["account_id"] for item in lines}
    if len(account_ids) < 2:
        raise HTTPException(status_code=422, detail="A journal entry must affect at least two accounts")

    for item in lines:
        debit = _money(item.get("debit"))
        credit = _money(item.get("credit"))
        if debit < 0 or credit < 0 or (debit > 0) == (credit > 0):
            raise HTTPException(
                status_code=422,
                detail="Each journal line must contain one positive debit or credit",
            )

    total_debit = sum((_money(item.get("debit")) for item in lines), Decimal("0.00"))
    total_credit = sum((_money(item.get("credit")) for item in lines), Decimal("0.00"))
    if total_debit <= 0 or total_debit != total_credit:
        raise HTTPException(
            status_code=422,
            detail="Journal entry debits and credits must be equal and greater than zero",
        )
    return total_debit, total_credit


def validate_postable_entry(db: Session, entry: JournalEntry) -> tuple[Decimal, Decimal]:
    """Revalidate persisted journal data immediately before it becomes ledger truth.

    Drafts can live for some time before maker/checker approval.  Recomputing the
    invariant from persisted lines prevents a malformed or tampered draft from
    becoming a posted ledger entry.
    """
    lines = db.query(JournalLine).filter(
        JournalLine.journal_entry_id == entry.id
    ).order_by(JournalLine.created_at.asc()).all()

    normalized = [
        {
            "account_id": line.account_id,
            "debit": _money(line.debit),
            "credit": _money(line.credit),
        }
        for line in lines
    ]
    total_debit, total_credit = _validate_normalized_journal_lines(normalized)

    accounts = db.query(AccountingAccount).filter(
        AccountingAccount.id.in_({item["account_id"] for item in normalized}),
        AccountingAccount.scope_key == entry.scope_key,
        AccountingAccount.is_active.is_(True),
    ).all()
    if len(accounts) != len({item["account_id"] for item in normalized}):
        raise HTTPException(
            status_code=422,
            detail="One or more journal accounts are outside the selected ledger",
        )

    if _money(entry.total_debit) != total_debit or _money(entry.total_credit) != total_credit:
        raise HTTPException(
            status_code=409,
            detail="Journal header totals do not match persisted journal lines",
        )
    return total_debit, total_credit


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

    if status_value not in ALLOWED_JOURNAL_STATUSES:
        raise HTTPException(status_code=422, detail="Journal status must be draft or posted")

    normalized = [
        {
            **item,
            "debit": _money(item.get("debit")),
            "credit": _money(item.get("credit")),
        }
        for item in lines
    ]
    total_debit, total_credit = _validate_normalized_journal_lines(normalized)

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
    if payment.loan_id:
        written_off_case = db.query(CollectionCase).filter(
            CollectionCase.company_id == payment.company_id,
            CollectionCase.loan_id == payment.loan_id,
            CollectionCase.write_off_at.is_not(None),
        ).first()
        payment_date = accounting_business_date(
            db, payment.company_id, payment.completed_at or payment.created_at
        )
        if written_off_case and written_off_case.write_off_at.date() <= payment_date:
            method = (
                "cash"
                if payment.payment_method == PaymentMethod.CASH
                else "bank"
                if payment.payment_method == PaymentMethod.BANK
                else "electronic"
            )
            return record_written_off_loan_recovery(
                db,
                company_id=payment.company_id,
                loan_id=payment.loan_id,
                amount=payment.amount,
                recovery_date=payment_date,
                payment_method=method,
                proof_reference=payment.provider_reference or payment.proof_reference,
                description="Recovery received after loan write-off",
                user_id=payment.initiated_by_user_id,
                reference_type="payment_transaction",
                reference_id=str(payment.id),
            )
    if _journal_for_reference(db, key, "payment_transaction", str(payment.id)):
        return _journal_for_reference(db, key, "payment_transaction", str(payment.id))

    ensure_chart(db, company_id=payment.company_id)
    cash = account_by_code(db, key, settlement_account_code(payment.payment_method))
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
    if payment.status != PaymentStatus.SUCCEEDED:
        return
    amount = _money(payment.amount)
    if amount <= 0:
        return

    when = accounting_business_date(db, payment.company_id, payment.completed_at or payment.created_at)
    backdated = bool((payment.provider_payload or {}).get("backdated_by_company_owner"))

    if payment.company_id:
        if payment.purpose == PaymentPurpose.LOAN_REPAYMENT:
            _post_company_loan_repayment(db, payment)
        elif payment.purpose == PaymentPurpose.DIRECT_DEBIT and db.query(PaymentAllocation.id).filter(
            PaymentAllocation.payment_id == payment.id
        ).first():
            _post_company_loan_repayment(db, payment)
        else:
            debit_code, credit_code, description = COMPANY_PAYMENT_RULES.get(
                payment.purpose,
                ("2990", "1000", f"Unclassified outbound payment: {payment.purpose.value}")
                if payment.direction == PaymentDirection.OUTBOUND
                else ("1000", "2990", f"Unclassified inbound payment: {payment.purpose.value}"),
            )
            settlement_code = settlement_account_code(payment.payment_method)
            debit_code = settlement_code if debit_code == "1000" else debit_code
            credit_code = settlement_code if credit_code == "1000" else credit_code
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
        settlement_code = settlement_account_code(payment.payment_method)
        platform_debit = settlement_code if rule[0] == "1000" else rule[0]
        platform_credit = settlement_code if rule[1] == "1000" else rule[1]
        post_codes(
            db,
            company_id=None,
            branch_id=None,
            debit_code=platform_debit,
            credit_code=platform_credit,
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
    """Reverse the exact journals created by a payment and its derived platform charge."""
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
        if payment.loan_id:
            case = db.query(CollectionCase).filter(
                CollectionCase.company_id == payment.company_id,
                CollectionCase.loan_id == payment.loan_id,
                CollectionCase.write_off_at.is_not(None),
            ).first()
            if case:
                case.recovered_amount = _written_off_recovery_balance(
                    db,
                    company_id=payment.company_id,
                    loan_id=payment.loan_id,
                )
                db.add(case)

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

    # A successful payment can also have produced a transaction-charge accrual.
    # Reverse both sides of that accrual from the original journal lines instead
    # of approximating the accounts or amount.
    from database.models.finance import TransactionChargeLedgerEntry
    charge = db.query(TransactionChargeLedgerEntry).filter(
        TransactionChargeLedgerEntry.payment_id == payment.id
    ).first()
    if charge and charge.status not in {"waived", "reversed"}:
        reverse_reference_accounting(
            db,
            company_id=charge.company_id,
            branch_id=None,
            reference_type="platform_transaction_charge_accrual",
            reference_id=str(charge.id),
            user_id=payment.initiated_by_user_id,
            reason=f"transaction charge for reversed payment {payment.id}",
        )
        if _journal_for_reference(
            db, platform_key, "platform_transaction_charge_accrual", str(charge.id)
        ):
            reverse_reference_accounting(
                db,
                company_id=None,
                branch_id=None,
                reference_type="platform_transaction_charge_accrual",
                reference_id=str(charge.id),
                user_id=payment.initiated_by_user_id,
                reason=f"transaction charge for reversed payment {payment.id}",
            )
        charge.status = "reversed"
        charge.waived_at = datetime.now(timezone.utc)
        charge.waiver_reason = "Underlying payment reversed"
        db.add(charge)

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
    settlement_code = settlement_account_code(treasury_entry.payment_method)
    if treasury_entry.entry_type == TreasuryEntryType.OWNER_CONTRIBUTION:
        rule = (settlement_code, "3000")
    elif treasury_entry.entry_type == TreasuryEntryType.EXPENSE:
        rule = ("6500", settlement_code)
    elif treasury_entry.entry_type == TreasuryEntryType.MANUAL_INCOME and direction_in:
        rule = (settlement_code, "4900")
    elif treasury_entry.entry_type == TreasuryEntryType.REFUND:
        rule = ("6300", settlement_code) if not direction_in else (settlement_code, "2300")
    elif direction_in:
        rule = (settlement_code, "2990")
    else:
        rule = ("2990", settlement_code)

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
        debit_code=settlement_account_code(source.payment_method),
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


def record_platform_transaction_charge_accrual(db: Session, charge) -> None:
    """Accrue a LoanHub transaction charge when the charge is earned/incurred.

    Tenant:   Dr platform fees / Cr provider payable
    Platform: Dr tenant receivable / Cr transaction-fee revenue
    """
    amount = _money(charge.charge_amount)
    if amount <= 0:
        return
    when = (charge.accrued_at or datetime.now(timezone.utc)).date()
    post_codes(
        db,
        company_id=charge.company_id,
        branch_id=None,
        debit_code="6600",
        credit_code="2400",
        amount=amount,
        description=f"LoanHub transaction charge {charge.id}",
        reference_type="platform_transaction_charge_accrual",
        reference_id=str(charge.id),
        entry_date=when,
    )
    post_codes(
        db,
        company_id=None,
        branch_id=None,
        debit_code="1200",
        credit_code="4200",
        amount=amount,
        description=f"Transaction fee revenue {charge.id}",
        reference_type="platform_transaction_charge_accrual",
        reference_id=str(charge.id),
        entry_date=when,
    )


def record_credit_bureau_transaction_accrual(db: Session, transaction) -> None:
    """Recognise a live Credit Bureau usage charge when the service is consumed."""
    amount = _money(transaction.amount)
    if amount <= 0 or transaction.status not in {"accrued", "invoiced", "settled"}:
        return
    when = (transaction.accrued_at or datetime.now(timezone.utc)).date()
    post_codes(
        db,
        company_id=transaction.company_id,
        branch_id=None,
        debit_code="6700",
        credit_code="2400",
        amount=amount,
        description=f"Credit Bureau usage {transaction.transaction_reference}",
        reference_type="credit_bureau_transaction_accrual",
        reference_id=str(transaction.id),
        entry_date=when,
    )
    post_codes(
        db,
        company_id=None,
        branch_id=None,
        debit_code="1200",
        credit_code="4500",
        amount=amount,
        description=f"Credit Bureau usage revenue {transaction.transaction_reference}",
        reference_type="credit_bureau_transaction_accrual",
        reference_id=str(transaction.id),
        entry_date=when,
    )


def reverse_credit_bureau_transaction_accrual(db: Session, transaction) -> None:
    """Reverse a previously accrued Credit Bureau charge when it is waived."""
    amount = _money(transaction.amount)
    if amount <= 0:
        return
    when = (transaction.waived_at or datetime.now(timezone.utc)).date()
    post_codes(
        db,
        company_id=transaction.company_id,
        branch_id=None,
        debit_code="2400",
        credit_code="6700",
        amount=amount,
        description=f"Credit Bureau charge waived {transaction.transaction_reference}",
        reference_type="credit_bureau_transaction_waiver",
        reference_id=str(transaction.id),
        entry_date=when,
    )
    post_codes(
        db,
        company_id=None,
        branch_id=None,
        debit_code="4500",
        credit_code="1200",
        amount=amount,
        description=f"Credit Bureau revenue waived {transaction.transaction_reference}",
        reference_type="credit_bureau_transaction_waiver",
        reference_id=str(transaction.id),
        entry_date=when,
    )


def record_cdas_transaction_accrual(db: Session, transaction) -> None:
    """Recognise a live CDAS usage charge when the operation succeeds."""
    amount = _money(transaction.amount)
    if amount <= 0 or transaction.status not in {"accrued", "invoiced", "settled"}:
        return
    when = (transaction.accrued_at or datetime.now(timezone.utc)).date()
    post_codes(
        db,
        company_id=transaction.company_id,
        branch_id=None,
        debit_code="6800",
        credit_code="2400",
        amount=amount,
        description=f"CDAS usage {transaction.transaction_reference}",
        reference_type="cdas_transaction_accrual",
        reference_id=str(transaction.id),
        entry_date=when,
    )
    post_codes(
        db,
        company_id=None,
        branch_id=None,
        debit_code="1200",
        credit_code="4600",
        amount=amount,
        description=f"CDAS usage revenue {transaction.transaction_reference}",
        reference_type="cdas_transaction_accrual",
        reference_id=str(transaction.id),
        entry_date=when,
    )


def reverse_cdas_transaction_accrual(db: Session, transaction) -> None:
    """Reverse a previously accrued CDAS charge when it is waived."""
    amount = _money(transaction.amount)
    if amount <= 0:
        return
    when = (transaction.waived_at or datetime.now(timezone.utc)).date()
    post_codes(
        db,
        company_id=transaction.company_id,
        branch_id=None,
        debit_code="2400",
        credit_code="6800",
        amount=amount,
        description=f"CDAS charge waived {transaction.transaction_reference}",
        reference_type="cdas_transaction_waiver",
        reference_id=str(transaction.id),
        entry_date=when,
    )
    post_codes(
        db,
        company_id=None,
        branch_id=None,
        debit_code="4600",
        credit_code="1200",
        amount=amount,
        description=f"CDAS revenue waived {transaction.transaction_reference}",
        reference_type="cdas_transaction_waiver",
        reference_id=str(transaction.id),
        entry_date=when,
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
    settlement = dict(invoice.snapshot or {}).get("settlement") or {}
    settlement_code = settlement_account_code(settlement.get("payment_method"))
    post_codes(db, company_id=invoice.company_id, branch_id=None, debit_code="2400", credit_code=settlement_code,
               amount=amount, description=f"Credit Bureau invoice payment {invoice.invoice_number}",
               reference_type="credit_bureau_invoice_payment", reference_id=str(invoice.id), entry_date=when)
    post_codes(db, company_id=None, branch_id=None, debit_code=settlement_code, credit_code="1200",
               amount=amount, description=f"Credit Bureau invoice receipt {invoice.invoice_number}",
               reference_type="credit_bureau_invoice_payment", reference_id=str(invoice.id), entry_date=when)


def record_credit_bureau_transaction_refund(db: Session, transaction) -> None:
    """Return a settled Credit Bureau charge using the actual refund channel."""
    amount = _money(transaction.amount)
    if amount <= 0:
        return
    metadata = dict(transaction.metadata_json or {})
    refund = metadata.get("refund") or {}
    refunded_at = refund.get("recorded_at")
    when = date.fromisoformat(str(refunded_at)[:10]) if refunded_at else datetime.now(timezone.utc).date()
    settlement_code = settlement_account_code(refund.get("payment_method"))
    post_codes(
        db,
        company_id=transaction.company_id,
        branch_id=None,
        debit_code=settlement_code,
        credit_code="6700",
        amount=amount,
        description=f"Credit Bureau transaction refund {transaction.transaction_reference}",
        reference_type="credit_bureau_transaction_refund",
        reference_id=str(transaction.id),
        entry_date=when,
    )
    post_codes(
        db,
        company_id=None,
        branch_id=None,
        debit_code="4500",
        credit_code=settlement_code,
        amount=amount,
        description=f"Credit Bureau revenue reversal {transaction.transaction_reference}",
        reference_type="credit_bureau_transaction_refund",
        reference_id=str(transaction.id),
        entry_date=when,
    )


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
    settlement = dict(invoice.snapshot or {}).get("settlement") or {}
    settlement_code = settlement_account_code(settlement.get("payment_method"))
    post_codes(db, company_id=invoice.company_id, branch_id=None, debit_code="2400", credit_code=settlement_code,
               amount=amount, description=f"CDAS invoice payment {invoice.invoice_number}",
               reference_type="cdas_invoice_payment", reference_id=str(invoice.id), entry_date=when)
    post_codes(db, company_id=None, branch_id=None, debit_code=settlement_code, credit_code="1200",
               amount=amount, description=f"CDAS invoice receipt {invoice.invoice_number}",
               reference_type="cdas_invoice_payment", reference_id=str(invoice.id), entry_date=when)


def record_cdas_transaction_refund(db: Session, transaction) -> None:
    amount = _money(transaction.amount)
    if amount <= 0:
        return
    when = (transaction.refunded_at or datetime.now(timezone.utc)).date()
    refund = dict(transaction.metadata_json or {}).get("refund") or {}
    settlement_code = settlement_account_code(refund.get("payment_method"))
    post_codes(db, company_id=transaction.company_id, branch_id=None, debit_code=settlement_code, credit_code="6800",
               amount=amount, description=f"CDAS transaction refund {transaction.transaction_reference}",
               reference_type="cdas_transaction_refund", reference_id=str(transaction.id), entry_date=when)
    post_codes(db, company_id=None, branch_id=None, debit_code="4600", credit_code=settlement_code,
               amount=amount, description=f"CDAS revenue reversal {transaction.transaction_reference}",
               reference_type="cdas_transaction_refund", reference_id=str(transaction.id), entry_date=when)


SETTLEMENT_BOOK_CODES = {"1000", "1010", "1020"}
RECEIVABLE_BOOK_CODES = {"1100", "1110", "1120", "1200"}
PAYABLE_BOOK_CODES = {"2000", "2100", "2300", "2400"}


def classify_book_of_original_entry(entry: JournalEntry) -> tuple[str, str]:
    """Classify a posted journal into the modern equivalent of a book of original entry.

    The classification follows the purpose of Chapters 11-15 rather than forcing
    a lending platform into merchandise-specific books. Cash/bank/electronic
    settlement goes to the cash book; non-cash revenue against receivables maps
    to the sales day book; non-cash expenses/assets against payables map to the
    purchases day book; adjustments and anything else remain in the journal.
    """
    codes = {
        line.account.code
        for line in entry.lines
        if line.account is not None
    }
    types = {
        line.account.account_type
        for line in entry.lines
        if line.account is not None
    }

    if codes & SETTLEMENT_BOOK_CODES:
        return "cash_book", "contains cash, bank or electronic-settlement movement"

    if "revenue" in types and codes & RECEIVABLE_BOOK_CODES:
        return "sales_day_book", "non-cash income recognised against a receivable"

    if ("expense" in types or "asset" in types) and codes & PAYABLE_BOOK_CODES:
        return "purchases_day_book", "non-cash purchase or expense recognised against a payable"

    return "journal", "adjustment, opening, correction or transaction outside specialist day books"


def books_of_original_entry(
    db: Session,
    *,
    company_id,
    from_date: date | None = None,
    to_date: date | None = None,
    branch_id=None,
    book: str | None = None,
) -> list[dict]:
    key, _ = scope_key(company_id)
    query = db.query(JournalEntry).options(
        joinedload(JournalEntry.lines).joinedload(JournalLine.account)
    ).filter(
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
    )
    if from_date:
        query = query.filter(JournalEntry.entry_date >= from_date)
    if to_date:
        query = query.filter(JournalEntry.entry_date <= to_date)
    if branch_id:
        query = query.filter(JournalEntry.branch_id == branch_id)

    rows = []
    for entry in query.order_by(JournalEntry.entry_date.asc(), JournalEntry.created_at.asc()).all():
        source_book, classification_basis = classify_book_of_original_entry(entry)
        if book and source_book != book:
            continue

        folio = []
        for line in entry.lines:
            account = line.account
            folio.append({
                "account_code": account.code if account else None,
                "account_name": account.name if account else None,
                "side": "debit" if _money(line.debit) > 0 else "credit",
                "amount": float(_money(line.debit or line.credit)),
            })

        rows.append({
            "entry_id": str(entry.id),
            "entry_number": entry.entry_number,
            "entry_date": entry.entry_date.isoformat(),
            "book": source_book,
            "classification_basis": classification_basis,
            "narrative": entry.description,
            "reference_type": entry.reference_type,
            "reference_id": entry.reference_id,
            "source_reference": (
                f"{entry.reference_type}:{entry.reference_id}"
                if entry.reference_type and entry.reference_id
                else entry.entry_number
            ),
            "source_reference_kind": (
                "operational_source"
                if entry.reference_type and entry.reference_id
                else "internal_journal_reference"
            ),
            "total_debit": float(_money(entry.total_debit)),
            "total_credit": float(_money(entry.total_credit)),
            "folio": folio,
        })
    return rows


def source_book_traceability(
    db: Session,
    *,
    company_id,
    from_date: date | None = None,
    to_date: date | None = None,
    branch_id=None,
) -> dict:
    rows = books_of_original_entry(
        db,
        company_id=company_id,
        from_date=from_date,
        to_date=to_date,
        branch_id=branch_id,
    )
    counts = {
        "cash_book": 0,
        "sales_day_book": 0,
        "purchases_day_book": 0,
        "journal": 0,
    }
    missing_narrative = 0
    missing_operational_source = 0
    for row in rows:
        counts[row["book"]] = counts.get(row["book"], 0) + 1
        if not str(row["narrative"] or "").strip():
            missing_narrative += 1
        if row["source_reference_kind"] != "operational_source":
            missing_operational_source += 1

    return {
        "from_date": from_date.isoformat() if from_date else None,
        "to_date": to_date.isoformat() if to_date else None,
        "branch_id": str(branch_id) if branch_id else None,
        "posted_entry_count": len(rows),
        "book_counts": counts,
        "missing_narrative_count": missing_narrative,
        "internal_reference_only_count": missing_operational_source,
        "traceability_complete": missing_narrative == 0,
        "note": (
            "Internal-reference-only journals remain traceable by LoanHub journal number, "
            "but operational postings should normally carry reference_type and reference_id."
        ),
    }


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


def post_share_issue(
    db: Session, *, company_id, branch_id, shares_issued: int,
    nominal_value_per_share, issue_price_per_share, settlement_account_code: str,
    description: str, reference_id: str, user_id, entry_date: date | None = None,
) -> JournalEntry:
    """Chapter 35: record paid-up share capital and any share premium."""
    nominal = _money(nominal_value_per_share)
    issue = _money(issue_price_per_share)
    if shares_issued <= 0 or nominal <= 0 or issue <= 0 or issue < nominal:
        raise HTTPException(status_code=422, detail="Invalid share issue terms")

    total_cash = _money(issue * shares_issued)
    share_capital = _money(nominal * shares_issued)
    premium = _money(total_cash - share_capital)

    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    settlement = account_by_code(db, key, settlement_account_code)
    if settlement.account_type != "asset":
        raise HTTPException(status_code=422, detail="Share issue settlement must debit an asset account")

    lines = [
        {"account_id": settlement.id, "debit": total_cash, "credit": 0},
        {"account_id": account_by_code(db, key, "3300").id, "debit": 0, "credit": share_capital},
    ]
    if premium:
        lines.append({"account_id": account_by_code(db, key, "3310").id, "debit": 0, "credit": premium})

    return create_entry(
        db, company_id=company_id, branch_id=branch_id, created_by_user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
        description=description, reference_type="share_issue", reference_id=reference_id,
        status_value="posted", lines=lines,
    )


def post_dividend_payment(
    db: Session, *, company_id, branch_id, amount, settlement_account_code: str,
    description: str, reference_id: str, user_id, entry_date: date | None = None,
) -> JournalEntry:
    """Chapter 35: dividends are distributions of equity, not operating expenses."""
    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    settlement = account_by_code(db, key, settlement_account_code)
    if settlement.account_type != "asset":
        raise HTTPException(status_code=422, detail="Dividend settlement must use cash or bank")
    return create_entry(
        db, company_id=company_id, branch_id=branch_id, created_by_user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
        description=description, reference_type="dividend_payment", reference_id=reference_id,
        status_value="posted",
        lines=[
            {"account_id": account_by_code(db, key, "3200").id, "debit": _money(amount), "credit": 0},
            {"account_id": settlement.id, "debit": 0, "credit": _money(amount)},
        ],
    )


def post_corporation_tax_charge(
    db: Session, *, company_id, branch_id, amount, description: str,
    reference_id: str, user_id, entry_date: date | None = None,
) -> JournalEntry:
    """Chapter 35: Dr corporation tax expense / Cr corporation tax payable."""
    return post_codes(
        db, company_id=company_id, branch_id=branch_id,
        debit_code="6900", credit_code="2600", amount=amount,
        description=description, reference_type="corporation_tax_charge",
        reference_id=reference_id, user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
    )


def post_loan_note_issue(
    db: Session, *, company_id, branch_id, amount, settlement_account_code: str,
    description: str, reference_id: str, user_id, entry_date: date | None = None,
) -> JournalEntry:
    """Chapter 35: issue loan notes as financing, not revenue."""
    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    settlement = account_by_code(db, key, settlement_account_code)
    if settlement.account_type != "asset":
        raise HTTPException(status_code=422, detail="Loan-note proceeds must debit cash or bank")
    return create_entry(
        db, company_id=company_id, branch_id=branch_id, created_by_user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
        description=description, reference_type="loan_note_issue", reference_id=reference_id,
        status_value="posted",
        lines=[
            {"account_id": settlement.id, "debit": _money(amount), "credit": 0},
            {"account_id": account_by_code(db, key, "2500").id, "debit": 0, "credit": _money(amount)},
        ],
    )


def statement_of_changes_in_equity(
    db: Session, *, company_id, from_date: date, to_date: date, branch_id=None,
) -> dict:
    """Chapter 35: reconcile movements in company equity accounts."""
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")
    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)

    accounts = db.query(AccountingAccount).filter(
        AccountingAccount.scope_key == key,
        AccountingAccount.account_type == "equity",
        AccountingAccount.is_active.is_(True),
    ).order_by(AccountingAccount.code.asc()).all()

    movements = []
    opening_total = Decimal("0.00")
    closing_total = Decimal("0.00")
    for account in accounts:
        opening_signed = _account_signed_balance(
            db, scope_key_value=key, account_code=account.code,
            to_date=from_date.fromordinal(from_date.toordinal() - 1), branch_id=branch_id,
        )
        closing_signed = _account_signed_balance(
            db, scope_key_value=key, account_code=account.code,
            to_date=to_date, branch_id=branch_id,
        )
        opening = _money(-opening_signed if account.normal_balance == "credit" else opening_signed)
        closing = _money(-closing_signed if account.normal_balance == "credit" else closing_signed)
        movement = _money(closing - opening)
        opening_total += opening
        closing_total += closing
        movements.append({
            "account_code": account.code,
            "account_name": account.name,
            "opening_balance": float(opening),
            "movement": float(movement),
            "closing_balance": float(closing),
        })

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "opening_equity": float(_money(opening_total)),
        "closing_equity": float(_money(closing_total)),
        "net_movement": float(_money(closing_total - opening_total)),
        "accounts": movements,
    }


def _safe_ratio(numerator: Decimal, denominator: Decimal, *, scale: Decimal = Decimal("1")) -> float | None:
    if denominator == 0:
        return None
    return float((numerator / denominator * scale).quantize(Decimal("0.01")))


def financial_ratio_analysis(
    db: Session,
    *,
    company_id,
    from_date: date,
    to_date: date,
    branch_id=None,
) -> dict:
    """Chapters 38-39: calculate and expose core accounting ratios.

    Ratios are calculation aids and analytical signals.  They do not, by
    themselves, explain why performance changed; interpretation must consider
    the institution's operating context.
    """
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")

    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)

    income_rows = db.query(
        AccountingAccount.code,
        AccountingAccount.account_type,
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalLine, JournalLine.account_id == AccountingAccount.id).join(
        JournalEntry, JournalEntry.id == JournalLine.journal_entry_id
    ).filter(
        AccountingAccount.scope_key == key,
        AccountingAccount.account_type.in_(["revenue", "expense"]),
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date.between(from_date, to_date),
        or_(
            JournalEntry.reference_type.is_(None),
            JournalEntry.reference_type != "year_end_closing",
        ),
    )
    if branch_id:
        income_rows = income_rows.filter(JournalEntry.branch_id == branch_id)
    income_rows = income_rows.group_by(
        AccountingAccount.code, AccountingAccount.account_type
    ).all()

    revenue = Decimal("0.00")
    expense = Decimal("0.00")
    cost_of_services = Decimal("0.00")
    for code, account_type, debit, credit in income_rows:
        balance = _money(Decimal(debit) - Decimal(credit))
        amount = -balance if account_type == "revenue" else balance
        if account_type == "revenue":
            revenue += amount
        else:
            expense += amount
            if code == "5000":
                cost_of_services += amount
    revenue = _money(revenue)
    expense = _money(expense)
    cost_of_services = _money(cost_of_services)
    gross_result = _money(revenue - cost_of_services)
    net_profit = _money(revenue - expense)

    current_asset_codes = {
        "1000", "1010", "1020", "1100", "1110", "1120", "1150",
        "1200", "1210", "1220", "1300", "1400", "1600",
    }
    current_liability_codes = {
        "2000", "2100", "2200", "2300", "2400", "2600", "2990",
    }
    current_assets = Decimal("0.00")
    current_liabilities = Decimal("0.00")
    total_equity = Decimal("0.00")
    position_rows = db.query(AccountingAccount).filter(
        AccountingAccount.scope_key == key,
        AccountingAccount.is_active.is_(True),
    ).all()
    for account in position_rows:
        signed = _account_signed_balance(
            db,
            scope_key_value=key,
            account_code=account.code,
            to_date=to_date,
            branch_id=branch_id,
        )
        presented = (
            -signed
            if account.account_type in {"liability", "equity"}
            else signed
        )
        if account.code in current_asset_codes:
            current_assets += presented
        if account.code in current_liability_codes:
            current_liabilities += presented
        if account.account_type == "equity":
            total_equity += presented

    # Unclosed cumulative profit/loss is part of equity even before a formal
    # retained-earnings closing entry is posted. Use all posted P&L through the
    # reporting date rather than only the requested ratio-analysis period.
    cumulative_rows = db.query(
        AccountingAccount.account_type,
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalLine, JournalLine.account_id == AccountingAccount.id).join(
        JournalEntry, JournalEntry.id == JournalLine.journal_entry_id
    ).filter(
        AccountingAccount.scope_key == key,
        AccountingAccount.account_type.in_(["revenue", "expense"]),
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date <= to_date,
    )
    if branch_id:
        cumulative_rows = cumulative_rows.filter(JournalEntry.branch_id == branch_id)
    cumulative_rows = cumulative_rows.group_by(AccountingAccount.account_type).all()
    cumulative_profit = Decimal("0.00")
    for account_type, debit, credit in cumulative_rows:
        balance = _money(Decimal(debit) - Decimal(credit))
        cumulative_profit += -balance if account_type == "revenue" else -balance
    total_equity = _money(total_equity + cumulative_profit)
    current_assets = _money(current_assets)
    current_liabilities = _money(current_liabilities)
    inventory = _account_signed_balance(
        db, scope_key_value=key, account_code="1300", to_date=to_date, branch_id=branch_id
    )
    inventory = _money(max(inventory, Decimal("0.00")))
    receivables = _money(
        _account_signed_balance(db, scope_key_value=key, account_code="1200", to_date=to_date, branch_id=branch_id)
        + _account_signed_balance(db, scope_key_value=key, account_code="1100", to_date=to_date, branch_id=branch_id)
        + _account_signed_balance(db, scope_key_value=key, account_code="1110", to_date=to_date, branch_id=branch_id)
        + _account_signed_balance(db, scope_key_value=key, account_code="1120", to_date=to_date, branch_id=branch_id)
        + _account_signed_balance(db, scope_key_value=key, account_code="1220", to_date=to_date, branch_id=branch_id)
    )
    trade_payables_signed = _account_signed_balance(
        db, scope_key_value=key, account_code="2000", to_date=to_date, branch_id=branch_id
    )
    trade_payables = _money(max(-trade_payables_signed, Decimal("0.00")))
    loan_notes_signed = _account_signed_balance(
        db, scope_key_value=key, account_code="2500", to_date=to_date, branch_id=branch_id
    )
    loan_notes = _money(max(-loan_notes_signed, Decimal("0.00")))
    capital_employed = _money(total_equity + loan_notes)

    opening_inventory = _account_signed_balance(
        db,
        scope_key_value=key,
        account_code="1300",
        to_date=from_date.fromordinal(from_date.toordinal() - 1),
        branch_id=branch_id,
    )
    opening_inventory = _money(max(opening_inventory, Decimal("0.00")))
    average_inventory = _money((opening_inventory + inventory) / Decimal("2"))
    inventory_turnover = (
        _safe_ratio(cost_of_services, average_inventory)
        if average_inventory > 0
        else None
    )
    inventory_days = (
        round(365 / inventory_turnover, 2)
        if inventory_turnover not in {None, 0}
        else None
    )

    gross_margin_pct = _safe_ratio(gross_result, revenue, scale=Decimal("100"))
    mark_up_pct = _safe_ratio(gross_result, cost_of_services, scale=Decimal("100"))
    net_profit_margin_pct = _safe_ratio(net_profit, revenue, scale=Decimal("100"))
    current_ratio = _safe_ratio(current_assets, current_liabilities)
    acid_test_ratio = _safe_ratio(current_assets - inventory, current_liabilities)
    receivables_days = _safe_ratio(receivables, revenue, scale=Decimal("365"))
    payables_days = _safe_ratio(trade_payables, cost_of_services, scale=Decimal("365"))
    return_on_shareholders_funds_pct = _safe_ratio(
        net_profit, total_equity, scale=Decimal("100")
    )
    return_on_capital_employed_pct = _safe_ratio(
        net_profit, capital_employed, scale=Decimal("100")
    )
    gearing_pct = _safe_ratio(
        loan_notes, capital_employed, scale=Decimal("100")
    )

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "profitability": {
            "gross_margin_percent": gross_margin_pct,
            "mark_up_percent": mark_up_pct,
            "net_profit_margin_percent": net_profit_margin_pct,
            "return_on_shareholders_funds_percent": return_on_shareholders_funds_pct,
            "return_on_capital_employed_percent": return_on_capital_employed_pct,
        },
        "liquidity": {
            "current_ratio": current_ratio,
            "acid_test_ratio": acid_test_ratio,
            "working_capital": float(_money(current_assets - current_liabilities)),
        },
        "efficiency": {
            "inventory_turnover_times": inventory_turnover,
            "inventory_days": inventory_days,
            "receivables_days": receivables_days,
            "payables_days": payables_days,
        },
        "capital_structure": {
            "gearing_percent": gearing_pct,
            "loan_notes": float(loan_notes),
            "total_equity": float(total_equity),
            "capital_employed": float(capital_employed),
        },
        "inputs": {
            "revenue": float(revenue),
            "gross_result": float(gross_result),
            "net_profit": float(net_profit),
            "cost_of_services": float(cost_of_services),
            "current_assets": float(current_assets),
            "current_liabilities": float(current_liabilities),
            "inventory": float(inventory),
            "average_inventory": float(average_inventory),
            "receivables": float(receivables),
            "trade_payables": float(trade_payables),
        },
        "interpretation_note": (
            "Ratios identify relationships and trends but do not explain causes by themselves; "
            "interpret them in the context of the institution, its lending model, market and policies."
        ),
        "book_alignment": {
            "chapter_38": [
                "gross_margin",
                "mark_up",
                "inventory_turnover",
                "inventory_days",
                "current_ratio",
            ],
            "chapter_39": [
                "profitability",
                "liquidity",
                "efficiency",
                "capital_structure",
                "return_on_shareholders_funds",
                "return_on_capital_employed",
            ],
        },
    }


ACCOUNTING_ETHICS_PRINCIPLES = [
    "integrity",
    "objectivity",
    "professional_competence_and_due_care",
    "confidentiality",
    "professional_behaviour",
]


def accounting_modern_practice_readiness(
    db: Session,
    *,
    company_id,
    from_date: date,
    to_date: date,
    branch_id=None,
) -> dict:
    """Chapter 40 governance/readiness view for a modern automated accounting system.

    Chapter 40 emphasises that technology automates more basic accounting work,
    increasing the importance of judgement, analysis, communication and ethics.
    This control therefore reports whether automation remains traceable and whether
    human posting duties are segregated where maker/checker data exists.
    """
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")

    key, _ = scope_key(company_id)
    diagnostics = accounting_error_diagnostics(
        db,
        company_id=company_id,
        from_date=from_date,
        to_date=to_date,
        branch_id=branch_id,
    )
    traceability = source_book_traceability(
        db,
        company_id=company_id,
        from_date=from_date,
        to_date=to_date,
        branch_id=branch_id,
    )
    ratios = financial_ratio_analysis(
        db,
        company_id=company_id,
        from_date=from_date,
        to_date=to_date,
        branch_id=branch_id,
    )

    journals = db.query(JournalEntry).filter(
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date.between(from_date, to_date),
    )
    if branch_id:
        journals = journals.filter(JournalEntry.branch_id == branch_id)
    rows = journals.all()

    maker_checker_population = [
        row for row in rows
        if row.created_by_user_id is not None and row.posted_by_user_id is not None
    ]
    maker_checker_conflicts = [
        row for row in maker_checker_population
        if row.created_by_user_id == row.posted_by_user_id
    ]
    automated_postings = [
        row for row in rows
        if row.posted_by_user_id is None and row.reference_type
    ]
    unattributed_postings = [
        row for row in rows
        if row.created_by_user_id is None and row.posted_by_user_id is None and not row.reference_type
    ]

    controls = {
        "accounting_integrity_controls_healthy": bool(diagnostics["healthy"]),
        "source_traceability_complete": bool(traceability["traceability_complete"]),
        "maker_checker_segregated_where_recorded": len(maker_checker_conflicts) == 0,
        "no_unattributed_postings": len(unattributed_postings) == 0,
        "ratio_analysis_available": bool(ratios.get("book_alignment")),
    }

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "ready": all(controls.values()),
        "controls": controls,
        "automation": {
            "posted_journal_count": len(rows),
            "automated_posting_count": len(automated_postings),
            "maker_checker_population_count": len(maker_checker_population),
            "maker_checker_conflict_count": len(maker_checker_conflicts),
            "maker_checker_conflict_entry_ids": [str(row.id) for row in maker_checker_conflicts],
            "unattributed_posting_count": len(unattributed_postings),
            "unattributed_posting_entry_ids": [str(row.id) for row in unattributed_postings],
        },
        "ethics_principles": ACCOUNTING_ETHICS_PRINCIPLES,
        "ethics_note": (
            "These principles are governance expectations from the book; this endpoint "
            "does not claim that software can determine whether a person is ethical."
        ),
        "technology_note": (
            "Automation should reduce routine bookkeeping while preserving traceability, "
            "controls and human interpretation of financial information."
        ),
        "analysis_note": ratios["interpretation_note"],
        "integrity_diagnostics": {
            "healthy": diagnostics["healthy"],
            "controls": diagnostics["controls"],
        },
        "source_traceability": {
            "posted_entry_count": traceability["posted_entry_count"],
            "internal_reference_only_count": traceability["internal_reference_only_count"],
            "missing_narrative_count": traceability["missing_narrative_count"],
        },
        "book_alignment": {
            "chapter_40": [
                "ethics_and_integrity",
                "technology_and_automation",
                "analysis_and_interpretation",
                "professional_judgement",
                "traceability_and_controls",
            ]
        },
    }


def _year_end_period_coverage(
    db: Session,
    *,
    company_id,
    financial_year_start: date,
    financial_year_end: date,
    branch_id=None,
) -> tuple[list[AccountingPeriod], AccountingPeriod]:
    if financial_year_start > financial_year_end:
        raise HTTPException(status_code=422, detail="Financial year start must not be after financial year end")

    periods = db.query(AccountingPeriod).filter(
        AccountingPeriod.company_id == company_id,
        AccountingPeriod.period_end >= financial_year_start,
        AccountingPeriod.period_start <= financial_year_end,
    )
    if branch_id:
        periods = periods.filter(AccountingPeriod.branch_id == branch_id)
    else:
        periods = periods.filter(AccountingPeriod.branch_id.is_(None))
    periods = periods.order_by(AccountingPeriod.period_start.asc()).all()
    if not periods:
        raise HTTPException(status_code=404, detail="No accounting periods cover the selected financial year")

    expected_start = financial_year_start
    for period in periods:
        if period.period_start != expected_start:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Accounting periods do not continuously cover the selected financial year; "
                    f"expected a period starting {expected_start.isoformat()}"
                ),
            )
        if period.period_end > financial_year_end:
            raise HTTPException(
                status_code=409,
                detail="An accounting period crosses the selected financial-year boundary",
            )
        if period.status != "closed":
            raise HTTPException(
                status_code=409,
                detail=(
                    "Every accounting period in the selected financial year must be hard-closed; "
                    f"{period.period_start.isoformat()} to {period.period_end.isoformat()} is {period.status}"
                ),
            )
        expected_start = period.period_end + timedelta(days=1)

    if expected_start != financial_year_end + timedelta(days=1):
        raise HTTPException(
            status_code=409,
            detail="Accounting periods do not fully cover the selected financial year",
        )

    next_date = financial_year_end + timedelta(days=1)
    next_period = db.query(AccountingPeriod).filter(
        AccountingPeriod.company_id == company_id,
        AccountingPeriod.period_start <= next_date,
        AccountingPeriod.period_end >= next_date,
    )
    if branch_id:
        next_period = next_period.filter(AccountingPeriod.branch_id == branch_id)
    else:
        next_period = next_period.filter(AccountingPeriod.branch_id.is_(None))
    next_period = next_period.first()
    if not next_period:
        raise HTTPException(
            status_code=409,
            detail="Create the next accounting period before preparing year-end closing",
        )
    if next_period.status != "open":
        raise HTTPException(
            status_code=409,
            detail="The next accounting period must be open for year-end closing",
        )
    return periods, next_period


def year_end_closing_preview(
    db: Session,
    *,
    company_id,
    financial_year_start: date,
    financial_year_end: date,
    branch_id=None,
) -> dict:
    """Prepare the retained-earnings transfer across a complete financial year.

    The selected financial year may contain monthly, quarterly or annual
    accounting periods. Every period must be hard-closed with continuous
    coverage. The closing journal is dated on the first day of the next open
    period, while reporting excludes the special journal from operating P&L.
    """
    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    periods, next_period = _year_end_period_coverage(
        db,
        company_id=company_id,
        financial_year_start=financial_year_start,
        financial_year_end=financial_year_end,
        branch_id=branch_id,
    )
    next_date = financial_year_end + timedelta(days=1)

    rows = db.query(
        AccountingAccount.id,
        AccountingAccount.code,
        AccountingAccount.name,
        AccountingAccount.account_type,
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(
        JournalLine, JournalLine.account_id == AccountingAccount.id
    ).join(
        JournalEntry, JournalEntry.id == JournalLine.journal_entry_id
    ).filter(
        AccountingAccount.scope_key == key,
        AccountingAccount.account_type.in_(["revenue", "expense"]),
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date.between(financial_year_start, financial_year_end),
        or_(
            JournalEntry.reference_type.is_(None),
            JournalEntry.reference_type != "year_end_closing",
        ),
    )
    if branch_id:
        rows = rows.filter(JournalEntry.branch_id == branch_id)
    rows = rows.group_by(
        AccountingAccount.id,
        AccountingAccount.code,
        AccountingAccount.name,
        AccountingAccount.account_type,
    ).order_by(AccountingAccount.code.asc()).all()

    closing_lines = []
    revenue_total = Decimal("0.00")
    expense_total = Decimal("0.00")
    for account_id, code, name, account_type, debit, credit in rows:
        debit = _money(debit)
        credit = _money(credit)
        if account_type == "revenue":
            balance = _money(credit - debit)
            revenue_total += balance
            if balance > 0:
                closing_lines.append({
                    "account_id": account_id,
                    "account_code": code,
                    "account_name": name,
                    "debit": balance,
                    "credit": Decimal("0.00"),
                    "purpose": "close_revenue",
                })
            elif balance < 0:
                closing_lines.append({
                    "account_id": account_id,
                    "account_code": code,
                    "account_name": name,
                    "debit": Decimal("0.00"),
                    "credit": abs(balance),
                    "purpose": "close_revenue_debit_balance",
                })
        else:
            balance = _money(debit - credit)
            expense_total += balance
            if balance > 0:
                closing_lines.append({
                    "account_id": account_id,
                    "account_code": code,
                    "account_name": name,
                    "debit": Decimal("0.00"),
                    "credit": balance,
                    "purpose": "close_expense",
                })
            elif balance < 0:
                closing_lines.append({
                    "account_id": account_id,
                    "account_code": code,
                    "account_name": name,
                    "debit": abs(balance),
                    "credit": Decimal("0.00"),
                    "purpose": "close_expense_credit_balance",
                })

    net_profit = _money(revenue_total - expense_total)
    retained = account_by_code(db, key, "3100")
    if net_profit > 0:
        closing_lines.append({
            "account_id": retained.id,
            "account_code": retained.code,
            "account_name": retained.name,
            "debit": Decimal("0.00"),
            "credit": net_profit,
            "purpose": "transfer_profit_to_retained_earnings",
        })
    elif net_profit < 0:
        closing_lines.append({
            "account_id": retained.id,
            "account_code": retained.code,
            "account_name": retained.name,
            "debit": abs(net_profit),
            "credit": Decimal("0.00"),
            "purpose": "transfer_loss_to_retained_earnings",
        })

    total_debit = _money(sum((line["debit"] for line in closing_lines), Decimal("0.00")))
    total_credit = _money(sum((line["credit"] for line in closing_lines), Decimal("0.00")))
    if total_debit != total_credit:
        raise HTTPException(status_code=500, detail="Year-end closing preview is not balanced")

    branch_key = str(branch_id) if branch_id else "ALL"
    reference = (
        f"YEAR-END:{financial_year_start.isoformat()}:"
        f"{financial_year_end.isoformat()}:{branch_key}"
    )
    existing = _journal_for_reference(db, key, "year_end_closing", reference)

    return {
        "source_period_ids": [str(period.id) for period in periods],
        "financial_year_start": financial_year_start.isoformat(),
        "financial_year_end": financial_year_end.isoformat(),
        "closing_date": next_date.isoformat(),
        "next_period_id": str(next_period.id),
        "next_period_status": next_period.status,
        "reference": reference,
        "revenue_total": float(_money(revenue_total)),
        "expense_total": float(_money(expense_total)),
        "net_profit_or_loss": float(net_profit),
        "total_debit": float(total_debit),
        "total_credit": float(total_credit),
        "balanced": total_debit == total_credit,
        "existing_journal_id": str(existing.id) if existing else None,
        "existing_journal_status": existing.status if existing else None,
        "lines": [
            {
                **line,
                "account_id": str(line["account_id"]),
                "debit": float(line["debit"]),
                "credit": float(line["credit"]),
            }
            for line in closing_lines
        ],
        "policy": (
            "All accounting periods in the financial year must be hard-closed. "
            "The closing journal is dated on the first day of the next open period "
            "and is excluded from that period's operating P&L."
        ),
    }


def prepare_year_end_closing_draft(
    db: Session,
    *,
    company_id,
    financial_year_start: date,
    financial_year_end: date,
    branch_id,
    user_id,
) -> JournalEntry:
    preview = year_end_closing_preview(
        db,
        company_id=company_id,
        financial_year_start=financial_year_start,
        financial_year_end=financial_year_end,
        branch_id=branch_id,
    )
    key, _ = scope_key(company_id)
    reference = preview["reference"]
    existing = _journal_for_reference(db, key, "year_end_closing", reference)
    if existing:
        return existing
    if not preview["lines"]:
        raise HTTPException(status_code=409, detail="There is no revenue or expense activity to close")

    return create_entry(
        db,
        company_id=company_id,
        branch_id=branch_id,
        created_by_user_id=user_id,
        entry_date=date.fromisoformat(preview["closing_date"]),
        description=(
            f"Year-end closing transfer for {financial_year_start.isoformat()} "
            f"to {financial_year_end.isoformat()}"
        ),
        reference_type="year_end_closing",
        reference_id=reference,
        status_value="draft",
        lines=[
            {
                "account_id": UUID(line["account_id"]),
                "debit": _money(line["debit"]),
                "credit": _money(line["credit"]),
                "description": line["purpose"],
            }
            for line in preview["lines"]
        ],
    )


def cancel_year_end_closing_draft(
    db: Session,
    *,
    company_id,
    journal_entry_id,
) -> None:
    key, _ = scope_key(company_id)
    entry = entry_query(db, key).filter(
        JournalEntry.id == journal_entry_id,
        JournalEntry.reference_type == "year_end_closing",
    ).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Year-end closing journal not found")
    if entry.status != "draft":
        raise HTTPException(
            status_code=409,
            detail="Only an unposted year-end closing draft can be cancelled",
        )
    db.delete(entry)
    db.flush()


def value_inventory_lower_of_cost_and_nrv(items: list[dict]) -> dict:
    """Chapter 18: value inventory item-by-item at the lower of cost and NRV."""
    valued = []
    total_cost = Decimal("0.00")
    total_nrv = Decimal("0.00")
    total_value = Decimal("0.00")
    total_write_down = Decimal("0.00")

    for item in items:
        cost = _money(item.get("cost"))
        expected_selling_price = _money(item.get("expected_selling_price"))
        costs_to_sell = _money(item.get("costs_to_sell"))
        if cost < 0 or expected_selling_price < 0 or costs_to_sell < 0:
            raise HTTPException(status_code=422, detail="Inventory valuation inputs cannot be negative")

        nrv = max(Decimal("0.00"), _money(expected_selling_price - costs_to_sell))
        value = min(cost, nrv)
        write_down = _money(cost - value)

        valued.append({
            "reference": str(item.get("reference") or "").strip(),
            "cost": float(cost),
            "net_realisable_value": float(nrv),
            "valuation": float(value),
            "write_down": float(write_down),
            "basis": "cost" if cost <= nrv else "net_realisable_value",
        })
        total_cost += cost
        total_nrv += nrv
        total_value += value
        total_write_down += write_down

    return {
        "method": "lower_of_cost_and_net_realisable_value_item_by_item",
        "items": valued,
        "total_cost": float(_money(total_cost)),
        "total_nrv": float(_money(total_nrv)),
        "inventory_value": float(_money(total_value)),
        "write_down": float(_money(total_write_down)),
    }


CAPITAL_COMPONENT_CATEGORIES = {
    "purchase_price",
    "delivery",
    "non_refundable_tax",
    "site_preparation",
    "assembly_installation",
    "testing",
    "professional_fees",
    "improvement",
}
REVENUE_COMPONENT_CATEGORIES = {
    "repair_maintenance",
    "insurance",
    "fuel",
    "day_to_day",
}


def assess_capital_expenditure(
    components: list[dict],
    *,
    borrowing_costs_directly_attributable: bool = False,
    asset_requires_substantial_time_to_prepare: bool = False,
) -> dict:
    """Chapter 20 classification using explicit source-supported component categories."""
    rows = []
    capital_total = Decimal("0.00")
    revenue_total = Decimal("0.00")

    for component in components:
        amount = _money(component.get("amount"))
        category = str(component.get("category") or "").strip()
        if amount <= 0:
            raise HTTPException(status_code=422, detail="Expenditure component amount must be positive")

        if category == "borrowing_cost_construction":
            is_capital = (
                borrowing_costs_directly_attributable
                and asset_requires_substantial_time_to_prepare
            )
            reason = (
                "directly attributable borrowing cost during construction of a qualifying asset"
                if is_capital
                else "borrowing cost does not meet the construction-capitalisation conditions"
            )
        elif category in CAPITAL_COMPONENT_CATEGORIES:
            is_capital = True
            reason = "directly attributable to acquisition, initial use or improvement of a non-current asset"
        elif category in REVENUE_COMPONENT_CATEGORIES:
            is_capital = False
            reason = "day-to-day running or maintenance of existing earning capacity"
        else:
            raise HTTPException(status_code=422, detail=f"Unsupported expenditure category: {category}")

        if is_capital:
            capital_total += amount
        else:
            revenue_total += amount
        rows.append({
            "description": str(component.get("description") or "").strip(),
            "category": category,
            "amount": float(amount),
            "classification": "capital" if is_capital else "revenue",
            "reason": reason,
        })

    return {
        "components": rows,
        "capital_expenditure": float(_money(capital_total)),
        "revenue_expenditure": float(_money(revenue_total)),
        "total": float(_money(capital_total + revenue_total)),
        "policy": "Frank Wood Chapter 20 / IAS 16 principles; IAS 23 condition for qualifying borrowing costs",
    }


def post_accrued_income_adjustment(
    db: Session, *, company_id, branch_id, amount, revenue_account_code: str,
    description: str, reference_id: str, user_id, entry_date: date | None = None,
) -> JournalEntry:
    """Chapter 22 treatment: Dr accrued income / Cr revenue."""
    if not revenue_account_code.startswith("4"):
        raise HTTPException(status_code=422, detail="Accrued income must credit a revenue account")
    return post_codes(
        db, company_id=company_id, branch_id=branch_id,
        debit_code="1220", credit_code=revenue_account_code, amount=amount,
        description=description, reference_type="accrued_income_adjustment",
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


def _cash_flow_section(entry: JournalEntry, counterpart_codes: set[str], *, company_id) -> tuple[str, str]:
    """Classify a cash movement using an explicit accounting policy.

    Frank Wood provides the operating/investing/financing structure. LoanHub's
    lending-business treatment is expressed separately here so it remains
    reviewable rather than being hidden in account heuristics.
    """
    if entry.reference_type in {"fixed_asset_acquisition", "fixed_asset_disposal"}:
        return "investing", "fixed_asset_transaction"
    if counterpart_codes & {"1500", "1510", "4910", "6510"}:
        return "investing", "property_equipment_counterpart"
    if counterpart_codes & {"3000", "3100", "3200"}:
        return "financing", "owner_equity_counterpart"

    # Lending is LoanHub tenants' ordinary revenue-generating activity. The
    # classifier makes that institution-specific policy visible and testable.
    # It should remain subject to each lender's approved reporting policy.
    if company_id is not None and entry.reference_type == "payment_transaction":
        if counterpart_codes & {"1100", "1110", "1120", "4000", "4100", "4200"}:
            return "operating", "lending_business_cash_flow"

    return "operating", "default_operating_activity"


def _cash_balance_at(
    db: Session,
    *,
    key: str,
    cash_ids: set,
    before_date: date | None = None,
    to_date: date | None = None,
    branch_id=None,
) -> Decimal:
    query = db.query(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
        JournalLine.account_id.in_(cash_ids),
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
    )
    if before_date is not None:
        query = query.filter(JournalEntry.entry_date < before_date)
    if to_date is not None:
        query = query.filter(JournalEntry.entry_date <= to_date)
    if branch_id:
        query = query.filter(JournalEntry.branch_id == branch_id)
    debit, credit = query.first()
    return _money(Decimal(debit) - Decimal(credit))


def cash_flow_statement(
    db: Session, *, company_id, from_date: date, to_date: date, branch_id=None,
) -> dict:
    """Summarise posted cash/bank movements into operating, investing and financing.

    The three-section structure follows the textbook. Classification decisions
    specific to a lending business are made by _cash_flow_section and are
    returned with every detail row for auditability.
    """
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")

    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    cash_ids = {
        account_by_code(db, key, code).id
        for code in CASH_EQUIVALENT_CODES
    }
    opening_cash = _cash_balance_at(
        db, key=key, cash_ids=cash_ids, before_date=from_date, branch_id=branch_id
    )

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

    sections = {
        "operating": Decimal("0.00"),
        "investing": Decimal("0.00"),
        "financing": Decimal("0.00"),
    }
    details = []
    for entry in rows.order_by(JournalEntry.entry_date.asc(), JournalEntry.created_at.asc()).all():
        cash_movement = Decimal("0.00")
        counterpart_codes = set()
        for line in entry.lines:
            if line.account_id in cash_ids:
                cash_movement += _money(line.debit) - _money(line.credit)
            elif line.account is not None:
                counterpart_codes.add(line.account.code)

        cash_movement = _money(cash_movement)
        # Cash-to-bank transfers have equal cash inflow/outflow and therefore
        # do not belong in the statement of cash flows.
        if cash_movement == 0:
            continue

        section, classification_basis = _cash_flow_section(
            entry, counterpart_codes, company_id=company_id
        )
        sections[section] = _money(sections[section] + cash_movement)
        details.append({
            "entry_id": str(entry.id),
            "entry_number": entry.entry_number,
            "entry_date": entry.entry_date.isoformat(),
            "description": entry.description,
            "reference_type": entry.reference_type,
            "reference_id": entry.reference_id,
            "section": section,
            "classification_basis": classification_basis,
            "counterpart_account_codes": sorted(counterpart_codes),
            "amount": float(cash_movement),
        })

    net_change = _money(sum(sections.values(), Decimal("0.00")))
    calculated_closing_cash = _money(opening_cash + net_change)
    ledger_closing_cash = _cash_balance_at(
        db, key=key, cash_ids=cash_ids, to_date=to_date, branch_id=branch_id
    )
    reconciliation_difference = _money(ledger_closing_cash - calculated_closing_cash)

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "operating_activities": float(sections["operating"]),
        "investing_activities": float(sections["investing"]),
        "financing_activities": float(sections["financing"]),
        "net_change_in_cash": float(net_change),
        "cash_and_cash_equivalents_at_beginning": float(opening_cash),
        "cash_and_cash_equivalents_at_end": float(ledger_closing_cash),
        "calculated_closing_cash": float(calculated_closing_cash),
        "reconciliation_difference": float(reconciliation_difference),
        "reconciled": reconciliation_difference == 0,
        "classification_policy": {
            "structure": "operating_investing_financing",
            "tenant_lending_cash_flows": "operating",
            "fixed_assets": "investing",
            "owner_equity": "financing",
            "cash_equivalent_account_codes": sorted(CASH_EQUIVALENT_CODES),
            "electronic_clearing": "excluded_until_settled_to_cash_or_bank",
            "note": "Lending-specific classification is an explicit LoanHub policy layer and should be confirmed by each institution's approved reporting policy.",
        },
        "details": details,
    }


def receipts_and_payments_summary(
    db: Session,
    *,
    company_id,
    from_date: date,
    to_date: date,
    branch_id=None,
) -> dict:
    """Chapter 29-style cash-book summary adapted for a profit-oriented lender.

    This is deliberately a receipts/payments statement only. It does not replace
    LoanHub's accrual-basis income statement and is not presented as a non-profit
    income-and-expenditure account.
    """
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")

    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    cash_accounts = {
        account_by_code(db, key, code).id: code
        for code in CASH_EQUIVALENT_CODES
    }
    opening_cash = _cash_balance_at(
        db,
        key=key,
        cash_ids=set(cash_accounts),
        before_date=from_date,
        branch_id=branch_id,
    )

    query = db.query(JournalEntry).options(
        joinedload(JournalEntry.lines).joinedload(JournalLine.account)
    ).filter(
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date.between(from_date, to_date),
    )
    if branch_id:
        query = query.filter(JournalEntry.branch_id == branch_id)

    receipts: dict[tuple[str, str], Decimal] = {}
    payments: dict[tuple[str, str], Decimal] = {}
    detail = []

    for entry in query.order_by(JournalEntry.entry_date.asc(), JournalEntry.created_at.asc()).all():
        cash_movement = Decimal("0.00")
        counterpart_codes = []
        counterpart_names = []
        for line in entry.lines:
            if line.account_id in cash_accounts:
                cash_movement += _money(line.debit) - _money(line.credit)
            elif line.account is not None:
                counterpart_codes.append(line.account.code)
                counterpart_names.append(line.account.name)

        cash_movement = _money(cash_movement)
        if cash_movement == 0:
            continue

        code = ",".join(sorted(set(counterpart_codes))) or "UNCLASSIFIED"
        name = " / ".join(sorted(set(counterpart_names))) or "Unclassified counterpart"
        bucket = receipts if cash_movement > 0 else payments
        key_name = (code, name)
        bucket[key_name] = _money(bucket.get(key_name, Decimal("0.00")) + abs(cash_movement))
        detail.append({
            "entry_id": str(entry.id),
            "entry_number": entry.entry_number,
            "entry_date": entry.entry_date.isoformat(),
            "description": entry.description,
            "reference_type": entry.reference_type,
            "reference_id": entry.reference_id,
            "direction": "receipt" if cash_movement > 0 else "payment",
            "amount": float(abs(cash_movement)),
            "counterpart_account_codes": sorted(set(counterpart_codes)),
        })

    total_receipts = _money(sum(receipts.values(), Decimal("0.00")))
    total_payments = _money(sum(payments.values(), Decimal("0.00")))
    closing_cash = _money(opening_cash + total_receipts - total_payments)

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "opening_cash_and_bank": float(opening_cash),
        "receipts": [
            {"account_code": code, "account_name": name, "amount": float(amount)}
            for (code, name), amount in sorted(receipts.items())
        ],
        "payments": [
            {"account_code": code, "account_name": name, "amount": float(amount)}
            for (code, name), amount in sorted(payments.items())
        ],
        "total_receipts": float(total_receipts),
        "total_payments": float(total_payments),
        "closing_cash_and_bank": float(closing_cash),
        "cash_equivalent_account_codes": sorted(CASH_EQUIVALENT_CODES),
        "basis": "cash_book_summary",
        "note": "This cash-basis summary complements, but does not replace, LoanHub's accrual-basis income statement.",
        "details": detail,
    }


def post_vat_transaction(
    db: Session,
    *,
    company_id,
    branch_id,
    transaction_type: str,
    net_amount,
    vat_amount,
    account_code: str,
    settlement_account_code: str,
    vat_registered: bool,
    description: str,
    reference_id: str,
    user_id,
    entry_date: date | None = None,
) -> JournalEntry:
    """Chapter 16 VAT treatment.

    VAT-registered sale:
      Dr cash/bank/receivable (gross)
      Cr revenue (net)
      Cr VAT payable/output VAT

    VAT-registered purchase/expense/asset:
      Dr expense/asset (net)
      Dr VAT receivable/input VAT
      Cr cash/bank/payable (gross)

    Non-registered entities do not post VAT separately; tax paid is part of cost.
    """
    if transaction_type not in {"sale", "purchase", "expense", "asset"}:
        raise HTTPException(status_code=422, detail="Unsupported VAT transaction type")

    net = _money(net_amount)
    vat = _money(vat_amount)
    gross = _money(net + vat)
    if net <= 0 or vat < 0:
        raise HTTPException(status_code=422, detail="VAT transaction amounts are invalid")
    if not vat_registered and transaction_type == "sale" and vat:
        raise HTTPException(status_code=422, detail="A non-VAT-registered business must not add output VAT")

    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    primary = account_by_code(db, key, account_code)
    settlement = account_by_code(db, key, settlement_account_code)

    if transaction_type == "sale":
        if primary.account_type != "revenue":
            raise HTTPException(status_code=422, detail="Sales must credit a revenue account")
        if settlement.account_type != "asset":
            raise HTTPException(status_code=422, detail="Sales settlement must debit cash, bank or receivables")
        lines = [
            {"account_id": settlement.id, "debit": gross, "credit": 0},
            {"account_id": primary.id, "debit": 0, "credit": net if vat_registered else gross},
        ]
        if vat_registered and vat:
            output_vat = account_by_code(db, key, "2200")
            lines.append({"account_id": output_vat.id, "debit": 0, "credit": vat})
    else:
        if primary.account_type not in {"expense", "asset"}:
            raise HTTPException(status_code=422, detail="Purchase/expense/asset VAT must debit an expense or asset account")
        if settlement.account_type not in {"asset", "liability"}:
            raise HTTPException(status_code=422, detail="Purchase settlement must use cash, bank or a payable account")
        cost = net if vat_registered else gross
        lines = [{"account_id": primary.id, "debit": cost, "credit": 0}]
        if vat_registered and vat:
            input_vat = account_by_code(db, key, "1600")
            lines.append({"account_id": input_vat.id, "debit": vat, "credit": 0})
        lines.append({"account_id": settlement.id, "debit": 0, "credit": gross})

    return create_entry(
        db,
        company_id=company_id,
        branch_id=branch_id,
        created_by_user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
        description=description,
        reference_type="vat_transaction",
        reference_id=reference_id,
        status_value="posted",
        lines=lines,
    )


def post_suspense_correction(
    db: Session,
    *,
    company_id,
    branch_id,
    amount,
    target_account_code: str,
    target_side: str,
    description: str,
    reference_id: str,
    user_id,
    entry_date: date | None = None,
) -> JournalEntry:
    """Chapter 26 correction mechanism.

    Suspense is cleared only by an explicit correcting journal. If the target
    account needs a debit, suspense is credited; if the target needs a credit,
    suspense is debited.
    """
    if target_account_code == "2990":
        raise HTTPException(status_code=422, detail="Suspense correction must target a non-suspense account")
    if target_side not in {"debit", "credit"}:
        raise HTTPException(status_code=422, detail="target_side must be debit or credit")

    debit_code, credit_code = (
        (target_account_code, "2990")
        if target_side == "debit"
        else ("2990", target_account_code)
    )
    return post_codes(
        db,
        company_id=company_id,
        branch_id=branch_id,
        debit_code=debit_code,
        credit_code=credit_code,
        amount=amount,
        description=description,
        reference_type="suspense_correction",
        reference_id=reference_id,
        user_id=user_id,
        entry_date=entry_date or accounting_business_date(db, company_id),
    )


def fixed_asset_query(db: Session, *, company_id, branch_id=None):
    query = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.company_id == company_id,
        CompanyOperatingRecord.module == "accounting",
        CompanyOperatingRecord.record_type == "fixed_asset",
        CompanyOperatingRecord.is_archived.is_(False),
    )
    if branch_id:
        query = query.filter(CompanyOperatingRecord.branch_id == branch_id)
    return query


def _asset_data(asset: CompanyOperatingRecord) -> dict:
    return dict(asset.data or {})


def asset_payload(asset: CompanyOperatingRecord) -> dict:
    data = _asset_data(asset)
    return {
        "id": asset.id,
        "reference": asset.reference,
        "name": asset.title,
        "description": asset.description,
        "status": asset.status,
        "branch_id": asset.branch_id,
        "currency": asset.currency,
        "cost": _money(asset.amount),
        "acquisition_date": date.fromisoformat(data["acquisition_date"]),
        "residual_value": _money(data.get("residual_value")),
        "useful_life_years": int(data["useful_life_years"]),
        "depreciation_method": data["depreciation_method"],
        "depreciation_rate": Decimal(str(data["depreciation_rate"])) if data.get("depreciation_rate") is not None else None,
        "accumulated_depreciation": _money(data.get("accumulated_depreciation")),
        "carrying_amount": _money(data.get("carrying_amount", asset.amount)),
        "location": data.get("location"),
        "serial_number": data.get("serial_number"),
        "assigned_to": data.get("assigned_to"),
        "last_depreciation_date": date.fromisoformat(data["last_depreciation_date"]) if data.get("last_depreciation_date") else None,
        "disposed_at": date.fromisoformat(data["disposed_at"]) if data.get("disposed_at") else None,
        "disposal_proceeds": _money(data["disposal_proceeds"]) if data.get("disposal_proceeds") is not None else None,
    }


def create_fixed_asset(
    db: Session,
    *,
    company_id,
    branch_id,
    reference: str,
    name: str,
    description: str | None,
    acquisition_date: date,
    cost,
    residual_value,
    useful_life_years: int,
    depreciation_method: str,
    depreciation_rate,
    location: str | None,
    serial_number: str | None,
    assigned_to: str | None,
    user_id,
    settlement_account_code: str | None = None,
    post_acquisition: bool = False,
) -> CompanyOperatingRecord:
    if fixed_asset_query(db, company_id=company_id).filter(CompanyOperatingRecord.reference == reference).first():
        raise HTTPException(status_code=409, detail="Fixed asset reference already exists")

    cost = _money(cost)
    residual = _money(residual_value)
    if residual >= cost:
        raise HTTPException(status_code=422, detail="Residual value must be lower than asset cost")
    if depreciation_method not in {"straight_line", "reducing_balance"}:
        raise HTTPException(status_code=422, detail="Unsupported depreciation method")
    if depreciation_method == "reducing_balance" and depreciation_rate is None:
        raise HTTPException(status_code=422, detail="Reducing-balance assets require a depreciation rate")

    rate = Decimal(str(depreciation_rate)) if depreciation_rate is not None else None
    asset = CompanyOperatingRecord(
        company_id=company_id,
        branch_id=branch_id,
        module="accounting",
        record_type="fixed_asset",
        reference=reference.strip(),
        title=name.strip(),
        description=(description or "").strip() or None,
        status="active",
        created_by_user_id=user_id,
        amount=cost,
        currency="LSL",
        data={
            "acquisition_date": acquisition_date.isoformat(),
            "residual_value": str(residual),
            "useful_life_years": useful_life_years,
            "depreciation_method": depreciation_method,
            "depreciation_rate": str(rate) if rate is not None else None,
            "accumulated_depreciation": "0.00",
            "carrying_amount": str(cost),
            "location": location,
            "serial_number": serial_number,
            "assigned_to": assigned_to,
            "last_depreciation_date": None,
            "disposed_at": None,
            "disposal_proceeds": None,
            "depreciation_policy": "monthly_proration",
        },
    )
    db.add(asset)
    db.flush()

    if post_acquisition:
        if not settlement_account_code:
            raise HTTPException(status_code=422, detail="settlement_account_code is required when posting acquisition")
        key, _ = scope_key(company_id)
        ensure_chart(db, company_id=company_id)
        asset_account = account_by_code(db, key, "1500")
        settlement = account_by_code(db, key, settlement_account_code)
        if settlement.account_type not in {"asset", "liability"}:
            raise HTTPException(status_code=422, detail="Asset acquisition settlement must use cash, bank or a payable")
        create_entry(
            db,
            company_id=company_id,
            branch_id=branch_id,
            created_by_user_id=user_id,
            entry_date=acquisition_date,
            description=f"Fixed asset acquisition: {asset.title}",
            reference_type="fixed_asset_acquisition",
            reference_id=str(asset.id),
            status_value="posted",
            lines=[
                {"account_id": asset_account.id, "debit": cost, "credit": 0},
                {"account_id": settlement.id, "debit": 0, "credit": cost},
            ],
        )
    return asset


def _months_inclusive(start: date, end: date) -> int:
    if end < start:
        return 0
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def calculate_fixed_asset_depreciation(
    asset: CompanyOperatingRecord, *, period_start: date, period_end: date
) -> Decimal:
    data = _asset_data(asset)
    acquisition_date = date.fromisoformat(data["acquisition_date"])
    if period_end < acquisition_date:
        return Decimal("0.00")
    if asset.status != "active":
        return Decimal("0.00")

    last_date = date.fromisoformat(data["last_depreciation_date"]) if data.get("last_depreciation_date") else None
    effective_start = max(period_start, acquisition_date)
    if last_date:
        if effective_start <= last_date:
            effective_start = date(last_date.year + (1 if last_date.month == 12 else 0), 1 if last_date.month == 12 else last_date.month + 1, 1)
    if effective_start > period_end:
        return Decimal("0.00")

    cost = _money(asset.amount)
    residual = _money(data.get("residual_value"))
    accumulated = _money(data.get("accumulated_depreciation"))
    carrying = _money(cost - accumulated)
    depreciable_remaining = max(Decimal("0.00"), carrying - residual)
    if depreciable_remaining <= 0:
        return Decimal("0.00")

    months = _months_inclusive(effective_start, period_end)
    method = data["depreciation_method"]
    if method == "straight_line":
        annual = (cost - residual) / Decimal(int(data["useful_life_years"]))
        amount = annual * Decimal(months) / Decimal("12")
    else:
        rate = Decimal(str(data["depreciation_rate"])) / Decimal("100")
        amount = carrying * rate * Decimal(months) / Decimal("12")

    return min(_money(amount), _money(depreciable_remaining))


def post_fixed_asset_depreciation(
    db: Session,
    *,
    asset: CompanyOperatingRecord,
    period_start: date,
    period_end: date,
    user_id,
) -> JournalEntry | None:
    if asset.status != "active":
        raise HTTPException(status_code=409, detail="Only active fixed assets can be depreciated")
    amount = calculate_fixed_asset_depreciation(asset, period_start=period_start, period_end=period_end)
    if amount <= 0:
        return None

    entry = post_depreciation_adjustment(
        db,
        company_id=asset.company_id,
        branch_id=asset.branch_id,
        amount=amount,
        description=f"Depreciation: {asset.reference} - {asset.title}",
        reference_id=f"{asset.id}:{period_start.isoformat()}:{period_end.isoformat()}",
        user_id=user_id,
        entry_date=period_end,
    )
    data = _asset_data(asset)
    accumulated = _money(data.get("accumulated_depreciation")) + amount
    carrying = max(_money(data.get("residual_value")), _money(asset.amount) - accumulated)
    data["accumulated_depreciation"] = str(_money(accumulated))
    data["carrying_amount"] = str(_money(carrying))
    data["last_depreciation_date"] = period_end.isoformat()
    asset.data = data
    db.add(asset)
    return entry


def dispose_fixed_asset(
    db: Session,
    *,
    asset: CompanyOperatingRecord,
    disposal_date: date,
    proceeds,
    settlement_account_code: str,
    description: str,
    user_id,
) -> JournalEntry:
    if asset.status != "active":
        raise HTTPException(status_code=409, detail="Only active fixed assets can be disposed")

    data = _asset_data(asset)
    acquisition_date = date.fromisoformat(data["acquisition_date"])
    if disposal_date < acquisition_date:
        raise HTTPException(status_code=422, detail="Disposal date cannot be before acquisition date")

    last_date = date.fromisoformat(data["last_depreciation_date"]) if data.get("last_depreciation_date") else acquisition_date
    pending_start = acquisition_date if not data.get("last_depreciation_date") else date(
        last_date.year + (1 if last_date.month == 12 else 0),
        1 if last_date.month == 12 else last_date.month + 1,
        1,
    )
    if pending_start <= disposal_date:
        post_fixed_asset_depreciation(
            db, asset=asset, period_start=pending_start, period_end=disposal_date, user_id=user_id
        )
        data = _asset_data(asset)

    cost = _money(asset.amount)
    accumulated = _money(data.get("accumulated_depreciation"))
    carrying = _money(cost - accumulated)
    proceeds = _money(proceeds)
    gain = max(Decimal("0.00"), proceeds - carrying)
    loss = max(Decimal("0.00"), carrying - proceeds)

    key, _ = scope_key(asset.company_id)
    ensure_chart(db, company_id=asset.company_id)
    settlement = account_by_code(db, key, settlement_account_code)
    if settlement.account_type != "asset":
        raise HTTPException(status_code=422, detail="Disposal proceeds must be received into cash/bank/receivable asset account")
    asset_cost = account_by_code(db, key, "1500")
    accumulated_account = account_by_code(db, key, "1510")

    lines = []
    if proceeds:
        lines.append({"account_id": settlement.id, "debit": proceeds, "credit": 0})
    if accumulated:
        lines.append({"account_id": accumulated_account.id, "debit": accumulated, "credit": 0})
    if loss:
        lines.append({"account_id": account_by_code(db, key, "6510").id, "debit": loss, "credit": 0})
    lines.append({"account_id": asset_cost.id, "debit": 0, "credit": cost})
    if gain:
        lines.append({"account_id": account_by_code(db, key, "4910").id, "debit": 0, "credit": gain})

    entry = create_entry(
        db,
        company_id=asset.company_id,
        branch_id=asset.branch_id,
        created_by_user_id=user_id,
        entry_date=disposal_date,
        description=description,
        reference_type="fixed_asset_disposal",
        reference_id=str(asset.id),
        status_value="posted",
        lines=lines,
    )
    data["disposed_at"] = disposal_date.isoformat()
    data["disposal_proceeds"] = str(proceeds)
    data["carrying_amount"] = "0.00"
    data["disposal_gain"] = str(_money(gain))
    data["disposal_loss"] = str(_money(loss))
    asset.data = data
    asset.status = "disposed"
    db.add(asset)
    return entry


def loan_receivables_control_reconciliation(
    db: Session,
    *,
    company_id,
    as_of: date,
    branch_id=None,
) -> dict:
    """Reconcile the loan principal control account to the payment/loan subledger.

    The general ledger side is account 1100. The source-side balance is derived
    independently from successful loan disbursements less the principal portion
    of successful repayments, so a missing or duplicated journal is visible.
    """
    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    principal_account = account_by_code(db, key, "1100")

    ledger_q = db.query(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
        JournalLine.account_id == principal_account.id,
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date <= as_of,
    )
    if branch_id:
        ledger_q = ledger_q.filter(JournalEntry.branch_id == branch_id)
    ledger_debit, ledger_credit = ledger_q.first()
    ledger_balance = _money(Decimal(ledger_debit) - Decimal(ledger_credit))

    payments = db.query(PaymentTransaction).filter(
        PaymentTransaction.company_id == company_id,
        PaymentTransaction.status == PaymentStatus.SUCCEEDED,
        PaymentTransaction.purpose.in_([
            PaymentPurpose.LOAN_DISBURSEMENT,
            PaymentPurpose.LOAN_REPAYMENT,
            PaymentPurpose.DIRECT_DEBIT,
        ]),
        func.date(func.coalesce(PaymentTransaction.completed_at, PaymentTransaction.created_at)) <= as_of,
    )
    if branch_id:
        payments = payments.join(
            ClientCompanyLoan, ClientCompanyLoan.id == PaymentTransaction.loan_id
        ).filter(ClientCompanyLoan.branch_id == branch_id)

    disbursed = Decimal("0.00")
    principal_repaid = Decimal("0.00")
    disbursement_count = repayment_count = 0
    for payment in payments.all():
        if payment.purpose == PaymentPurpose.LOAN_DISBURSEMENT:
            disbursed += _money(payment.amount)
            disbursement_count += 1
        elif payment.purpose in {PaymentPurpose.LOAN_REPAYMENT, PaymentPurpose.DIRECT_DEBIT}:
            principal, _, _ = _loan_repayment_components(db, payment)
            principal_repaid += principal
            repayment_count += 1

    written_off_principal = Decimal("0.00")
    write_off_count = 0
    writeoff_cases = db.query(CollectionCase).join(
        ClientCompanyLoan, ClientCompanyLoan.id == CollectionCase.loan_id
    ).filter(
        CollectionCase.company_id == company_id,
        CollectionCase.write_off_at.is_not(None),
        func.date(CollectionCase.write_off_at) <= as_of,
    )
    if branch_id:
        writeoff_cases = writeoff_cases.filter(ClientCompanyLoan.branch_id == branch_id)
    for case in writeoff_cases.all():
        written_off_principal += loan_source_principal_outstanding(
            db,
            company_id=company_id,
            loan_id=case.loan_id,
            as_of=case.write_off_at.date(),
        )
        write_off_count += 1

    subledger_balance = _money(disbursed - principal_repaid - written_off_principal)
    variance = _money(ledger_balance - subledger_balance)
    return {
        "as_of": as_of.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "ledger_account_code": "1100",
        "ledger_principal_receivable": float(ledger_balance),
        "source_disbursements": float(_money(disbursed)),
        "source_principal_repayments": float(_money(principal_repaid)),
        "source_written_off_principal": float(_money(written_off_principal)),
        "source_principal_receivable": float(subledger_balance),
        "variance": float(variance),
        "balanced": variance == 0,
        "source_counts": {
            "disbursements": disbursement_count,
            "repayments": repayment_count,
            "write_offs": write_off_count,
        },
    }


def loan_source_principal_outstanding(
    db: Session,
    *,
    company_id,
    loan_id,
    as_of: date,
) -> Decimal:
    payments = db.query(PaymentTransaction).filter(
        PaymentTransaction.company_id == company_id,
        PaymentTransaction.loan_id == loan_id,
        PaymentTransaction.status == PaymentStatus.SUCCEEDED,
        PaymentTransaction.purpose.in_([
            PaymentPurpose.LOAN_DISBURSEMENT,
            PaymentPurpose.LOAN_REPAYMENT,
            PaymentPurpose.DIRECT_DEBIT,
        ]),
        func.date(func.coalesce(PaymentTransaction.completed_at, PaymentTransaction.created_at)) <= as_of,
    ).all()
    disbursed = Decimal("0.00")
    principal_repaid = Decimal("0.00")
    for payment in payments:
        if payment.purpose == PaymentPurpose.LOAN_DISBURSEMENT:
            disbursed += _money(payment.amount)
        elif payment.purpose in {PaymentPurpose.LOAN_REPAYMENT, PaymentPurpose.DIRECT_DEBIT}:
            principal, _, _ = _loan_repayment_components(db, payment)
            principal_repaid += principal
    return max(_money(disbursed - principal_repaid), Decimal("0.00"))


def post_loan_write_off(
    db: Session,
    *,
    company_id,
    loan_id,
    write_off_date: date,
    description: str,
    user_id,
) -> JournalEntry:
    """Write off a loan principal after operational collections have marked it written off.

    The available credit-loss allowance is used first; any uncovered principal
    is charged to credit-loss provision expense. The gross loan receivable is
    removed from account 1100. The source loan remains available operationally
    for recoveries and audit history.
    """
    loan = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == loan_id,
        ClientCompanyLoan.company_id == company_id,
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    case = db.query(CollectionCase).filter(
        CollectionCase.company_id == company_id,
        CollectionCase.loan_id == loan_id,
    ).first()
    if not case or case.status != "written_off":
        raise HTTPException(
            status_code=409,
            detail="Collections must mark the loan written_off before accounting can derecognise the receivable",
        )

    key, _ = scope_key(company_id)
    existing = _journal_for_reference(db, key, "loan_write_off", str(loan_id))
    if existing:
        return existing

    principal = loan_source_principal_outstanding(
        db, company_id=company_id, loan_id=loan_id, as_of=write_off_date
    )
    if principal <= 0:
        raise HTTPException(status_code=409, detail="No outstanding loan principal remains to write off")

    ensure_chart(db, company_id=company_id)
    allowance_account = account_by_code(db, key, "1150")
    expense_account = account_by_code(db, key, "5510")
    principal_account = account_by_code(db, key, "1100")

    allowance_q = db.query(
        func.coalesce(func.sum(JournalLine.credit), 0),
        func.coalesce(func.sum(JournalLine.debit), 0),
    ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
        JournalLine.account_id == allowance_account.id,
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date <= write_off_date,
    )
    allowance_credit, allowance_debit = allowance_q.first()
    allowance_available = max(
        _money(Decimal(allowance_credit) - Decimal(allowance_debit)),
        Decimal("0.00"),
    )
    allowance_used = min(principal, allowance_available)
    uncovered = _money(principal - allowance_used)

    lines = []
    if allowance_used:
        lines.append({
            "account_id": allowance_account.id,
            "debit": allowance_used,
            "credit": 0,
            "description": "Use credit-loss allowance on write-off",
        })
    if uncovered:
        lines.append({
            "account_id": expense_account.id,
            "debit": uncovered,
            "credit": 0,
            "description": "Uncovered loan write-off expense",
        })
    lines.append({
        "account_id": principal_account.id,
        "debit": 0,
        "credit": principal,
        "description": "Derecognise written-off loan principal",
    })

    return create_entry(
        db,
        company_id=company_id,
        branch_id=loan.branch_id,
        created_by_user_id=user_id,
        entry_date=write_off_date,
        description=description,
        reference_type="loan_write_off",
        reference_id=str(loan_id),
        status_value="posted",
        lines=lines,
    )


def _account_signed_balance(
    db: Session,
    *,
    scope_key_value: str,
    account_code: str,
    to_date: date,
    branch_id=None,
) -> Decimal:
    account = account_by_code(db, scope_key_value, account_code)
    query = db.query(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
        JournalLine.account_id == account.id,
        JournalEntry.scope_key == scope_key_value,
        JournalEntry.status == "posted",
        JournalEntry.entry_date <= to_date,
    )
    if branch_id:
        query = query.filter(JournalEntry.branch_id == branch_id)
    debit, credit = query.first()
    return _money(Decimal(debit) - Decimal(credit))


def period_close_pack(
    db: Session,
    *,
    company_id,
    period_start: date,
    period_end: date,
    branch_id=None,
) -> dict:
    """Evidence pack and hard checks used before locking an accounting period.

    The pack does not invent adjustments. It verifies that source records,
    reconciliations and deterministic period-end postings are complete enough
    for finance to lock the books.
    """
    if period_end < period_start:
        raise HTTPException(status_code=422, detail="Period end must be on or after period start")

    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)

    trial = db.query(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date <= period_end,
    )
    if branch_id:
        trial = trial.filter(JournalEntry.branch_id == branch_id)
    total_debit, total_credit = trial.first()
    total_debit = _money(total_debit)
    total_credit = _money(total_credit)

    suspense = _account_signed_balance(
        db, scope_key_value=key, account_code="2990", to_date=period_end, branch_id=branch_id
    )
    vat_receivable = _account_signed_balance(
        db, scope_key_value=key, account_code="1600", to_date=period_end, branch_id=branch_id
    )
    vat_payable_signed = _account_signed_balance(
        db, scope_key_value=key, account_code="2200", to_date=period_end, branch_id=branch_id
    )
    accruals_signed = _account_signed_balance(
        db, scope_key_value=key, account_code="2100", to_date=period_end, branch_id=branch_id
    )
    prepayments = _account_signed_balance(
        db, scope_key_value=key, account_code="1400", to_date=period_end, branch_id=branch_id
    )

    drafts = db.query(JournalEntry.id).filter(
        JournalEntry.company_id == company_id,
        JournalEntry.entry_date.between(period_start, period_end),
        JournalEntry.status == "draft",
    )
    bank_unmatched = db.query(BankStatementLine.id).filter(
        BankStatementLine.company_id == company_id,
        BankStatementLine.transaction_date.between(period_start, period_end),
        BankStatementLine.status == "unmatched",
    )
    canonical_bank_batch_q = db.query(ReconciliationBatch.id).filter(
        ReconciliationBatch.company_id == company_id,
        ReconciliationBatch.source_type == "bank_statement",
        ReconciliationBatch.period_end >= period_start,
        ReconciliationBatch.period_start <= period_end,
    )
    approvals = db.query(ApprovalRequest.id).filter(
        ApprovalRequest.company_id == company_id,
        ApprovalRequest.status == "pending",
    )
    reconciliation_open = db.query(ReconciliationBatch.id).filter(
        ReconciliationBatch.company_id == company_id,
        ReconciliationBatch.period_end <= period_end,
        ReconciliationBatch.period_end >= period_start,
        ReconciliationBatch.status != "closed",
    )
    if branch_id:
        drafts = drafts.filter(JournalEntry.branch_id == branch_id)
        bank_unmatched = bank_unmatched.filter(BankStatementLine.branch_id == branch_id)
        canonical_bank_batch_q = canonical_bank_batch_q.filter(
            (ReconciliationBatch.branch_id == branch_id) | (ReconciliationBatch.branch_id.is_(None))
        )
        approvals = approvals.filter(
            (ApprovalRequest.branch_id == branch_id) | (ApprovalRequest.branch_id.is_(None))
        )
        reconciliation_open = reconciliation_open.filter(
            (ReconciliationBatch.branch_id == branch_id) | (ReconciliationBatch.branch_id.is_(None))
        )

    loan_query = db.query(ClientCompanyLoan.id).filter(
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.balance > 0,
    )
    if branch_id:
        loan_query = loan_query.filter(ClientCompanyLoan.branch_id == branch_id)
    active_loan_count = loan_query.count()

    provision = db.query(CreditLossProvisionRun).filter(
        CreditLossProvisionRun.company_id == company_id,
        CreditLossProvisionRun.as_of_date == period_end,
        CreditLossProvisionRun.status == "posted",
    )
    if branch_id:
        provision = provision.filter(CreditLossProvisionRun.branch_id == branch_id)
    else:
        provision = provision.filter(CreditLossProvisionRun.branch_scope_key == "ALL")
    provision_posted = provision.first() is not None

    assets = fixed_asset_query(db, company_id=company_id, branch_id=branch_id).filter(
        CompanyOperatingRecord.status == "active"
    ).all()
    asset_depreciation_due = []
    for asset in assets:
        data = _asset_data(asset)
        acquired = date.fromisoformat(data["acquisition_date"])
        if acquired > period_end:
            continue
        last = date.fromisoformat(data["last_depreciation_date"]) if data.get("last_depreciation_date") else None
        if last is None or last < period_end:
            asset_depreciation_due.append(str(asset.id))

    receivables_control = loan_receivables_control_reconciliation(
        db, company_id=company_id, as_of=period_end, branch_id=branch_id
    )
    cash_flow = cash_flow_statement(
        db,
        company_id=company_id,
        from_date=period_start,
        to_date=period_end,
        branch_id=branch_id,
    )
    coverage = transaction_accounting_coverage(
        db,
        company_id=company_id,
        from_date=period_start,
        to_date=period_end,
        branch_id=branch_id,
    )
    electronic_clearing = electronic_clearing_reconciliation(
        db,
        company_id=company_id,
        as_of=period_end,
        branch_id=branch_id,
    )
    electronic_clearing_age = electronic_clearing_aging(
        db,
        company_id=company_id,
        as_of=period_end,
        branch_id=branch_id,
    )
    settlement_chain = bank_settlement_chain(
        db,
        company_id=company_id,
        from_date=period_start,
        to_date=period_end,
        branch_id=branch_id,
    )

    bank_account = account_by_code(db, key, "1010")
    bank_activity_q = db.query(JournalLine.id).join(
        JournalEntry, JournalEntry.id == JournalLine.journal_entry_id
    ).filter(
        JournalLine.account_id == bank_account.id,
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date.between(period_start, period_end),
    )
    if branch_id:
        bank_activity_q = bank_activity_q.filter(JournalEntry.branch_id == branch_id)
    bank_activity_count = bank_activity_q.count()
    bank_opening = _cash_balance_at(
        db,
        key=key,
        cash_ids={bank_account.id},
        before_date=period_start,
        branch_id=branch_id,
    )
    bank_closing = _cash_balance_at(
        db,
        key=key,
        cash_ids={bank_account.id},
        to_date=period_end,
        branch_id=branch_id,
    )
    bank_reconciliation_required = bool(
        bank_activity_count or bank_opening != 0 or bank_closing != 0
    )

    bank_batch_q = db.query(ReconciliationBatch).filter(
        ReconciliationBatch.company_id == company_id,
        ReconciliationBatch.source_type == "bank_statement",
        ReconciliationBatch.period_start == period_start,
        ReconciliationBatch.period_end == period_end,
        ReconciliationBatch.status == "closed",
    )
    if branch_id:
        bank_batch_q = bank_batch_q.filter(ReconciliationBatch.branch_id == branch_id)
    else:
        bank_batch_q = bank_batch_q.filter(ReconciliationBatch.branch_id.is_(None))
    bank_batch = bank_batch_q.order_by(ReconciliationBatch.closed_at.desc()).first()
    bank_balance_control = {
        "required": bank_reconciliation_required,
        "configured": False,
        "balanced": not bank_reconciliation_required,
        "reason": "No bank activity in this period" if not bank_reconciliation_required else "Closed bank reconciliation batch not found",
    }
    if bank_batch is not None:
        from services.reconciliation_service import bank_statement_balance_reconciliation
        bank_balance_control = {
            "required": bank_reconciliation_required,
            **bank_statement_balance_reconciliation(db, bank_batch),
        }

    legacy_bank_unmatched_count = bank_unmatched.count()
    canonical_bank_batch_exists = canonical_bank_batch_q.first() is not None

    checks = {
        "trial_balance_balanced": total_debit == total_credit,
        "suspense_cleared": suspense == 0,
        "draft_journals_cleared": drafts.count() == 0,
        "bank_statement_exceptions_cleared": (
            True if canonical_bank_batch_exists else legacy_bank_unmatched_count == 0
        ),
        "reconciliation_batches_closed": reconciliation_open.count() == 0,
        "pending_financial_approvals_cleared": approvals.count() == 0,
        "loan_receivables_control_balanced": bool(receivables_control["balanced"]),
        "cash_flow_reconciled": bool(cash_flow["reconciled"]),
        "transaction_accounting_coverage_complete": bool(coverage["complete"]),
        "electronic_clearing_reconciled": bool(electronic_clearing["balanced"]),
        "electronic_clearing_has_no_stale_items": not bool(electronic_clearing_age["has_stale_items"]),
        "clearing_settlements_bank_matched": bool(settlement_chain["complete"]),
        "bank_statement_balance_reconciled": (
            not bank_reconciliation_required or bool(bank_balance_control.get("balanced"))
        ),
        "fixed_asset_depreciation_complete": len(asset_depreciation_due) == 0,
        "credit_loss_provision_posted": active_loan_count == 0 or provision_posted,
    }
    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "ready_to_lock": all(checks.values()),
        "checks": checks,
        "counts": {
            "draft_journals": drafts.count(),
            "legacy_unmatched_bank_lines": legacy_bank_unmatched_count,
            "canonical_bank_batch_exists": int(canonical_bank_batch_exists),
            "open_reconciliation_batches": reconciliation_open.count(),
            "pending_approvals": approvals.count(),
            "active_loans": active_loan_count,
            "fixed_assets_needing_depreciation": len(asset_depreciation_due),
            "bank_ledger_activity": bank_activity_count,
        },
        "balances": {
            "trial_debit": float(total_debit),
            "trial_credit": float(total_credit),
            "trial_difference": float(_money(total_debit - total_credit)),
            "suspense": float(suspense),
            "vat_receivable": float(vat_receivable),
            "vat_payable": float(-vat_payable_signed),
            "net_vat_payable": float(_money((-vat_payable_signed) - vat_receivable)),
            "accruals": float(-accruals_signed),
            "prepayments": float(prepayments),
            "bank_opening": float(bank_opening),
            "bank_closing": float(bank_closing),
        },
        "loan_receivables_control": receivables_control,
        "cash_flow": cash_flow,
        "transaction_accounting_coverage": coverage,
        "electronic_clearing": electronic_clearing,
        "electronic_clearing_aging": electronic_clearing_age,
        "bank_settlement_chain": settlement_chain,
        "bank_statement_balance_reconciliation": bank_balance_control,
        "fixed_asset_ids_needing_depreciation": asset_depreciation_due,
        "credit_loss_provision_run_id": str(provision.first().id) if provision.first() else None,
    }



MONTH_END_ADJUSTMENT_REFERENCE_TYPES = {
    "accrual_adjustment",
    "prepayment_adjustment",
    "accrued_income_adjustment",
    "depreciation_adjustment",
    "doubtful_debt_allowance",
    "credit_loss_provision_run",
    "corporation_tax_charge",
    "period_adjustment_reversal",
}


def loan_receivables_subledger(
    db: Session,
    *,
    company_id,
    as_of: date,
    branch_id=None,
) -> dict:
    """Build loan-by-loan principal folios and reconcile them to GL control 1100.

    Each folio is derived from successful disbursement/repayment source records,
    independently of the general ledger. Written-off loans are reduced to zero
    from their write-off date so the folio total follows the same source basis
    used by the receivables control reconciliation.
    """
    control = loan_receivables_control_reconciliation(
        db,
        company_id=company_id,
        as_of=as_of,
        branch_id=branch_id,
    )

    loans = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.company_id == company_id,
    )
    if branch_id:
        loans = loans.filter(ClientCompanyLoan.branch_id == branch_id)

    written_off_ids = {
        row.loan_id
        for row in db.query(CollectionCase).filter(
            CollectionCase.company_id == company_id,
            CollectionCase.write_off_at.is_not(None),
            func.date(CollectionCase.write_off_at) <= as_of,
        ).all()
    }

    folios = []
    source_total = Decimal("0.00")
    for loan in loans.order_by(ClientCompanyLoan.created_at.asc()).all():
        balance = Decimal("0.00") if loan.id in written_off_ids else loan_source_principal_outstanding(
            db,
            company_id=company_id,
            loan_id=loan.id,
            as_of=as_of,
        )
        balance = _money(balance)
        if balance == 0 and loan.id not in written_off_ids:
            # Settled zero-balance folios add noise to month-end control packs.
            continue
        source_total += balance
        folios.append({
            "loan_id": str(loan.id),
            "loan_reference": loan.loan_reference,
            "folio_number": loan.folio_number,
            "borrower_id": str(loan.borrower_id),
            "branch_id": str(loan.branch_id) if loan.branch_id else None,
            "status": str(getattr(getattr(loan, "status", None), "value", getattr(loan, "status", "")) or ""),
            "operational_balance": float(_money(getattr(loan, "balance", 0))),
            "source_principal_outstanding": float(balance),
            "written_off": loan.id in written_off_ids,
        })

    source_total = _money(source_total)
    control_source_total = _money(control["source_principal_receivable"])
    folio_to_control_variance = _money(source_total - control_source_total)
    return {
        "as_of": as_of.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "ledger_account_code": "1100",
        "folio_count": len(folios),
        "folio_total": float(source_total),
        "control_source_total": float(control_source_total),
        "general_ledger_total": float(_money(control["ledger_principal_receivable"])),
        "folio_to_control_variance": float(folio_to_control_variance),
        "control_to_gl_variance": float(_money(control["variance"])),
        "balanced": folio_to_control_variance == 0 and bool(control["balanced"]),
        "folios": folios,
    }


def month_end_control_pack(
    db: Session,
    *,
    company_id,
    period_start: date,
    period_end: date,
    branch_id=None,
) -> dict:
    """Accountant-facing month-end evidence pack.

    This extends the hard close pack with the supporting loan folios, fixed-asset
    depreciation preview and an adjustment register. It does not invent or post
    estimates: finance can see what is outstanding before locking the period.
    """
    close_pack = period_close_pack(
        db,
        company_id=company_id,
        period_start=period_start,
        period_end=period_end,
        branch_id=branch_id,
    )
    receivables = loan_receivables_subledger(
        db,
        company_id=company_id,
        as_of=period_end,
        branch_id=branch_id,
    )
    vat_control = vat_control_reconciliation(
        db,
        company_id=company_id,
        period_start=period_start,
        period_end=period_end,
        branch_id=branch_id,
    )

    assets = fixed_asset_query(db, company_id=company_id, branch_id=branch_id).filter(
        CompanyOperatingRecord.status == "active"
    ).all()
    depreciation_due = []
    depreciation_total = Decimal("0.00")
    for asset in assets:
        data = _asset_data(asset)
        acquisition_date = date.fromisoformat(data["acquisition_date"])
        if acquisition_date > period_end:
            continue
        amount = calculate_fixed_asset_depreciation(
            asset,
            period_start=period_start,
            period_end=period_end,
        )
        if amount <= 0:
            continue
        depreciation_total += amount
        depreciation_due.append({
            "asset_id": str(asset.id),
            "reference": asset.reference,
            "name": asset.title,
            "branch_id": str(asset.branch_id) if asset.branch_id else None,
            "amount_due": float(_money(amount)),
            "carrying_amount_before": float(_money(data.get("carrying_amount", asset.amount))),
            "last_depreciation_date": data.get("last_depreciation_date"),
        })

    adjustments = db.query(JournalEntry).filter(
        JournalEntry.company_id == company_id,
        JournalEntry.entry_date.between(period_start, period_end),
        JournalEntry.reference_type.in_(MONTH_END_ADJUSTMENT_REFERENCE_TYPES),
    )
    if branch_id:
        adjustments = adjustments.filter(JournalEntry.branch_id == branch_id)
    adjustment_rows = adjustments.order_by(
        JournalEntry.entry_date.asc(),
        JournalEntry.created_at.asc(),
    ).all()
    adjustment_register = [
        {
            "journal_entry_id": str(row.id),
            "entry_number": row.entry_number,
            "entry_date": row.entry_date.isoformat(),
            "reference_type": row.reference_type,
            "reference_id": row.reference_id,
            "description": row.description,
            "status": row.status,
            "amount": float(_money(row.total_debit)),
        }
        for row in adjustment_rows
    ]
    draft_adjustments = sum(1 for row in adjustment_rows if row.status == "draft")
    posted_adjustments = sum(1 for row in adjustment_rows if row.status == "posted")

    extended_checks = {
        "loan_folio_subledger_agrees_to_control_and_gl": bool(receivables["balanced"]),
        "month_end_adjustment_drafts_cleared": draft_adjustments == 0,
    }
    failed = [
        name for name, passed in {**close_pack["checks"], **extended_checks}.items()
        if not passed
    ]

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "ready_to_lock": bool(close_pack["ready_to_lock"]) and all(extended_checks.values()),
        "failed_checks": failed,
        "checks": {**close_pack["checks"], **extended_checks},
        "loan_receivables_subledger": receivables,
        "vat_reconciliation": vat_control,
        "fixed_asset_depreciation": {
            "asset_count_due": len(depreciation_due),
            "total_due": float(_money(depreciation_total)),
            "assets": depreciation_due,
        },
        "adjustment_register": {
            "posted_count": posted_adjustments,
            "draft_count": draft_adjustments,
            "entries": adjustment_register,
            "supported_reference_types": sorted(MONTH_END_ADJUSTMENT_REFERENCE_TYPES),
        },
        "close_pack": close_pack,
        "policy_note": (
            "The month-end pack reconciles supporting records to posted ledger truth. "
            "Estimated accruals, prepayments and other judgemental adjustments remain "
            "human-controlled journal decisions and are never fabricated by this pack."
        ),
    }


MONTH_END_DRAFT_TYPES = {
    "accrual": "accrual_adjustment",
    "prepayment": "prepayment_adjustment",
    "accrued_income": "accrued_income_adjustment",
}


def prepare_month_end_adjustment_draft(
    db: Session,
    *,
    company_id,
    branch_id,
    adjustment_type: str,
    amount,
    account_code: str,
    description: str,
    reference_id: str,
    entry_date: date,
    user_id,
    reversal_date: date | None = None,
) -> JournalEntry:
    """Prepare, but never post, a judgemental month-end adjustment.

    Accruals, prepayments and accrued income require human evidence and judgement.
    This helper translates the approved accounting treatment into balanced lines,
    leaves the entry in draft, and optionally records a future reversal schedule.
    A different finance user must post the journal through the normal maker/checker
    endpoint before it becomes ledger truth.
    """
    if adjustment_type not in MONTH_END_DRAFT_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported month-end adjustment type")
    amount = _money(amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Month-end adjustment amount must be greater than zero")
    if reversal_date is not None and reversal_date <= entry_date:
        raise HTTPException(status_code=422, detail="Scheduled reversal date must be after the adjustment date")

    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)

    if adjustment_type == "accrual":
        if not account_code.startswith(("5", "6")):
            raise HTTPException(status_code=422, detail="Accruals must use an expense account")
        debit = account_by_code(db, key, account_code)
        credit = account_by_code(db, key, "2100")
        line_purpose = ("Accrued expense", "Accrued expenses liability")
    elif adjustment_type == "prepayment":
        if not account_code.startswith(("5", "6")):
            raise HTTPException(status_code=422, detail="Prepayments must use an expense account")
        debit = account_by_code(db, key, "1400")
        credit = account_by_code(db, key, account_code)
        line_purpose = ("Prepayment asset", "Expense deferred")
    else:
        if not account_code.startswith("4"):
            raise HTTPException(status_code=422, detail="Accrued income must use a revenue account")
        debit = account_by_code(db, key, "1220")
        credit = account_by_code(db, key, account_code)
        line_purpose = ("Accrued income asset", "Revenue accrued")

    entry = create_entry(
        db,
        company_id=company_id,
        branch_id=branch_id,
        created_by_user_id=user_id,
        entry_date=entry_date,
        description=description,
        reference_type=MONTH_END_DRAFT_TYPES[adjustment_type],
        reference_id=reference_id,
        status_value="draft",
        lines=[
            {"account_id": debit.id, "debit": amount, "credit": 0, "description": line_purpose[0]},
            {"account_id": credit.id, "debit": 0, "credit": amount, "description": line_purpose[1]},
        ],
    )

    if reversal_date is not None:
        schedule_reference = f"ADJREV-{entry.id}"
        existing_schedule = db.query(CompanyOperatingRecord).filter(
            CompanyOperatingRecord.company_id == company_id,
            CompanyOperatingRecord.module == "accounting",
            CompanyOperatingRecord.record_type == "adjustment_reversal_schedule",
            CompanyOperatingRecord.reference == schedule_reference,
            CompanyOperatingRecord.is_archived.is_(False),
        ).first()
        if not existing_schedule:
            db.add(CompanyOperatingRecord(
                company_id=company_id,
                branch_id=branch_id,
                module="accounting",
                record_type="adjustment_reversal_schedule",
                reference=schedule_reference,
                title=f"Scheduled reversal for {entry.entry_number}",
                description=f"Prepare reversal after maker/checker posting: {description}",
                status="pending",
                created_by_user_id=user_id,
                amount=amount,
                currency="LSL",
                due_at=datetime.combine(reversal_date, datetime.min.time()),
                data={
                    "journal_entry_id": str(entry.id),
                    "reversal_date": reversal_date.isoformat(),
                    "adjustment_type": adjustment_type,
                    "source_reference_id": reference_id,
                },
                tags=["month_end", "scheduled_reversal"],
            ))
    return entry


def prepare_due_adjustment_reversal_drafts(
    db: Session,
    *,
    company_id,
    as_of: date,
    branch_id=None,
    user_id=None,
) -> dict:
    """Prepare due reversal journals as drafts; never auto-post them."""
    schedules = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.company_id == company_id,
        CompanyOperatingRecord.module == "accounting",
        CompanyOperatingRecord.record_type == "adjustment_reversal_schedule",
        CompanyOperatingRecord.status == "pending",
        CompanyOperatingRecord.is_archived.is_(False),
        CompanyOperatingRecord.due_at <= datetime.combine(as_of, datetime.max.time()),
    )
    if branch_id:
        schedules = schedules.filter(CompanyOperatingRecord.branch_id == branch_id)

    prepared = []
    waiting_for_source_post = []
    key, _ = scope_key(company_id)
    for schedule in schedules.order_by(CompanyOperatingRecord.due_at.asc()).all():
        data = dict(schedule.data or {})
        journal_id = data.get("journal_entry_id")
        if not journal_id:
            schedule.status = "invalid"
            continue
        original = entry_query(db, key).filter(JournalEntry.id == UUID(str(journal_id))).first()
        if not original:
            schedule.status = "invalid"
            continue
        if original.status != "posted":
            waiting_for_source_post.append(str(original.id))
            continue

        reversal_date = date.fromisoformat(str(data["reversal_date"]))
        reference = f"scheduled:{schedule.id}:{original.id}:{reversal_date.isoformat()}"
        existing = _journal_for_reference(db, key, "period_adjustment_reversal", reference)
        if existing:
            schedule.status = "prepared"
            prepared.append({
                "schedule_id": str(schedule.id),
                "journal_entry_id": str(existing.id),
                "entry_number": existing.entry_number,
                "existing": True,
            })
            continue

        reversal = create_entry(
            db,
            company_id=company_id,
            branch_id=original.branch_id,
            created_by_user_id=user_id,
            entry_date=reversal_date,
            description=f"Scheduled reversal of {original.entry_number}: {original.description}",
            reference_type="period_adjustment_reversal",
            reference_id=reference,
            status_value="draft",
            lines=[
                {
                    "account_id": line.account_id,
                    "debit": _money(line.credit),
                    "credit": _money(line.debit),
                    "description": f"Reverse {original.entry_number}",
                }
                for line in original.lines
            ],
        )
        schedule.status = "prepared"
        schedule.data = {
            **data,
            "reversal_journal_entry_id": str(reversal.id),
            "prepared_at": datetime.now(timezone.utc).isoformat(),
        }
        prepared.append({
            "schedule_id": str(schedule.id),
            "journal_entry_id": str(reversal.id),
            "entry_number": reversal.entry_number,
            "existing": False,
        })

    return {
        "as_of": as_of.isoformat(),
        "prepared_count": len(prepared),
        "waiting_for_source_post_count": len(waiting_for_source_post),
        "waiting_for_source_post_entry_ids": waiting_for_source_post,
        "prepared": prepared,
        "policy_note": "Scheduled reversals are prepared as drafts and still require a different finance user to post them.",
    }


def vat_control_reconciliation(
    db: Session,
    *,
    company_id,
    period_start: date,
    period_end: date,
    branch_id=None,
) -> dict:
    """Reconcile VAT control accounts using posted ledger entries only."""
    if period_end < period_start:
        raise HTTPException(status_code=422, detail="Period end must be on or after period start")
    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    input_vat = account_by_code(db, key, "1600")
    output_vat = account_by_code(db, key, "2200")

    def movements(account_id):
        q = db.query(
            func.coalesce(func.sum(JournalLine.debit), 0),
            func.coalesce(func.sum(JournalLine.credit), 0),
        ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
            JournalLine.account_id == account_id,
            JournalEntry.scope_key == key,
            JournalEntry.status == "posted",
            JournalEntry.entry_date.between(period_start, period_end),
        )
        if branch_id:
            q = q.filter(JournalEntry.branch_id == branch_id)
        debit, credit = q.first()
        return _money(debit), _money(credit)

    input_debit, input_credit = movements(input_vat.id)
    output_debit, output_credit = movements(output_vat.id)
    input_balance = _account_signed_balance(
        db, scope_key_value=key, account_code="1600", to_date=period_end, branch_id=branch_id
    )
    output_signed = _account_signed_balance(
        db, scope_key_value=key, account_code="2200", to_date=period_end, branch_id=branch_id
    )
    output_balance = _money(-output_signed)
    net = _money(output_balance - input_balance)
    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "input_vat_account": "1600",
        "output_vat_account": "2200",
        "period_input_vat_debits": float(input_debit),
        "period_input_vat_credits": float(input_credit),
        "period_output_vat_debits": float(output_debit),
        "period_output_vat_credits": float(output_credit),
        "closing_input_vat_receivable": float(input_balance),
        "closing_output_vat_payable": float(output_balance),
        "net_vat_payable": float(max(net, Decimal("0.00"))),
        "net_vat_receivable": float(max(-net, Decimal("0.00"))),
        "ledger_balanced": input_balance >= 0 and output_balance >= 0,
        "policy_note": "This is a ledger reconciliation control, not a Lesotho VAT return or statutory tax determination.",
    }


def create_financial_plan(
    db: Session,
    *,
    company_id,
    branch_id,
    name: str,
    plan_type: str,
    fiscal_start: date,
    fiscal_end: date,
    notes: str | None,
    lines: list[dict],
    user_id,
) -> CompanyOperatingRecord:
    """Create a versioned planning record that never alters posted accounting."""
    if plan_type not in {"budget", "forecast"}:
        raise HTTPException(status_code=422, detail="plan_type must be budget or forecast")
    if fiscal_end < fiscal_start:
        raise HTTPException(status_code=422, detail="Invalid financial plan period")

    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    normalised = []
    seen = set()
    total = Decimal("0.00")
    for raw in lines:
        code = str(raw["account_code"]).strip().upper()
        account = account_by_code(db, key, code)
        period = raw["period_start"]
        if period < fiscal_start or period > fiscal_end:
            raise HTTPException(status_code=422, detail="Plan line falls outside plan period")
        dedupe = (code, period.isoformat())
        if dedupe in seen:
            raise HTTPException(status_code=422, detail=f"Duplicate plan line for {code} {period.isoformat()}")
        seen.add(dedupe)
        amount = _money(raw["amount"])
        total += amount
        normalised.append({
            "account_code": code,
            "account_name": account.name,
            "account_type": account.account_type,
            "period_start": period.isoformat(),
            "amount": float(amount),
            "note": (raw.get("note") or "").strip() or None,
            "basis": "management_plan",
        })

    reference = f"PLAN-{plan_type.upper()}-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{str(uuid4())[:8].upper()}"
    record = CompanyOperatingRecord(
        company_id=company_id,
        branch_id=branch_id,
        module="accounting",
        record_type="financial_plan",
        reference=reference,
        title=name.strip(),
        description=(notes or "").strip() or None,
        status="draft",
        created_by_user_id=user_id,
        amount=_money(total),
        currency="LSL",
        data={
            "plan_type": plan_type,
            "fiscal_start": fiscal_start.isoformat(),
            "fiscal_end": fiscal_end.isoformat(),
            "version": 1,
            "lines": normalised,
            "approved_by_user_id": None,
            "approved_at": None,
            "source_plan_id": None,
        },
        tags=["financial_planning", plan_type],
    )
    db.add(record)
    db.flush()
    return record


def approve_financial_plan(
    db: Session,
    *,
    company_id,
    plan_id,
    user_id,
) -> CompanyOperatingRecord:
    plan = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.id == plan_id,
        CompanyOperatingRecord.company_id == company_id,
        CompanyOperatingRecord.module == "accounting",
        CompanyOperatingRecord.record_type == "financial_plan",
        CompanyOperatingRecord.is_archived.is_(False),
    ).with_for_update().first()
    if not plan:
        raise HTTPException(status_code=404, detail="Financial plan not found")
    if plan.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft financial plans can be approved")
    if plan.created_by_user_id == user_id:
        raise HTTPException(status_code=409, detail="Maker/checker control: plan creator cannot approve the plan")
    data = dict(plan.data or {})
    data["approved_by_user_id"] = str(user_id)
    data["approved_at"] = datetime.now(timezone.utc).isoformat()
    plan.data = data
    plan.status = "approved"
    db.add(plan)
    return plan


def financial_plan_payload(plan: CompanyOperatingRecord) -> dict:
    data = dict(plan.data or {})
    return {
        "id": str(plan.id),
        "reference": plan.reference,
        "name": plan.title,
        "description": plan.description,
        "status": plan.status,
        "branch_id": str(plan.branch_id) if plan.branch_id else None,
        "plan_type": data.get("plan_type"),
        "fiscal_start": data.get("fiscal_start"),
        "fiscal_end": data.get("fiscal_end"),
        "version": data.get("version", 1),
        "source_plan_id": data.get("source_plan_id"),
        "approved_by_user_id": data.get("approved_by_user_id"),
        "approved_at": data.get("approved_at"),
        "total_planned": float(_money(plan.amount)),
        "lines": data.get("lines", []),
    }


def financial_plan_variance(
    db: Session,
    *,
    company_id,
    plan: CompanyOperatingRecord,
    as_of: date,
    branch_id=None,
) -> dict:
    """Compare plan lines to posted ledger actuals using account normal balances."""
    data = dict(plan.data or {})
    fiscal_start = date.fromisoformat(data["fiscal_start"])
    fiscal_end = date.fromisoformat(data["fiscal_end"])
    effective_end = min(as_of, fiscal_end)
    if effective_end < fiscal_start:
        raise HTTPException(status_code=422, detail="as_of precedes financial plan")

    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    plan_map = {}
    account_meta = {}
    for line in data.get("lines", []):
        period = date.fromisoformat(line["period_start"])
        if period > effective_end:
            continue
        k = (line["account_code"], period.year, period.month)
        plan_map[k] = _money(line["amount"])
        account_meta[line["account_code"]] = {
            "name": line.get("account_name"),
            "account_type": line.get("account_type"),
        }

    actual_q = db.query(
        AccountingAccount.code,
        AccountingAccount.name,
        AccountingAccount.account_type,
        func.extract("year", JournalEntry.entry_date),
        func.extract("month", JournalEntry.entry_date),
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalLine, JournalLine.account_id == AccountingAccount.id).join(
        JournalEntry, JournalEntry.id == JournalLine.journal_entry_id
    ).filter(
        AccountingAccount.scope_key == key,
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date.between(fiscal_start, effective_end),
    )
    selected_branch = branch_id or plan.branch_id
    if selected_branch:
        actual_q = actual_q.filter(JournalEntry.branch_id == selected_branch)
    actual_rows = actual_q.group_by(
        AccountingAccount.code,
        AccountingAccount.name,
        AccountingAccount.account_type,
        func.extract("year", JournalEntry.entry_date),
        func.extract("month", JournalEntry.entry_date),
    ).all()

    actual_map = {}
    for code, name, account_type, year_value, month_value, debit, credit in actual_rows:
        raw = _money(Decimal(debit) - Decimal(credit))
        actual = -raw if account_type in {"liability", "equity", "revenue"} else raw
        actual_map[(code, int(year_value), int(month_value))] = _money(actual)
        account_meta[code] = {"name": name, "account_type": account_type}

    keys = sorted(set(plan_map) | set(actual_map), key=lambda x: (x[1], x[2], x[0]))
    rows = []
    planned_total = Decimal("0.00")
    actual_total = Decimal("0.00")
    for code, year_value, month_value in keys:
        planned = plan_map.get((code, year_value, month_value), Decimal("0.00"))
        actual = actual_map.get((code, year_value, month_value), Decimal("0.00"))
        variance = _money(actual - planned)
        meta = account_meta.get(code, {})
        account_type = meta.get("account_type") or "unknown"
        favorable = None
        if account_type == "revenue":
            favorable = variance >= 0
        elif account_type == "expense":
            favorable = variance <= 0
        pct = None if planned == 0 else float((variance / abs(planned) * Decimal("100")).quantize(Decimal("0.01")))
        narrative = (
            f"{meta.get('name') or code} actual {float(actual):,.2f} versus plan {float(planned):,.2f}; "
            f"variance {float(abs(variance)):,.2f} {'above' if variance > 0 else 'below' if variance < 0 else 'on'} plan."
        )
        rows.append({
            "account_code": code,
            "account_name": meta.get("name") or code,
            "account_type": account_type,
            "period": f"{year_value:04d}-{month_value:02d}",
            "planned": float(planned),
            "actual": float(actual),
            "variance": float(variance),
            "variance_percent": pct,
            "favorability": "favorable" if favorable is True else "unfavorable" if favorable is False else "neutral",
            "explanation": narrative,
            "cause_inferred": False,
        })
        planned_total += planned
        actual_total += actual

    ranked = sorted(rows, key=lambda row: abs(row["variance"]), reverse=True)
    return {
        "plan": financial_plan_payload(plan),
        "as_of": effective_end.isoformat(),
        "planned_total": float(_money(planned_total)),
        "actual_total": float(_money(actual_total)),
        "net_variance": float(_money(actual_total - planned_total)),
        "rows": rows,
        "top_variances": ranked[:10],
        "intelligence_policy": (
            "Variance explanations describe ledger-observed amount differences only. "
            "LoanHub does not infer business causes without supporting evidence."
        ),
    }


def create_rolling_forecast_from_plan(
    db: Session,
    *,
    company_id,
    source_plan: CompanyOperatingRecord,
    cutoff_date: date,
    name: str,
    user_id,
) -> CompanyOperatingRecord:
    """Create a draft rolling forecast: actual months to cutoff + remaining planned months."""
    source = dict(source_plan.data or {})
    fiscal_start = date.fromisoformat(source["fiscal_start"])
    fiscal_end = date.fromisoformat(source["fiscal_end"])
    if cutoff_date < fiscal_start or cutoff_date > fiscal_end:
        raise HTTPException(status_code=422, detail="Forecast cutoff must fall within source plan period")

    variance = financial_plan_variance(
        db,
        company_id=company_id,
        plan=source_plan,
        as_of=cutoff_date,
        branch_id=source_plan.branch_id,
    )
    actual_index = {
        (row["account_code"], row["period"]): _money(row["actual"])
        for row in variance["rows"]
    }
    forecast_lines = []
    for line in source.get("lines", []):
        period = date.fromisoformat(line["period_start"])
        month_key = f"{period.year:04d}-{period.month:02d}"
        if period.year < cutoff_date.year or (period.year == cutoff_date.year and period.month <= cutoff_date.month):
            amount = actual_index.get((line["account_code"], month_key), Decimal("0.00"))
            basis = "actual_to_cutoff"
        else:
            amount = _money(line["amount"])
            basis = "source_plan"
        forecast_lines.append({
            **line,
            "amount": float(amount),
            "basis": basis,
        })

    reference = f"PLAN-FORECAST-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{str(uuid4())[:8].upper()}"
    record = CompanyOperatingRecord(
        company_id=company_id,
        branch_id=source_plan.branch_id,
        module="accounting",
        record_type="financial_plan",
        reference=reference,
        title=name.strip(),
        description=f"Rolling forecast based on {source_plan.reference} through {cutoff_date.isoformat()}",
        status="draft",
        created_by_user_id=user_id,
        amount=_money(sum((_money(line["amount"]) for line in forecast_lines), Decimal("0.00"))),
        currency="LSL",
        data={
            "plan_type": "forecast",
            "fiscal_start": source["fiscal_start"],
            "fiscal_end": source["fiscal_end"],
            "version": int(source.get("version", 1)) + 1,
            "lines": forecast_lines,
            "approved_by_user_id": None,
            "approved_at": None,
            "source_plan_id": str(source_plan.id),
            "cutoff_date": cutoff_date.isoformat(),
        },
        tags=["financial_planning", "forecast", "rolling"],
    )
    db.add(record)
    db.flush()
    return record


def create_treasury_commitment(
    db: Session,
    *,
    company_id,
    branch_id,
    title: str,
    category: str,
    due_date: date,
    amount,
    description: str | None,
    user_id,
) -> CompanyOperatingRecord:
    amount = _money(amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Treasury commitment amount must be greater than zero")
    reference = f"TC-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{str(uuid4())[:8].upper()}"
    record = CompanyOperatingRecord(
        company_id=company_id,
        branch_id=branch_id,
        module="accounting",
        record_type="treasury_commitment",
        reference=reference,
        title=title.strip(),
        description=(description or "").strip() or None,
        status="draft",
        created_by_user_id=user_id,
        amount=amount,
        currency="LSL",
        due_at=datetime.combine(due_date, datetime.min.time()),
        data={
            "category": category,
            "due_date": due_date.isoformat(),
            "approved_by_user_id": None,
            "approved_at": None,
        },
        tags=["treasury", "forecast", category],
    )
    db.add(record)
    db.flush()
    return record


def approve_treasury_commitment(
    db: Session,
    *,
    company_id,
    commitment_id,
    user_id,
    branch_id=None,
) -> CompanyOperatingRecord:
    row = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.id == commitment_id,
        CompanyOperatingRecord.company_id == company_id,
        CompanyOperatingRecord.module == "accounting",
        CompanyOperatingRecord.record_type == "treasury_commitment",
        CompanyOperatingRecord.is_archived.is_(False),
    ).with_for_update().first()
    if not row:
        raise HTTPException(status_code=404, detail="Treasury commitment not found")
    if branch_id and row.branch_id != branch_id:
        raise HTTPException(status_code=403, detail="Treasury commitment is outside your branch scope")
    if row.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft treasury commitments can be approved")
    if row.created_by_user_id == user_id:
        raise HTTPException(status_code=409, detail="Maker/checker control: commitment creator cannot approve it")
    data = dict(row.data or {})
    data["approved_by_user_id"] = str(user_id)
    data["approved_at"] = datetime.now(timezone.utc).isoformat()
    row.data = data
    row.status = "approved"
    db.add(row)
    return row


def treasury_commitment_payload(row: CompanyOperatingRecord) -> dict:
    data = dict(row.data or {})
    return {
        "id": str(row.id),
        "reference": row.reference,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "branch_id": str(row.branch_id) if row.branch_id else None,
        "category": data.get("category"),
        "due_date": data.get("due_date"),
        "amount": float(_money(row.amount)),
        "approved_by_user_id": data.get("approved_by_user_id"),
        "approved_at": data.get("approved_at"),
    }


def _forecast_opening_liquidity(
    db: Session,
    *,
    company_id,
    before_date: date,
    branch_id=None,
) -> dict:
    key, _ = scope_key(company_id)
    cash = _account_signed_balance(db, scope_key_value=key, account_code="1000", to_date=before_date, branch_id=branch_id)
    bank = _account_signed_balance(db, scope_key_value=key, account_code="1010", to_date=before_date, branch_id=branch_id)
    clearing = _account_signed_balance(db, scope_key_value=key, account_code="1020", to_date=before_date, branch_id=branch_id)
    return {
        "cash": _money(cash),
        "bank": _money(bank),
        "electronic_clearing": _money(clearing),
        "available_cash": _money(cash + bank),
        "gross_liquid_funds": _money(cash + bank + clearing),
    }


def treasury_cash_forecast(
    db: Session,
    *,
    company_id,
    from_date: date,
    to_date: date,
    branch_id=None,
    minimum_cash=Decimal("0"),
    collection_rate=Decimal("1"),
    obligation_rate=Decimal("1"),
    unexpected_outflow=Decimal("0"),
) -> dict:
    """Forward cash forecast from ledger liquidity, loan schedules and approved commitments."""
    if to_date < from_date:
        raise HTTPException(status_code=422, detail="Invalid treasury forecast period")
    if (to_date - from_date).days > 366:
        raise HTTPException(status_code=422, detail="Treasury forecast horizon cannot exceed 366 days")

    minimum_cash = _money(minimum_cash)
    collection_rate = Decimal(str(collection_rate))
    obligation_rate = Decimal(str(obligation_rate))
    unexpected_outflow = _money(unexpected_outflow)
    opening = _forecast_opening_liquidity(
        db,
        company_id=company_id,
        before_date=from_date - timedelta(days=1),
        branch_id=branch_id,
    )

    installments = db.query(RepaymentInstallment, ClientCompanyLoan).join(
        ClientCompanyLoan, ClientCompanyLoan.id == RepaymentInstallment.loan_id
    ).filter(
        ClientCompanyLoan.company_id == company_id,
        RepaymentInstallment.is_superseded.is_(False),
        RepaymentInstallment.due_date.between(from_date, to_date),
        RepaymentInstallment.status.notin_([InstallmentStatus.PAID, InstallmentStatus.WAIVED]),
    )
    if branch_id:
        installments = installments.filter(ClientCompanyLoan.branch_id == branch_id)

    collection_by_day: dict[date, Decimal] = {}
    collection_details = []
    for installment, loan in installments.all():
        remaining = max(_money(installment.total_due) - _money(installment.paid_amount), Decimal("0.00"))
        expected = _money(remaining * collection_rate)
        if expected <= 0:
            continue
        collection_by_day[installment.due_date] = _money(collection_by_day.get(installment.due_date, Decimal("0")) + expected)
        collection_details.append({
            "installment_id": str(installment.id),
            "loan_id": str(loan.id),
            "folio_number": loan.folio_number,
            "due_date": installment.due_date.isoformat(),
            "scheduled_remaining": float(remaining),
            "scenario_expected_collection": float(expected),
        })

    commitments = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.company_id == company_id,
        CompanyOperatingRecord.module == "accounting",
        CompanyOperatingRecord.record_type == "treasury_commitment",
        CompanyOperatingRecord.status == "approved",
        CompanyOperatingRecord.is_archived.is_(False),
        CompanyOperatingRecord.due_at >= datetime.combine(from_date, datetime.min.time()),
        CompanyOperatingRecord.due_at <= datetime.combine(to_date, datetime.max.time()),
    )
    if branch_id:
        commitments = commitments.filter(CompanyOperatingRecord.branch_id == branch_id)

    obligation_by_day: dict[date, Decimal] = {}
    commitment_details = []
    for row in commitments.all():
        due = date.fromisoformat(str((row.data or {}).get("due_date") or row.due_at.date().isoformat()))
        scenario_amount = _money(_money(row.amount) * obligation_rate)
        obligation_by_day[due] = _money(obligation_by_day.get(due, Decimal("0")) + scenario_amount)
        commitment_details.append({
            **treasury_commitment_payload(row),
            "scenario_amount": float(scenario_amount),
        })

    days = []
    running = _money(opening["available_cash"] - unexpected_outflow)
    breaches = []
    current = from_date
    while current <= to_date:
        inflow = collection_by_day.get(current, Decimal("0.00"))
        outflow = obligation_by_day.get(current, Decimal("0.00"))
        opening_balance = running
        running = _money(running + inflow - outflow)
        breach = running < minimum_cash
        if breach:
            breaches.append({
                "date": current.isoformat(),
                "projected_closing_cash": float(running),
                "minimum_cash": float(minimum_cash),
                "shortfall": float(_money(minimum_cash - running)),
            })
        days.append({
            "date": current.isoformat(),
            "opening_cash": float(opening_balance),
            "expected_collections": float(inflow),
            "approved_obligations": float(outflow),
            "projected_closing_cash": float(running),
            "minimum_cash_breach": breach,
        })
        current += timedelta(days=1)

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "opening_liquidity": {key: float(value) for key, value in opening.items()},
        "scenario": {
            "collection_rate": float(collection_rate),
            "obligation_rate": float(obligation_rate),
            "unexpected_outflow": float(unexpected_outflow),
            "minimum_cash": float(minimum_cash),
        },
        "total_expected_collections": float(_money(sum(collection_by_day.values(), Decimal("0.00")))),
        "total_approved_obligations": float(_money(sum(obligation_by_day.values(), Decimal("0.00")))),
        "projected_closing_cash": float(running),
        "minimum_projected_cash": min((row["projected_closing_cash"] for row in days), default=float(opening["available_cash"])),
        "breach_count": len(breaches),
        "breaches": breaches,
        "daily_forecast": days,
        "collection_details": collection_details,
        "commitments": commitment_details,
        "policy_note": (
            "This is a management liquidity forecast. It uses posted opening cash/bank balances, "
            "scheduled loan installments and approved treasury commitments. It does not post journals "
            "or guarantee that scheduled collections will be received."
        ),
    }


def treasury_stress_test(
    db: Session,
    *,
    company_id,
    from_date: date,
    to_date: date,
    branch_id=None,
    minimum_cash=Decimal("0"),
) -> dict:
    scenarios = [
        ("baseline", Decimal("1.00"), Decimal("1.00"), Decimal("0")),
        ("collections_down_20pct", Decimal("0.80"), Decimal("1.00"), Decimal("0")),
        ("collections_down_35pct", Decimal("0.65"), Decimal("1.00"), Decimal("0")),
        ("obligations_up_15pct", Decimal("1.00"), Decimal("1.15"), Decimal("0")),
        ("combined_stress", Decimal("0.70"), Decimal("1.15"), Decimal("0")),
    ]
    results = []
    for name, collection_rate, obligation_rate, shock in scenarios:
        forecast = treasury_cash_forecast(
            db,
            company_id=company_id,
            from_date=from_date,
            to_date=to_date,
            branch_id=branch_id,
            minimum_cash=minimum_cash,
            collection_rate=collection_rate,
            obligation_rate=obligation_rate,
            unexpected_outflow=shock,
        )
        results.append({
            "scenario": name,
            "collection_rate": float(collection_rate),
            "obligation_rate": float(obligation_rate),
            "projected_closing_cash": forecast["projected_closing_cash"],
            "minimum_projected_cash": forecast["minimum_projected_cash"],
            "breach_count": forecast["breach_count"],
            "first_breach": forecast["breaches"][0] if forecast["breaches"] else None,
        })
    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "minimum_cash": float(_money(minimum_cash)),
        "scenarios": results,
        "policy_note": "Stress scenarios change assumptions only; they never change loans, treasury entries, budgets or accounting journals.",
    }

def depreciate_all_fixed_assets_for_period(
    db: Session,
    *,
    company_id,
    period_start: date,
    period_end: date,
    branch_id=None,
    user_id=None,
) -> dict:
    assets = fixed_asset_query(db, company_id=company_id, branch_id=branch_id).filter(
        CompanyOperatingRecord.status == "active"
    ).all()
    posted = []
    skipped = []
    total = Decimal("0.00")
    for asset in assets:
        data = _asset_data(asset)
        if date.fromisoformat(data["acquisition_date"]) > period_end:
            skipped.append(str(asset.id))
            continue
        amount = calculate_fixed_asset_depreciation(
            asset, period_start=period_start, period_end=period_end
        )
        if amount <= 0:
            skipped.append(str(asset.id))
            continue
        entry = post_fixed_asset_depreciation(
            db,
            asset=asset,
            period_start=period_start,
            period_end=period_end,
            user_id=user_id,
        )
        if entry:
            posted.append({"asset_id": str(asset.id), "journal_entry_id": str(entry.id), "amount": float(amount)})
            total += amount
    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "posted": posted,
        "skipped_asset_ids": skipped,
        "total_depreciation": float(_money(total)),
    }


def reverse_period_adjustment(
    db: Session,
    *,
    company_id,
    journal_entry_id,
    reversal_date: date,
    description: str,
    user_id,
) -> JournalEntry:
    key, _ = scope_key(company_id)
    original = entry_query(db, key).filter(JournalEntry.id == journal_entry_id).first()
    if not original:
        raise HTTPException(status_code=404, detail="Period adjustment journal not found")
    if original.status != "posted":
        raise HTTPException(status_code=409, detail="Only posted period adjustments can be reversed")
    if original.reference_type not in {"accrual_adjustment", "prepayment_adjustment", "accrued_income_adjustment"}:
        raise HTTPException(
            status_code=422,
            detail="Only accrual, prepayment and accrued-income adjustments can use the period reversal workflow",
        )
    if reversal_date <= original.entry_date:
        raise HTTPException(status_code=422, detail="Reversal date must be after the original adjustment date")

    reversal_reference = f"{original.id}:{reversal_date.isoformat()}"
    existing = _journal_for_reference(db, key, "period_adjustment_reversal", reversal_reference)
    if existing:
        return existing

    return create_entry(
        db,
        company_id=company_id,
        branch_id=original.branch_id,
        created_by_user_id=user_id,
        entry_date=reversal_date,
        description=description,
        reference_type="period_adjustment_reversal",
        reference_id=reversal_reference,
        status_value="posted",
        lines=[
            {
                "account_id": line.account_id,
                "debit": _money(line.credit),
                "credit": _money(line.debit),
                "description": f"Reverse {original.entry_number}",
            }
            for line in original.lines
        ],
    )


def transaction_accounting_coverage(
    db: Session,
    *,
    company_id,
    from_date: date,
    to_date: date,
    branch_id=None,
) -> dict:
    """Audit operational money sources against their accounting journals."""
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")

    from database.models.finance import TransactionChargeLedgerEntry
    from database.models.platform_credit_bureau import (
        PlatformCreditBureauInvoice,
        PlatformCreditBureauTransaction,
    )
    from database.models.platform_cdas import PlatformCdasInvoice, PlatformCdasTransaction
    from database.models.treasury import TreasuryEntry

    key, _ = scope_key(company_id)
    platform_key, _ = scope_key(None)

    def journal_exists(reference_type: str, reference_id: str, *, journal_scope_key: str = key) -> bool:
        return db.query(JournalEntry.id).filter(
            JournalEntry.scope_key == journal_scope_key,
            JournalEntry.reference_type == reference_type,
            JournalEntry.reference_id == str(reference_id),
            JournalEntry.status == "posted",
        ).first() is not None

    payments = db.query(PaymentTransaction).filter(
        PaymentTransaction.company_id == company_id,
        PaymentTransaction.status == PaymentStatus.SUCCEEDED,
        func.date(func.coalesce(PaymentTransaction.completed_at, PaymentTransaction.created_at)).between(from_date, to_date),
    )
    if branch_id:
        payments = payments.outerjoin(
            ClientCompanyLoan, ClientCompanyLoan.id == PaymentTransaction.loan_id
        ).filter(
            (ClientCompanyLoan.branch_id == branch_id) | (PaymentTransaction.loan_id.is_(None))
        )
    payment_rows = payments.all()
    missing_payments = [
        str(row.id) for row in payment_rows
        if not journal_exists("payment_transaction", str(row.id))
    ]
    missing_platform_payment_journals = [
        str(row.id) for row in payment_rows
        if row.purpose in PLATFORM_PAYMENT_RULES
        and not journal_exists(
            "payment_transaction", str(row.id), journal_scope_key=platform_key
        )
    ]

    charges = db.query(TransactionChargeLedgerEntry).filter(
        TransactionChargeLedgerEntry.company_id == company_id,
        func.date(TransactionChargeLedgerEntry.accrued_at).between(from_date, to_date),
        TransactionChargeLedgerEntry.status.in_(["accrued", "claimed", "settled"]),
    ).all()
    missing_transaction_charges = [
        str(row.id) for row in charges
        if _money(row.charge_amount) > 0
        and not journal_exists("platform_transaction_charge_accrual", str(row.id))
    ]
    missing_platform_transaction_charges = [
        str(row.id) for row in charges
        if _money(row.charge_amount) > 0
        and not journal_exists(
            "platform_transaction_charge_accrual",
            str(row.id),
            journal_scope_key=platform_key,
        )
    ]

    bureau = db.query(PlatformCreditBureauTransaction).filter(
        PlatformCreditBureauTransaction.company_id == company_id,
        func.date(PlatformCreditBureauTransaction.accrued_at).between(from_date, to_date),
        PlatformCreditBureauTransaction.status.in_(["accrued", "invoiced", "settled"]),
        PlatformCreditBureauTransaction.amount > 0,
    ).all()
    missing_credit_bureau = [
        str(row.id) for row in bureau
        if not journal_exists("credit_bureau_transaction_accrual", str(row.id))
    ]
    missing_platform_credit_bureau = [
        str(row.id) for row in bureau
        if not journal_exists(
            "credit_bureau_transaction_accrual",
            str(row.id),
            journal_scope_key=platform_key,
        )
    ]

    cdas = db.query(PlatformCdasTransaction).filter(
        PlatformCdasTransaction.company_id == company_id,
        func.date(PlatformCdasTransaction.accrued_at).between(from_date, to_date),
        PlatformCdasTransaction.status.in_(["accrued", "invoiced", "settled"]),
        PlatformCdasTransaction.amount > 0,
    ).all()

    bureau_invoices = db.query(PlatformCreditBureauInvoice).filter(
        PlatformCreditBureauInvoice.company_id == company_id,
        PlatformCreditBureauInvoice.status == "paid",
        PlatformCreditBureauInvoice.amount_due > 0,
        func.date(PlatformCreditBureauInvoice.paid_at).between(from_date, to_date),
    ).all()
    missing_bureau_invoice_payments = [
        str(row.id) for row in bureau_invoices
        if not journal_exists("credit_bureau_invoice_payment", str(row.id))
    ]
    missing_platform_bureau_invoice_receipts = [
        str(row.id) for row in bureau_invoices
        if not journal_exists(
            "credit_bureau_invoice_payment",
            str(row.id),
            journal_scope_key=platform_key,
        )
    ]

    cdas_invoices = db.query(PlatformCdasInvoice).filter(
        PlatformCdasInvoice.company_id == company_id,
        PlatformCdasInvoice.status == "paid",
        PlatformCdasInvoice.amount_due > 0,
        func.date(PlatformCdasInvoice.paid_at).between(from_date, to_date),
    ).all()
    missing_cdas_invoice_payments = [
        str(row.id) for row in cdas_invoices
        if not journal_exists("cdas_invoice_payment", str(row.id))
    ]
    missing_platform_cdas_invoice_receipts = [
        str(row.id) for row in cdas_invoices
        if not journal_exists(
            "cdas_invoice_payment",
            str(row.id),
            journal_scope_key=platform_key,
        )
    ]
    missing_cdas = [
        str(row.id) for row in cdas
        if not journal_exists("cdas_transaction_accrual", str(row.id))
    ]
    missing_platform_cdas = [
        str(row.id) for row in cdas
        if not journal_exists(
            "cdas_transaction_accrual",
            str(row.id),
            journal_scope_key=platform_key,
        )
    ]

    treasury = db.query(TreasuryEntry).filter(
        TreasuryEntry.company_id == company_id,
        TreasuryEntry.payment_transaction_id.is_(None),
        TreasuryEntry.is_voided.is_(False),
        TreasuryEntry.approval_status.in_([
            TreasuryEntryApprovalStatus.POSTED,
            TreasuryEntryApprovalStatus.APPROVED,
        ]),
        func.date(TreasuryEntry.occurred_at).between(from_date, to_date),
    )
    if branch_id:
        treasury = treasury.filter(TreasuryEntry.branch_id == branch_id)
    treasury_rows = treasury.all()
    missing_treasury = [
        str(row.id) for row in treasury_rows
        if row.entry_type != TreasuryEntryType.BRANCH_FUNDING
        and not journal_exists("treasury_entry", str(row.id))
    ]

    missing = {
        "successful_payments": missing_payments,
        "platform_payment_journals": missing_platform_payment_journals,
        "platform_transaction_charges": missing_transaction_charges,
        "platform_transaction_charge_revenue": missing_platform_transaction_charges,
        "credit_bureau_usage": missing_credit_bureau,
        "credit_bureau_platform_revenue": missing_platform_credit_bureau,
        "cdas_usage": missing_cdas,
        "cdas_platform_revenue": missing_platform_cdas,
        "credit_bureau_invoice_payments": missing_bureau_invoice_payments,
        "credit_bureau_platform_receipts": missing_platform_bureau_invoice_receipts,
        "cdas_invoice_payments": missing_cdas_invoice_payments,
        "cdas_platform_receipts": missing_platform_cdas_invoice_receipts,
        "manual_treasury_entries": missing_treasury,
    }
    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "complete": all(not values for values in missing.values()),
        "source_counts": {
            "successful_payments": len(payment_rows),
            "platform_transaction_charges": len(charges),
            "credit_bureau_usage": len(bureau),
            "cdas_usage": len(cdas),
            "credit_bureau_invoice_payments": len(bureau_invoices),
            "cdas_invoice_payments": len(cdas_invoices),
            "manual_treasury_entries": len(treasury_rows),
        },
        "missing_counts": {name: len(values) for name, values in missing.items()},
        "missing_source_ids": missing,
    }


EXPECTED_REFERENCE_ACCOUNTS = {
    "fixed_asset_acquisition": {"1500"},
    "depreciation_adjustment": {"5400", "1510"},
    "accrual_adjustment": {"2100"},
    "prepayment_adjustment": {"1400"},
    "accrued_income_adjustment": {"1220"},
    "loan_write_off": {"1100"},
}


def accounting_error_diagnostics(
    db: Session,
    *,
    company_id,
    from_date: date,
    to_date: date,
    branch_id=None,
) -> dict:
    """Chapters 23-27: detect control failures, including errors a trial balance can miss.

    A balanced trial balance proves arithmetic equality, not correctness of account
    choice or completeness.  This diagnostic therefore combines double-entry
    integrity, control-account reconciliation, source completeness, suspense, bank
    reconciliation exceptions and conservative errors-of-principle heuristics.
    """
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")

    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)

    journals = db.query(JournalEntry).options(
        joinedload(JournalEntry.lines).joinedload(JournalLine.account)
    ).filter(
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date.between(from_date, to_date),
    )
    if branch_id:
        journals = journals.filter(JournalEntry.branch_id == branch_id)
    journal_rows = journals.all()

    malformed = []
    principle_risks = []
    internal_reference_only = []
    total_debit = Decimal("0.00")
    total_credit = Decimal("0.00")

    for entry in journal_rows:
        debit = _money(sum((_money(line.debit) for line in entry.lines), Decimal("0.00")))
        credit = _money(sum((_money(line.credit) for line in entry.lines), Decimal("0.00")))
        total_debit += debit
        total_credit += credit
        account_ids = {line.account_id for line in entry.lines}
        if (
            len(entry.lines) < 2
            or len(account_ids) < 2
            or debit <= 0
            or debit != credit
            or _money(entry.total_debit) != debit
            or _money(entry.total_credit) != credit
        ):
            malformed.append({
                "entry_id": str(entry.id),
                "entry_number": entry.entry_number,
                "reason": "persisted journal fails double-entry/header integrity",
            })

        codes = {line.account.code for line in entry.lines if line.account is not None}
        expected = EXPECTED_REFERENCE_ACCOUNTS.get(entry.reference_type or "")
        if expected and not expected.issubset(codes):
            principle_risks.append({
                "entry_id": str(entry.id),
                "entry_number": entry.entry_number,
                "reference_type": entry.reference_type,
                "expected_account_codes": sorted(expected),
                "actual_account_codes": sorted(codes),
                "error_class": "possible_error_of_principle_or_commission",
            })

        if not entry.reference_type or not entry.reference_id:
            internal_reference_only.append(str(entry.id))

    total_debit = _money(total_debit)
    total_credit = _money(total_credit)
    trial_difference = _money(total_debit - total_credit)

    suspense_account = account_by_code(db, key, "2990")
    suspense_q = db.query(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
        JournalLine.account_id == suspense_account.id,
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date <= to_date,
    )
    if branch_id:
        suspense_q = suspense_q.filter(JournalEntry.branch_id == branch_id)
    suspense_debit, suspense_credit = suspense_q.first()
    suspense_balance = _money(Decimal(suspense_debit) - Decimal(suspense_credit))

    receivables_control = loan_receivables_control_reconciliation(
        db, company_id=company_id, as_of=to_date, branch_id=branch_id
    )
    coverage = transaction_accounting_coverage(
        db,
        company_id=company_id,
        from_date=from_date,
        to_date=to_date,
        branch_id=branch_id,
    )

    reconciliation_q = db.query(ReconciliationLine).join(
        ReconciliationBatch, ReconciliationBatch.id == ReconciliationLine.batch_id
    ).filter(
        ReconciliationBatch.company_id == company_id,
        ReconciliationBatch.period_end >= from_date,
        ReconciliationBatch.period_start <= to_date,
        ReconciliationLine.status.in_([
            "unmatched", "shortage", "excess", "missing_source", "adjustment_required"
        ]),
    )
    if branch_id:
        reconciliation_q = reconciliation_q.filter(
            ReconciliationBatch.branch_id == branch_id
        )
    unresolved_reconciliation = reconciliation_q.all()

    controls = {
        "trial_balance_arithmetically_balanced": trial_difference == 0,
        "persisted_journals_valid": len(malformed) == 0,
        "suspense_cleared": suspense_balance == 0,
        "loan_receivables_control_balanced": bool(receivables_control["balanced"]),
        "operational_sources_fully_accounted": bool(coverage["complete"]),
        "reconciliation_exceptions_cleared": len(unresolved_reconciliation) == 0,
        "no_detected_principle_risks": len(principle_risks) == 0,
    }

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "controls": controls,
        "healthy": all(controls.values()),
        "trial_balance": {
            "total_debit": float(total_debit),
            "total_credit": float(total_credit),
            "difference": float(trial_difference),
        },
        "suspense_balance": float(suspense_balance),
        "malformed_journals": malformed,
        "possible_errors_not_revealed_by_trial_balance": principle_risks,
        "internal_reference_only_entry_ids": internal_reference_only,
        "unresolved_reconciliation_count": len(unresolved_reconciliation),
        "unresolved_reconciliation_line_ids": [
            str(line.id) for line in unresolved_reconciliation
        ],
        "loan_receivables_control": receivables_control,
        "transaction_accounting_coverage": coverage,
        "error_classes_checked": [
            "arithmetic_or_one_sided_error",
            "possible_error_of_principle",
            "possible_error_of_commission",
            "omission_via_source_coverage",
            "suspense_difference",
            "control_account_difference",
            "bank_or_external_reconciliation_difference",
        ],
        "note": (
            "A zero trial-balance difference does not prove that postings are correct; "
            "errors of principle, commission, original entry and compensating errors can still balance."
        ),
    }


def incomplete_records_control(
    db: Session,
    *,
    company_id,
    from_date: date,
    to_date: date,
    branch_id=None,
) -> dict:
    """Modern Chapter 27 completeness control for a computerised LoanHub ledger.

    The book's single-entry reconstruction techniques are intended for incomplete
    manual records. LoanHub instead identifies whether operational source records
    can be reconstructed into a complete double-entry population and lists the
    missing evidence explicitly.
    """
    diagnostics = accounting_error_diagnostics(
        db,
        company_id=company_id,
        from_date=from_date,
        to_date=to_date,
        branch_id=branch_id,
    )
    coverage = diagnostics["transaction_accounting_coverage"]
    reconstruction_ready = (
        coverage["complete"]
        and diagnostics["controls"]["persisted_journals_valid"]
        and diagnostics["controls"]["loan_receivables_control_balanced"]
        and diagnostics["controls"]["reconciliation_exceptions_cleared"]
    )
    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "records_complete": reconstruction_ready,
        "source_counts": coverage["source_counts"],
        "missing_counts": coverage["missing_counts"],
        "missing_source_ids": coverage["missing_source_ids"],
        "unresolved_reconciliation_count": diagnostics["unresolved_reconciliation_count"],
        "loan_receivables_control_variance": diagnostics["loan_receivables_control"]["variance"],
        "malformed_journal_count": len(diagnostics["malformed_journals"]),
        "principle_risk_count": len(diagnostics["possible_errors_not_revealed_by_trial_balance"]),
        "method": "operational-source-to-double-entry reconstruction",
        "note": (
            "This is LoanHub's computerised equivalent of the completeness problem in "
            "Chapter 27; it does not estimate profit from single-entry statements of affairs."
        ),
    }


def _written_off_recovery_balance(db: Session, *, company_id, loan_id) -> Decimal:
    """Net posted recovery income for one written-off loan, including reversals."""
    key, _ = scope_key(company_id)
    recovery_income = account_by_code(db, key, "4300")
    payment_ids = [
        str(row[0])
        for row in db.query(PaymentTransaction.id).filter(
            PaymentTransaction.company_id == company_id,
            PaymentTransaction.loan_id == loan_id,
        ).all()
    ]
    conditions = [
        and_condition
        for and_condition in [
            JournalEntry.reference_id.like(f"{loan_id}:%"),
            JournalEntry.reference_id.like(f"reversal:written_off_loan_recovery:{loan_id}:%"),
        ]
    ]
    if payment_ids:
        conditions.extend([
            JournalEntry.reference_id.in_(payment_ids),
            JournalEntry.reference_id.in_([f"reversal:payment_transaction:{pid}" for pid in payment_ids]),
        ])
    value = (
        db.query(func.coalesce(func.sum(JournalLine.credit - JournalLine.debit), 0))
        .join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id)
        .filter(
            JournalLine.account_id == recovery_income.id,
            JournalEntry.scope_key == key,
            JournalEntry.status == "posted",
            or_(*conditions),
        )
        .scalar()
        or 0
    )
    return max(_money(value), Decimal("0.00"))


def record_written_off_loan_recovery(
    db: Session,
    *,
    company_id,
    loan_id,
    amount,
    recovery_date: date,
    payment_method: str,
    proof_reference: str | None,
    description: str,
    user_id,
    reference_type: str = "written_off_loan_recovery",
    reference_id: str | None = None,
) -> JournalEntry:
    """Recognise cash recovered after a loan has already been written off.

    Recovery does not recreate the old receivable. It recognises income when
    value is recovered, while the operational loan and collection history stay
    intact for audit.
    """
    loan = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == loan_id,
        ClientCompanyLoan.company_id == company_id,
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    case = db.query(CollectionCase).filter(
        CollectionCase.company_id == company_id,
        CollectionCase.loan_id == loan_id,
    ).with_for_update().first()
    if not case or not case.write_off_at:
        raise HTTPException(status_code=409, detail="Loan has not been written off operationally")

    key, _ = scope_key(company_id)
    writeoff = _journal_for_reference(db, key, "loan_write_off", str(loan_id))
    if not writeoff:
        raise HTTPException(status_code=409, detail="Accounting write-off journal does not exist")

    method = payment_method.strip().lower()
    settlement_code = {
        "cash": "1000",
        "bank": "1010",
        "electronic": "1020",
    }.get(method)
    if not settlement_code:
        raise HTTPException(status_code=422, detail="Unsupported recovery payment method")
    if method != "cash" and not (proof_reference or "").strip():
        raise HTTPException(status_code=422, detail="Non-cash recoveries require proof_reference")

    amount = _money(amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Recovery amount must be greater than zero")

    written_off_principal = _money(writeoff.total_credit)
    recovered_to_date = _written_off_recovery_balance(
        db,
        company_id=company_id,
        loan_id=loan_id,
    )
    if recovered_to_date + amount > written_off_principal:
        raise HTTPException(
            status_code=409,
            detail="Recovery exceeds the principal amount derecognised by the write-off journal",
        )

    reference_id = reference_id or f"{loan_id}:{recovery_date.isoformat()}:{proof_reference or method}:{amount}"
    existing = _journal_for_reference(db, key, reference_type, reference_id)
    if existing:
        return existing

    entry = post_codes(
        db,
        company_id=company_id,
        branch_id=loan.branch_id,
        debit_code=settlement_code,
        credit_code="4300",
        amount=amount,
        description=description,
        reference_type=reference_type,
        reference_id=reference_id,
        user_id=user_id,
        entry_date=recovery_date,
    )
    case.recovered_amount = _money(recovered_to_date + amount)
    db.add(case)
    return entry


def record_electronic_clearing_settlement(
    db: Session,
    *,
    company_id,
    branch_id,
    settlement_date: date,
    amount,
    direction: str,
    provider_reference: str,
    proof_reference: str,
    notes: str | None,
    user_id,
) -> dict:
    """Move verified gateway clearing balances between account 1020 and bank 1010."""
    amount = _money(amount)
    if amount <= 0:
        raise HTTPException(status_code=422, detail="Settlement amount must be greater than zero")
    if direction not in {"provider_to_bank", "bank_to_provider"}:
        raise HTTPException(status_code=422, detail="Unsupported clearing settlement direction")
    if not provider_reference.strip() or not proof_reference.strip():
        raise HTTPException(status_code=422, detail="Provider and proof references are required")

    duplicate_q = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.company_id == company_id,
        CompanyOperatingRecord.module == "accounting",
        CompanyOperatingRecord.record_type == "electronic_clearing_settlement",
        CompanyOperatingRecord.reference == provider_reference.strip(),
        CompanyOperatingRecord.is_archived.is_(False),
    )
    if branch_id:
        duplicate_q = duplicate_q.filter(CompanyOperatingRecord.branch_id == branch_id)
    duplicate = duplicate_q.first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Clearing settlement provider reference already exists")

    debit_code, credit_code = (
        ("1010", "1020") if direction == "provider_to_bank" else ("1020", "1010")
    )
    entry = post_codes(
        db,
        company_id=company_id,
        branch_id=branch_id,
        debit_code=debit_code,
        credit_code=credit_code,
        amount=amount,
        description=notes or f"Electronic clearing settlement {provider_reference}",
        reference_type="electronic_clearing_settlement",
        reference_id=provider_reference.strip(),
        user_id=user_id,
        entry_date=settlement_date,
    )
    record = CompanyOperatingRecord(
        company_id=company_id,
        branch_id=branch_id,
        module="accounting",
        record_type="electronic_clearing_settlement",
        reference=provider_reference.strip(),
        title=f"Electronic clearing settlement {provider_reference.strip()}",
        description=(notes or "").strip() or None,
        status="posted",
        created_by_user_id=user_id,
        amount=amount,
        currency="LSL",
        data={
            "settlement_date": settlement_date.isoformat(),
            "direction": direction,
            "proof_reference": proof_reference.strip(),
            "journal_entry_id": str(entry.id),
        },
    )
    db.add(record)
    db.flush()
    return {
        "id": str(record.id),
        "journal_entry_id": str(entry.id),
        "provider_reference": record.reference,
        "proof_reference": proof_reference.strip(),
        "direction": direction,
        "amount": float(amount),
        "settlement_date": settlement_date.isoformat(),
    }


def electronic_clearing_reconciliation(
    db: Session,
    *,
    company_id,
    as_of: date,
    branch_id=None,
) -> dict:
    """Reconcile account 1020 to unsettled electronic-source activity."""
    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    ledger_balance = _account_signed_balance(
        db,
        scope_key_value=key,
        account_code="1020",
        to_date=as_of,
        branch_id=branch_id,
    )

    payment_q = db.query(PaymentTransaction).filter(
        PaymentTransaction.company_id == company_id,
        PaymentTransaction.status == PaymentStatus.SUCCEEDED,
        PaymentTransaction.payment_method.notin_([PaymentMethod.CASH, PaymentMethod.BANK]),
        func.date(func.coalesce(PaymentTransaction.completed_at, PaymentTransaction.created_at)) <= as_of,
    )
    if branch_id:
        payment_q = payment_q.outerjoin(
            ClientCompanyLoan, ClientCompanyLoan.id == PaymentTransaction.loan_id
        ).filter(
            (ClientCompanyLoan.branch_id == branch_id) | (PaymentTransaction.loan_id.is_(None))
        )
    source_payments = payment_q.all()
    source_payment_net = Decimal("0.00")
    for row in source_payments:
        amount = _money(row.amount)
        source_payment_net += amount if row.direction == PaymentDirection.INBOUND else -amount

    treasury_q = db.query(TreasuryEntry).filter(
        TreasuryEntry.company_id == company_id,
        TreasuryEntry.payment_transaction_id.is_(None),
        TreasuryEntry.is_voided.is_(False),
        TreasuryEntry.approval_status.in_([
            TreasuryEntryApprovalStatus.POSTED,
            TreasuryEntryApprovalStatus.APPROVED,
        ]),
        TreasuryEntry.payment_method.notin_([PaymentMethod.CASH, PaymentMethod.BANK]),
        func.date(TreasuryEntry.occurred_at) <= as_of,
    )
    if branch_id:
        treasury_q = treasury_q.filter(TreasuryEntry.branch_id == branch_id)
    source_treasury = Decimal("0.00")
    treasury_rows = treasury_q.all()
    for row in treasury_rows:
        amount = _money(row.amount)
        source_treasury += amount if row.direction == TreasuryDirection.MONEY_IN else -amount

    from database.models.platform_credit_bureau import (
        PlatformCreditBureauInvoice,
        PlatformCreditBureauTransaction,
    )
    from database.models.platform_cdas import PlatformCdasInvoice, PlatformCdasTransaction
    from database.models.treasury import BranchOpeningSource
    from database.models.enums import OpeningSourceType

    provider_invoice_net = Decimal("0.00")
    provider_invoice_count = 0
    bureau_invoice_rows = db.query(PlatformCreditBureauInvoice).filter(
        PlatformCreditBureauInvoice.company_id == company_id,
        PlatformCreditBureauInvoice.status == "paid",
        PlatformCreditBureauInvoice.paid_at.is_not(None),
        func.date(PlatformCreditBureauInvoice.paid_at) <= as_of,
    ).all()
    for row in bureau_invoice_rows:
        settlement = dict(row.snapshot or {}).get("settlement") or {}
        if settlement_account_code(settlement.get("payment_method")) == "1020":
            provider_invoice_net -= _money(row.amount_due)
            provider_invoice_count += 1

    cdas_invoice_rows = db.query(PlatformCdasInvoice).filter(
        PlatformCdasInvoice.company_id == company_id,
        PlatformCdasInvoice.status == "paid",
        PlatformCdasInvoice.paid_at.is_not(None),
        func.date(PlatformCdasInvoice.paid_at) <= as_of,
    ).all()
    for row in cdas_invoice_rows:
        settlement = dict(row.snapshot or {}).get("settlement") or {}
        if settlement_account_code(settlement.get("payment_method")) == "1020":
            provider_invoice_net -= _money(row.amount_due)
            provider_invoice_count += 1

    provider_refund_net = Decimal("0.00")
    provider_refund_count = 0
    bureau_refunds = db.query(PlatformCreditBureauTransaction).filter(
        PlatformCreditBureauTransaction.company_id == company_id,
        PlatformCreditBureauTransaction.status == "refunded",
    ).all()
    for row in bureau_refunds:
        refund = dict(row.metadata_json or {}).get("refund") or {}
        recorded_at = refund.get("recorded_at")
        if recorded_at and date.fromisoformat(str(recorded_at)[:10]) <= as_of and settlement_account_code(refund.get("payment_method")) == "1020":
            provider_refund_net += _money(row.amount)
            provider_refund_count += 1

    cdas_refunds = db.query(PlatformCdasTransaction).filter(
        PlatformCdasTransaction.company_id == company_id,
        PlatformCdasTransaction.status == "refunded",
    ).all()
    for row in cdas_refunds:
        refund = dict(row.metadata_json or {}).get("refund") or {}
        recorded_at = refund.get("recorded_at")
        if recorded_at and date.fromisoformat(str(recorded_at)[:10]) <= as_of and settlement_account_code(refund.get("payment_method")) == "1020":
            provider_refund_net += _money(row.amount)
            provider_refund_count += 1

    opening_q = db.query(BranchOpeningSource).filter(
        BranchOpeningSource.company_id == company_id,
        BranchOpeningSource.is_confirmed.is_(True),
        BranchOpeningSource.is_voided.is_(False),
        BranchOpeningSource.payment_method.notin_([PaymentMethod.CASH, PaymentMethod.BANK]),
        BranchOpeningSource.source_type.notin_([
            OpeningSourceType.PREVIOUS_CLOSING,
            OpeningSourceType.HEADQUARTERS_FUNDING,
        ]),
    )
    if branch_id:
        opening_q = opening_q.filter(BranchOpeningSource.branch_id == branch_id)
    opening_rows = [
        row for row in opening_q.all()
        if row.daily_ledger and row.daily_ledger.business_date <= as_of
    ]
    opening_net = sum((_money(row.amount) for row in opening_rows), Decimal("0.00"))

    settlement_q = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.company_id == company_id,
        CompanyOperatingRecord.module == "accounting",
        CompanyOperatingRecord.record_type == "electronic_clearing_settlement",
        CompanyOperatingRecord.status == "posted",
        CompanyOperatingRecord.is_archived.is_(False),
    )
    if branch_id:
        settlement_q = settlement_q.filter(CompanyOperatingRecord.branch_id == branch_id)
    provider_to_bank = Decimal("0.00")
    bank_to_provider = Decimal("0.00")
    settlement_rows = []
    for row in settlement_q.all():
        data = dict(row.data or {})
        settlement_date_text = data.get("settlement_date")
        if not settlement_date_text or date.fromisoformat(settlement_date_text) > as_of:
            continue
        amount = _money(row.amount)
        if data.get("direction") == "provider_to_bank":
            provider_to_bank += amount
        elif data.get("direction") == "bank_to_provider":
            bank_to_provider += amount
        settlement_rows.append(row)

    expected = _money(
        source_payment_net
        + source_treasury
        + opening_net
        + provider_invoice_net
        + provider_refund_net
        - provider_to_bank
        + bank_to_provider
    )
    variance = _money(ledger_balance - expected)
    return {
        "as_of": as_of.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "ledger_clearing_balance": float(ledger_balance),
        "source_payment_net": float(_money(source_payment_net)),
        "source_treasury_net": float(_money(source_treasury)),
        "opening_source_net": float(_money(opening_net)),
        "provider_invoice_net": float(_money(provider_invoice_net)),
        "provider_refund_net": float(_money(provider_refund_net)),
        "provider_to_bank_settlements": float(_money(provider_to_bank)),
        "bank_to_provider_settlements": float(_money(bank_to_provider)),
        "expected_clearing_balance": float(expected),
        "variance": float(variance),
        "balanced": variance == 0,
        "source_counts": {
            "electronic_payments": len(source_payments),
            "manual_electronic_treasury_entries": len(treasury_rows),
            "electronic_opening_sources": len(opening_rows),
            "electronic_provider_invoice_payments": provider_invoice_count,
            "electronic_provider_refunds": provider_refund_count,
            "clearing_settlements": len(settlement_rows),
        },
    }


def electronic_clearing_aging(
    db: Session,
    *,
    company_id,
    as_of: date,
    branch_id=None,
    stale_after_days: int = ELECTRONIC_CLEARING_STALE_DAYS,
) -> dict:
    """Age the remaining 1020 balance by original journal date using FIFO matching.

    Debit lots represent electronic funds expected from a provider. Credit lots
    represent a provider-prefunding/outbound position. Opposite movements are
    matched oldest-first, so the remainder shows which clearing amounts are
    genuinely still outstanding.
    """
    if stale_after_days < 0 or stale_after_days > 365:
        raise HTTPException(status_code=422, detail="stale_after_days must be between 0 and 365")

    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    clearing = account_by_code(db, key, "1020")

    query = db.query(JournalLine, JournalEntry).join(
        JournalEntry, JournalEntry.id == JournalLine.journal_entry_id
    ).filter(
        JournalLine.account_id == clearing.id,
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date <= as_of,
    )
    if branch_id:
        query = query.filter(JournalEntry.branch_id == branch_id)

    rows = query.order_by(
        JournalEntry.entry_date.asc(),
        JournalEntry.created_at.asc(),
        JournalLine.created_at.asc(),
    ).all()

    open_lots: list[dict] = []
    for line, entry in rows:
        signed = _money(Decimal(line.debit or 0) - Decimal(line.credit or 0))
        if signed == 0:
            continue

        remaining = abs(signed)
        sign = 1 if signed > 0 else -1

        # Offset the oldest open lot on the opposite side.
        lot_index = 0
        while remaining > 0 and lot_index < len(open_lots):
            lot = open_lots[lot_index]
            if lot["sign"] == sign:
                lot_index += 1
                continue
            matched = min(remaining, lot["remaining"])
            lot["remaining"] = _money(lot["remaining"] - matched)
            remaining = _money(remaining - matched)
            if lot["remaining"] == 0:
                open_lots.pop(lot_index)
            else:
                lot_index += 1

        if remaining > 0:
            open_lots.append({
                "sign": sign,
                "remaining": remaining,
                "entry_date": entry.entry_date,
                "entry_id": str(entry.id),
                "entry_number": entry.entry_number,
                "reference_type": entry.reference_type,
                "reference_id": entry.reference_id,
                "description": entry.description,
            })

    items = []
    debit_total = Decimal("0.00")
    credit_total = Decimal("0.00")
    stale_total = Decimal("0.00")
    stale_count = 0
    buckets = {
        "0_2_days": Decimal("0.00"),
        "3_5_days": Decimal("0.00"),
        "6_10_days": Decimal("0.00"),
        "over_10_days": Decimal("0.00"),
    }

    for lot in open_lots:
        age_days = max(0, (as_of - lot["entry_date"]).days)
        signed_amount = lot["remaining"] if lot["sign"] > 0 else -lot["remaining"]
        if lot["sign"] > 0:
            debit_total += lot["remaining"]
            position = "receivable_from_provider"
        else:
            credit_total += lot["remaining"]
            position = "provider_prefunding_or_outbound"

        if age_days <= 2:
            bucket = "0_2_days"
        elif age_days <= 5:
            bucket = "3_5_days"
        elif age_days <= 10:
            bucket = "6_10_days"
        else:
            bucket = "over_10_days"
        buckets[bucket] += abs(signed_amount)

        stale = age_days > stale_after_days
        if stale:
            stale_count += 1
            stale_total += abs(signed_amount)

        items.append({
            **lot,
            "entry_date": lot["entry_date"].isoformat(),
            "age_days": age_days,
            "position": position,
            "amount": float(signed_amount),
            "absolute_amount": float(abs(signed_amount)),
            "stale": stale,
        })

    ledger_balance = _money(debit_total - credit_total)
    return {
        "as_of": as_of.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "policy": {
            "method": "fifo_open_item_aging",
            "stale_after_days": stale_after_days,
            "age_basis": "calendar_days",
        },
        "ledger_clearing_balance": float(ledger_balance),
        "open_debit_total": float(_money(debit_total)),
        "open_credit_total": float(_money(credit_total)),
        "open_item_count": len(items),
        "stale_item_count": stale_count,
        "stale_amount": float(_money(stale_total)),
        "has_stale_items": stale_count > 0,
        "aging_buckets": {name: float(_money(value)) for name, value in buckets.items()},
        "items": items,
    }


def bank_settlement_chain(
    db: Session,
    *,
    company_id,
    from_date: date,
    to_date: date,
    branch_id=None,
) -> dict:
    """Trace electronic clearing settlements from 1020 journal to bank statement evidence."""
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date must not be after to_date")

    settlement_q = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.company_id == company_id,
        CompanyOperatingRecord.module == "accounting",
        CompanyOperatingRecord.record_type == "electronic_clearing_settlement",
        CompanyOperatingRecord.status == "posted",
        CompanyOperatingRecord.is_archived.is_(False),
    )
    if branch_id:
        settlement_q = settlement_q.filter(CompanyOperatingRecord.branch_id == branch_id)

    bank_batches = db.query(ReconciliationBatch).filter(
        ReconciliationBatch.company_id == company_id,
        ReconciliationBatch.source_type == "bank_statement",
        ReconciliationBatch.period_end >= from_date,
        ReconciliationBatch.period_start <= to_date,
    )
    if branch_id:
        bank_batches = bank_batches.filter(
            (ReconciliationBatch.branch_id == branch_id) | (ReconciliationBatch.branch_id.is_(None))
        )
    batch_rows = bank_batches.all()
    batch_ids = [row.id for row in batch_rows]
    reconciliation_lines = (
        db.query(ReconciliationLine)
        .filter(
            ReconciliationLine.batch_id.in_(batch_ids),
            ReconciliationLine.source_kind == "external",
        )
        .all()
        if batch_ids
        else []
    )

    matched_by_settlement: dict[str, ReconciliationLine] = {}
    for line in reconciliation_lines:
        settlement_id = str((line.source_payload or {}).get("matched_clearing_settlement_id") or "")
        if settlement_id and line.status == "matched":
            matched_by_settlement[settlement_id] = line

    items = []
    unmatched = []
    for settlement in settlement_q.all():
        data = dict(settlement.data or {})
        settlement_date_text = data.get("settlement_date")
        if not settlement_date_text:
            continue
        settlement_date = date.fromisoformat(settlement_date_text)
        if settlement_date < from_date or settlement_date > to_date:
            continue

        line = matched_by_settlement.get(str(settlement.id))
        journal_id = data.get("journal_entry_id")
        journal_exists = bool(
            journal_id
            and db.query(JournalEntry.id).filter(
                JournalEntry.id == UUID(str(journal_id)),
                JournalEntry.company_id == company_id,
                JournalEntry.reference_type == "electronic_clearing_settlement",
                JournalEntry.status == "posted",
            ).first()
        )
        item = {
            "settlement_id": str(settlement.id),
            "provider_reference": settlement.reference,
            "proof_reference": data.get("proof_reference"),
            "settlement_date": settlement_date.isoformat(),
            "direction": data.get("direction"),
            "amount": float(_money(settlement.amount)),
            "journal_entry_id": journal_id,
            "journal_posted": journal_exists,
            "bank_statement_matched": line is not None,
            "reconciliation_line_id": str(line.id) if line else None,
            "reconciliation_batch_id": str(line.batch_id) if line else None,
            "bank_reference": line.reference if line else None,
            "bank_transaction_date": line.transaction_date.isoformat() if line else None,
        }
        items.append(item)
        if not journal_exists or line is None:
            unmatched.append(str(settlement.id))

    return {
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "branch_id": str(branch_id) if branch_id else None,
        "settlement_count": len(items),
        "fully_traced_count": len(items) - len(unmatched),
        "unmatched_count": len(unmatched),
        "complete": len(unmatched) == 0,
        "unmatched_settlement_ids": unmatched,
        "items": items,
    }
