from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database.models.accounting import JournalEntry
from database.models.enums import (
    BranchTransferStatus,
    OpeningSourceType,
    PaymentDirection,
    PaymentMethod,
    PaymentStatus,
    TreasuryDayStatus,
    TreasuryDirection,
    TreasuryEntryApprovalStatus,
    TreasuryEntryType,
)
from database.models.payment import PaymentTransaction
from database.models.treasury import (
    BranchDailyLedger,
    BranchFundingTransfer,
    BranchOpeningSource,
    TreasuryEntry,
)
from services.accounting_service import (
    company_payment_accounting_expected,
    record_opening_source_accounting,
    record_payment_accounting,
    record_treasury_entry_accounting,
    scope_key,
)
from services.treasury_service import (
    get_or_create_settings,
    money,
    recalculate_daily_ledger,
    record_payment_treasury_entry,
    resolve_payment_branch_id,
    resolve_timezone,
)

MONEY_TOLERANCE = Decimal("0.01")


def _day_bounds(settings, business_date: date) -> tuple[datetime, datetime]:
    zone = resolve_timezone(settings.timezone)
    start_local = datetime.combine(business_date, time.min, tzinfo=zone)
    end_local = datetime.combine(business_date, time.max, tzinfo=zone)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _severity_status(critical_count: int, warning_count: int) -> str:
    if critical_count:
        return "critical"
    if warning_count:
        return "warning"
    return "healthy"


def _issue(
    issues: list[dict[str, object]],
    *,
    code: str,
    severity: str,
    title: str,
    detail: str,
    record_type: str | None = None,
    record_id: object | None = None,
    branch_id: UUID | None = None,
    amount: Decimal | None = None,
    repairable: bool = False,
) -> None:
    issues.append({
        "code": code,
        "severity": severity,
        "title": title,
        "detail": detail,
        "record_type": record_type,
        "record_id": str(record_id) if record_id is not None else None,
        "branch_id": branch_id,
        "amount": money(amount) if amount is not None else None,
        "repairable": repairable,
    })


def _payment_rows(
    db: Session,
    *,
    company_id: UUID,
    business_date: date,
) -> list[PaymentTransaction]:
    settings = get_or_create_settings(db, company_id)
    start_utc, end_utc = _day_bounds(settings, business_date)
    return (
        db.query(PaymentTransaction)
        .options(
            joinedload(PaymentTransaction.loan),
            joinedload(PaymentTransaction.cash_transaction),
            joinedload(PaymentTransaction.company_borrower_account),
        )
        .filter(
            PaymentTransaction.company_id == company_id,
            PaymentTransaction.status == PaymentStatus.SUCCEEDED,
            func.coalesce(PaymentTransaction.completed_at, PaymentTransaction.created_at) >= start_utc,
            func.coalesce(PaymentTransaction.completed_at, PaymentTransaction.created_at) <= end_utc,
        )
        .order_by(PaymentTransaction.completed_at.asc())
        .all()
    )


def _active_treasury_entries(query):
    return query.filter(
        TreasuryEntry.is_voided.is_(False),
        TreasuryEntry.approval_status.in_([
            TreasuryEntryApprovalStatus.POSTED,
            TreasuryEntryApprovalStatus.APPROVED,
        ]),
    )


def build_financial_integrity_report(
    db: Session,
    *,
    company_id: UUID,
    business_date: date,
    branch_id: UUID | None = None,
) -> dict[str, object]:
    issues: list[dict[str, object]] = []
    checks_run = 0
    settings = get_or_create_settings(db, company_id)
    scope, _ = scope_key(company_id)

    payments = _payment_rows(db, company_id=company_id, business_date=business_date)
    scoped_payments: list[tuple[PaymentTransaction, UUID | None]] = []
    for payment in payments:
        resolved_branch = resolve_payment_branch_id(db, payment)
        if branch_id and resolved_branch != branch_id:
            continue
        scoped_payments.append((payment, resolved_branch))

    payment_ids = [payment.id for payment, _ in scoped_payments]
    treasury_by_payment = {
        row.payment_transaction_id: row
        for row in db.query(TreasuryEntry).filter(
            TreasuryEntry.company_id == company_id,
            TreasuryEntry.payment_transaction_id.in_(payment_ids or [None]),
        ).all()
        if row.payment_transaction_id is not None
    }
    journal_by_payment = {
        row.reference_id: row
        for row in db.query(JournalEntry).filter(
            JournalEntry.scope_key == scope,
            JournalEntry.reference_type == "payment_transaction",
            JournalEntry.reference_id.in_([str(value) for value in payment_ids] or ["__none__"]),
        ).all()
    }

    checks_run += 1
    for payment, resolved_branch in scoped_payments:
        if payment.completed_at is None:
            _issue(
                issues,
                code="PAYMENT_COMPLETION_TIME_MISSING",
                severity="critical",
                title="Successful payment has no completion timestamp",
                detail=(
                    f"Payment {payment.provider_reference or payment.id} is marked successful but completed_at is empty. "
                    "The integrity scan used its creation time so the transaction is not silently omitted."
                ),
                record_type="payment_transaction",
                record_id=payment.id,
                branch_id=resolved_branch,
                amount=payment.amount,
            )
        if resolved_branch is None:
            _issue(
                issues,
                code="PAYMENT_BRANCH_UNRESOLVED",
                severity="critical",
                title="Successful payment has no operational branch",
                detail=(
                    f"Successful {payment.purpose.value.replace('_', ' ')} payment {payment.provider_reference or payment.id} "
                    "cannot be allocated to a branch treasury. Configure Headquarters or link the source record to a branch."
                ),
                record_type="payment_transaction",
                record_id=payment.id,
                amount=payment.amount,
                repairable=False,
            )
            continue
        treasury = treasury_by_payment.get(payment.id)
        if treasury is None:
            _issue(
                issues,
                code="PAYMENT_MISSING_TREASURY",
                severity="critical",
                title="Successful payment is missing from the money book",
                detail=(
                    f"Payment {payment.provider_reference or payment.id} succeeded but has no linked treasury entry. "
                    "The accounting control centre would otherwise understate money movement."
                ),
                record_type="payment_transaction",
                record_id=payment.id,
                branch_id=resolved_branch,
                amount=payment.amount,
                repairable=True,
            )
        elif treasury.is_voided:
            _issue(
                issues,
                code="PAYMENT_TREASURY_VOIDED",
                severity="critical",
                title="Successful payment is linked to a voided treasury entry",
                detail=f"Payment {payment.provider_reference or payment.id} is successful while its money-book entry is voided.",
                record_type="treasury_entry",
                record_id=treasury.id,
                branch_id=treasury.branch_id,
                amount=treasury.amount,
            )
        else:
            expected_direction = (
                TreasuryDirection.MONEY_IN
                if payment.direction == PaymentDirection.INBOUND
                else TreasuryDirection.MONEY_OUT
            )
            mismatches: list[str] = []
            if money(treasury.amount) != money(payment.amount):
                mismatches.append(f"amount {money(treasury.amount)} vs payment {money(payment.amount)}")
            if treasury.payment_method != payment.payment_method:
                mismatches.append(f"channel {treasury.payment_method.value} vs payment {payment.payment_method.value}")
            if treasury.direction != expected_direction:
                mismatches.append(f"direction {treasury.direction.value} vs expected {expected_direction.value}")
            if treasury.branch_id != resolved_branch:
                mismatches.append("operational branch differs from the payment source")
            if mismatches:
                _issue(
                    issues,
                    code="PAYMENT_TREASURY_MISMATCH",
                    severity="critical",
                    title="Payment and money-book entry disagree",
                    detail=f"Payment {payment.provider_reference or payment.id}: " + "; ".join(mismatches) + ".",
                    record_type="treasury_entry",
                    record_id=treasury.id,
                    branch_id=treasury.branch_id,
                    amount=treasury.amount,
                )

        if company_payment_accounting_expected(payment) and str(payment.id) not in journal_by_payment:
            _issue(
                issues,
                code="PAYMENT_MISSING_JOURNAL",
                severity="critical",
                title="Successful payment is missing an accounting journal",
                detail=(
                    f"Payment {payment.provider_reference or payment.id} should create a posted company journal but none was found."
                ),
                record_type="payment_transaction",
                record_id=payment.id,
                branch_id=resolved_branch,
                amount=payment.amount,
                repairable=True,
            )
        elif company_payment_accounting_expected(payment):
            journal = journal_by_payment[str(payment.id)]
            if money(journal.total_debit) != money(payment.amount) or money(journal.total_credit) != money(payment.amount):
                _issue(
                    issues,
                    code="PAYMENT_JOURNAL_AMOUNT_MISMATCH",
                    severity="critical",
                    title="Payment journal total does not match the successful payment",
                    detail=(
                        f"Payment {payment.provider_reference or payment.id} is {money(payment.amount)} but journal "
                        f"{journal.entry_number} totals debit {money(journal.total_debit)} and credit {money(journal.total_credit)}."
                    ),
                    record_type="journal_entry",
                    record_id=journal.id,
                    branch_id=resolved_branch,
                    amount=payment.amount,
                )

    ledger_query = db.query(BranchDailyLedger).filter(
        BranchDailyLedger.company_id == company_id,
        BranchDailyLedger.business_date == business_date,
    )
    if branch_id:
        ledger_query = ledger_query.filter(BranchDailyLedger.branch_id == branch_id)
    ledgers = ledger_query.all()
    ledger_ids = [ledger.id for ledger in ledgers]

    treasury_query = db.query(TreasuryEntry).filter(
        TreasuryEntry.company_id == company_id,
        TreasuryEntry.daily_ledger_id.in_(ledger_ids or [None]),
    )
    all_entries = treasury_query.all()
    posted_entries = [
        row for row in all_entries
        if not row.is_voided and row.approval_status in {
            TreasuryEntryApprovalStatus.POSTED,
            TreasuryEntryApprovalStatus.APPROVED,
        }
    ]

    checks_run += 1
    manual_entries = [row for row in posted_entries if not row.payment_transaction_id]
    manual_journal_ids = [str(row.id) for row in manual_entries if row.entry_type != TreasuryEntryType.BRANCH_FUNDING]
    manual_journals = {
        row.reference_id: row
        for row in db.query(JournalEntry).filter(
            JournalEntry.scope_key == scope,
            JournalEntry.reference_type == "treasury_entry",
            JournalEntry.reference_id.in_(manual_journal_ids or ["__none__"]),
        ).all()
    }
    for entry in manual_entries:
        if entry.entry_type != TreasuryEntryType.BRANCH_FUNDING and str(entry.id) not in manual_journals:
            _issue(
                issues,
                code="TREASURY_MISSING_JOURNAL",
                severity="critical",
                title="Posted money-book entry is missing an accounting journal",
                detail=f"{entry.description} is posted in treasury but has no linked general-ledger journal.",
                record_type="treasury_entry",
                record_id=entry.id,
                branch_id=entry.branch_id,
                amount=entry.amount,
                repairable=True,
            )

    checks_run += 1
    proof_exception_count = 0
    for entry in posted_entries:
        if (
            entry.payment_method != PaymentMethod.CASH
            and not (entry.proof_reference or "").strip()
            and not (entry.proof_url or "").strip()
        ):
            proof_exception_count += 1
            _issue(
                issues,
                code="NON_CASH_WITHOUT_PROOF",
                severity="warning",
                title="Non-cash movement has no proof reference",
                detail=f"{entry.description} uses {entry.payment_method.value} but has no proof reference or supporting document.",
                record_type="treasury_entry",
                record_id=entry.id,
                branch_id=entry.branch_id,
                amount=entry.amount,
            )

    source_query = db.query(BranchOpeningSource).filter(
        BranchOpeningSource.company_id == company_id,
        BranchOpeningSource.daily_ledger_id.in_(ledger_ids or [None]),
        BranchOpeningSource.is_voided.is_(False),
        BranchOpeningSource.is_confirmed.is_(True),
    )
    sources = source_query.all()
    journal_expected_sources = [
        source for source in sources
        if source.source_type not in {OpeningSourceType.PREVIOUS_CLOSING, OpeningSourceType.HEADQUARTERS_FUNDING}
    ]
    source_journals = {
        row.reference_id: row
        for row in db.query(JournalEntry).filter(
            JournalEntry.scope_key == scope,
            JournalEntry.reference_type == "opening_source",
            JournalEntry.reference_id.in_([str(row.id) for row in journal_expected_sources] or ["__none__"]),
        ).all()
    }
    checks_run += 1
    for source in journal_expected_sources:
        if str(source.id) not in source_journals:
            _issue(
                issues,
                code="OPENING_SOURCE_MISSING_JOURNAL",
                severity="critical",
                title="Confirmed opening source is missing an accounting journal",
                detail=f"Opening source {source.source_reference} is included in branch funds but not the general ledger.",
                record_type="opening_source",
                record_id=source.id,
                branch_id=source.branch_id,
                amount=source.amount,
                repairable=True,
            )

    checks_run += 1
    ledger_variance_count = 0
    for ledger in ledgers:
        active = [row for row in posted_entries if row.daily_ledger_id == ledger.id]
        ledger_sources = [row for row in sources if row.daily_ledger_id == ledger.id]
        expected_opening = money(sum((money(row.amount) for row in ledger_sources), Decimal("0.00")))
        expected_in = money(sum((money(row.amount) for row in active if row.direction == TreasuryDirection.MONEY_IN), Decimal("0.00")))
        expected_out = money(sum((money(row.amount) for row in active if row.direction == TreasuryDirection.MONEY_OUT), Decimal("0.00")))
        expected_close = money(expected_opening + expected_in - expected_out)
        stored_gap = max(
            abs(money(ledger.opening_balance) - expected_opening),
            abs(money(ledger.total_money_in) - expected_in),
            abs(money(ledger.total_money_out) - expected_out),
            abs(money(ledger.expected_closing_balance) - expected_close),
        )
        if stored_gap > MONEY_TOLERANCE:
            _issue(
                issues,
                code="LEDGER_TOTALS_STALE",
                severity="critical",
                title="Stored branch totals do not match underlying transactions",
                detail=(
                    f"The stored totals for {ledger.business_date.isoformat()} differ from confirmed opening sources and posted movements."
                ),
                record_type="branch_daily_ledger",
                record_id=ledger.id,
                branch_id=ledger.branch_id,
                amount=stored_gap,
                repairable=ledger.status in {TreasuryDayStatus.OPEN, TreasuryDayStatus.REOPENED},
            )
        if abs(money(ledger.variance_amount)) > MONEY_TOLERANCE:
            ledger_variance_count += 1
            _issue(
                issues,
                code="DECLARED_CLOSING_VARIANCE",
                severity="warning",
                title="Branch declared closing does not reconcile",
                detail=f"Declared versus expected closing variance is {money(ledger.variance_amount)}.",
                record_type="branch_daily_ledger",
                record_id=ledger.id,
                branch_id=ledger.branch_id,
                amount=ledger.variance_amount,
            )

    transfer_query = db.query(BranchFundingTransfer).filter(
        BranchFundingTransfer.company_id == company_id,
        BranchFundingTransfer.business_date == business_date,
    )
    if branch_id:
        transfer_query = transfer_query.filter(
            (BranchFundingTransfer.source_branch_id == branch_id)
            | (BranchFundingTransfer.target_branch_id == branch_id)
        )
    transfers = transfer_query.all()
    checks_run += 1
    for transfer in transfers:
        outgoing = next((row for row in all_entries if row.transfer_id == transfer.id and row.entry_type == TreasuryEntryType.BRANCH_FUNDING), None)
        opening = next((row for row in sources if row.transfer_id == transfer.id and row.source_type == OpeningSourceType.HEADQUARTERS_FUNDING), None)
        if outgoing is None or opening is None:
            _issue(
                issues,
                code="BRANCH_TRANSFER_INCOMPLETE",
                severity="critical",
                title="Branch funding transfer is missing one side of the audit trail",
                detail=f"Transfer {transfer.reference} must have both an HQ outflow and a destination opening source.",
                record_type="branch_funding_transfer",
                record_id=transfer.id,
                amount=transfer.amount,
            )
        elif transfer.status == BranchTransferStatus.RECEIVED and not opening.is_confirmed:
            _issue(
                issues,
                code="BRANCH_TRANSFER_RECEIPT_MISMATCH",
                severity="critical",
                title="Received branch funding is not confirmed in the destination opening balance",
                detail=f"Transfer {transfer.reference} is marked received but its opening source is not confirmed.",
                record_type="branch_funding_transfer",
                record_id=transfer.id,
                amount=transfer.amount,
            )

    checks_run += 1
    journal_query = (
        db.query(JournalEntry)
        .options(joinedload(JournalEntry.lines))
        .filter(
            JournalEntry.scope_key == scope,
            JournalEntry.entry_date == business_date,
            JournalEntry.status == "posted",
        )
    )
    if branch_id:
        journal_query = journal_query.filter(JournalEntry.branch_id == branch_id)
    journals = journal_query.all()
    unbalanced_journal_count = 0
    for journal in journals:
        debit = money(sum((money(line.debit) for line in journal.lines), Decimal("0.00")))
        credit = money(sum((money(line.credit) for line in journal.lines), Decimal("0.00")))
        header_debit = money(journal.total_debit)
        header_credit = money(journal.total_credit)
        if debit != credit or debit != header_debit or credit != header_credit:
            unbalanced_journal_count += 1
            _issue(
                issues,
                code="UNBALANCED_JOURNAL",
                severity="critical",
                title="Posted journal is not balanced",
                detail=f"Journal {journal.entry_number} has inconsistent debit/credit totals or header values.",
                record_type="journal_entry",
                record_id=journal.id,
                branch_id=journal.branch_id,
                amount=abs(debit - credit),
            )

    pending_rows = [
        row for row in all_entries
        if not row.is_voided
        and row.entry_type == TreasuryEntryType.EXPENSE
        and row.approval_status == TreasuryEntryApprovalStatus.PENDING
    ]
    pending_expense_amount = money(sum((money(row.amount) for row in pending_rows), Decimal("0.00")))
    if pending_rows:
        _issue(
            issues,
            code="PENDING_EXPENSES",
            severity="info",
            title="Expenses are awaiting approval",
            detail=f"{len(pending_rows)} expense(s) totalling {pending_expense_amount} remain excluded from posted balances.",
            record_type="treasury_entry",
            amount=pending_expense_amount,
        )

    critical_count = sum(1 for row in issues if row["severity"] == "critical")
    warning_count = sum(1 for row in issues if row["severity"] == "warning")
    repairable_count = sum(1 for row in issues if row["repairable"])
    missing_treasury_count = sum(1 for row in issues if row["code"] == "PAYMENT_MISSING_TREASURY")
    missing_journal_count = sum(1 for row in issues if row["code"] in {
        "PAYMENT_MISSING_JOURNAL",
        "TREASURY_MISSING_JOURNAL",
        "OPENING_SOURCE_MISSING_JOURNAL",
    })

    return {
        "business_date": business_date,
        "branch_id": branch_id,
        "generated_at": datetime.now(timezone.utc),
        "status": _severity_status(critical_count, warning_count),
        "checks_run": checks_run,
        "issue_count": len(issues),
        "critical_count": critical_count,
        "warning_count": warning_count,
        "repairable_count": repairable_count,
        "succeeded_payment_count": len(scoped_payments),
        "treasury_payment_count": sum(1 for payment, _ in scoped_payments if payment.id in treasury_by_payment),
        "posted_treasury_count": len(posted_entries),
        "posted_journal_count": len(journals),
        "pending_expense_count": len(pending_rows),
        "pending_expense_amount": pending_expense_amount,
        "proof_exception_count": proof_exception_count,
        "ledger_variance_count": ledger_variance_count,
        "missing_treasury_count": missing_treasury_count,
        "missing_journal_count": missing_journal_count,
        "unbalanced_journal_count": unbalanced_journal_count,
        "issues": issues,
    }


def repair_financial_integrity(
    db: Session,
    *,
    company_id: UUID,
    business_date: date,
    branch_id: UUID | None = None,
) -> dict[str, object]:
    """Repair idempotent derived records without inventing source transactions.

    This function only rebuilds treasury links, accounting journals and cached
    ledger totals from already successful/confirmed source records. It never
    manufactures a payment, changes a payment result, approves an expense, or
    alters a declared cash count.
    """
    repaired_treasury = 0
    repaired_journals = 0
    recalculated = 0

    payments = _payment_rows(db, company_id=company_id, business_date=business_date)
    scope, _ = scope_key(company_id)
    for payment in payments:
        resolved_branch = resolve_payment_branch_id(db, payment)
        if branch_id and resolved_branch != branch_id:
            continue
        if not resolved_branch:
            continue
        treasury = db.query(TreasuryEntry).filter(TreasuryEntry.payment_transaction_id == payment.id).first()
        if treasury is None:
            try:
                created = record_payment_treasury_entry(db, payment, branch_id=resolved_branch)
            except HTTPException:
                # A historical submitted day can intentionally reject a late
                # rebuild. Report the gap but never mutate a locked snapshot.
                created = None
            if created is not None:
                repaired_treasury += 1
        if company_payment_accounting_expected(payment):
            journal = db.query(JournalEntry).filter(
                JournalEntry.scope_key == scope,
                JournalEntry.reference_type == "payment_transaction",
                JournalEntry.reference_id == str(payment.id),
            ).first()
            if journal is None:
                record_payment_accounting(db, payment)
                repaired_journals += 1

    ledger_query = db.query(BranchDailyLedger).filter(
        BranchDailyLedger.company_id == company_id,
        BranchDailyLedger.business_date == business_date,
    )
    if branch_id:
        ledger_query = ledger_query.filter(BranchDailyLedger.branch_id == branch_id)
    ledgers = ledger_query.all()
    ledger_ids = [row.id for row in ledgers]

    entries = _active_treasury_entries(
        db.query(TreasuryEntry).filter(
            TreasuryEntry.company_id == company_id,
            TreasuryEntry.daily_ledger_id.in_(ledger_ids or [None]),
        )
    ).all()
    for entry in entries:
        if entry.payment_transaction_id or entry.entry_type == TreasuryEntryType.BRANCH_FUNDING:
            continue
        journal = db.query(JournalEntry).filter(
            JournalEntry.scope_key == scope,
            JournalEntry.reference_type == "treasury_entry",
            JournalEntry.reference_id == str(entry.id),
        ).first()
        if journal is None:
            record_treasury_entry_accounting(db, entry)
            repaired_journals += 1

    sources = db.query(BranchOpeningSource).filter(
        BranchOpeningSource.company_id == company_id,
        BranchOpeningSource.daily_ledger_id.in_(ledger_ids or [None]),
        BranchOpeningSource.is_voided.is_(False),
        BranchOpeningSource.is_confirmed.is_(True),
    ).all()
    for source in sources:
        if source.source_type in {OpeningSourceType.PREVIOUS_CLOSING, OpeningSourceType.HEADQUARTERS_FUNDING}:
            continue
        journal = db.query(JournalEntry).filter(
            JournalEntry.scope_key == scope,
            JournalEntry.reference_type == "opening_source",
            JournalEntry.reference_id == str(source.id),
        ).first()
        if journal is None:
            record_opening_source_accounting(db, source)
            repaired_journals += 1

    for ledger in ledgers:
        if ledger.status in {TreasuryDayStatus.OPEN, TreasuryDayStatus.REOPENED}:
            recalculate_daily_ledger(db, ledger)
            recalculated += 1

    db.flush()
    report = build_financial_integrity_report(
        db,
        company_id=company_id,
        business_date=business_date,
        branch_id=branch_id,
    )
    return {
        "repaired_treasury_entries": repaired_treasury,
        "repaired_journals": repaired_journals,
        "recalculated_ledgers": recalculated,
        "report": report,
    }
