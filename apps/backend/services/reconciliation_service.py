from __future__ import annotations

import csv
import re
import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from io import StringIO
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from core.access_control import TenantContext
from database.models.accounting import AccountingAccount, JournalEntry, JournalLine
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_operating_system import CompanyOperatingRecord
from database.models.enums import PaymentDirection, PaymentPurpose, PaymentStatus
from database.models.governance_control import ApprovalRequest, PaymentAdjustment
from database.models.payment import PaymentTransaction
from database.models.reconciliation import ReconciliationBatch, ReconciliationEvent, ReconciliationLine
from services.polyglot_runtime_service import (
    record_parity_mismatch,
    rust_variance_classification,
    stable_sha256_text,
    workload_routing_mode,
)


MONEY = Decimal("0.01")
UNRESOLVED = {"unmatched", "shortage", "excess", "missing_source", "adjustment_required"}
FINAL_BATCH_STATUSES = {"closed"}
SUPPORTED_SOURCES = {"bank_statement", "payment_provider", "employer_payroll", "cdas_remittance", "manual_import"}


def money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=f"Invalid money amount: {value!r}") from exc


def normalize_header(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def parse_date(value: str) -> date:
    text = str(value or "").strip()
    for parser in (
        lambda: date.fromisoformat(text),
        lambda: datetime.strptime(text, "%d/%m/%Y").date(),
        lambda: datetime.strptime(text, "%d-%m-%Y").date(),
        lambda: datetime.strptime(text, "%Y/%m/%d").date(),
    ):
        try:
            return parser()
        except ValueError:
            pass
    raise HTTPException(status_code=422, detail=f"Unsupported transaction date: {text!r}")


def source_fingerprint(*, company_id: UUID, source_type: str, transaction_date: date, reference: str | None, description: str | None, amount: Decimal, direction: str) -> str:
    raw = "|".join([
        str(company_id),
        source_type.strip().lower(),
        transaction_date.isoformat(),
        str(reference or "").strip().upper(),
        str(description or "").strip().upper(),
        str(money(amount)),
        direction.strip().lower(),
    ])
    return stable_sha256_text(
        correlation_id=f"reconciliation-source:{company_id}:{transaction_date.isoformat()}",
        payload=raw,
    )


def _event(db: Session, batch: ReconciliationBatch, event_type: str, actor_user_id: UUID | None, *, line_id: UUID | None = None, payload: dict[str, Any] | None = None) -> None:
    db.add(ReconciliationEvent(
        company_id=batch.company_id,
        batch_id=batch.id,
        line_id=line_id,
        event_type=event_type,
        actor_user_id=actor_user_id,
        payload=payload or {},
    ))


def batch_or_404(db: Session, context: TenantContext, batch_id: UUID, *, lock: bool = False) -> ReconciliationBatch:
    query = db.query(ReconciliationBatch).filter(
        ReconciliationBatch.id == batch_id,
        ReconciliationBatch.company_id == context.company_id,
    )
    if context.branch_id:
        query = query.filter(ReconciliationBatch.branch_id == context.branch_id)
    if lock:
        query = query.with_for_update()
    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail="Reconciliation batch was not found")
    return row


def line_or_404(db: Session, context: TenantContext, batch_id: UUID, line_id: UUID) -> ReconciliationLine:
    row = db.query(ReconciliationLine).join(ReconciliationBatch, ReconciliationBatch.id == ReconciliationLine.batch_id).filter(
        ReconciliationLine.id == line_id,
        ReconciliationLine.batch_id == batch_id,
        ReconciliationLine.company_id == context.company_id,
    )
    if context.branch_id:
        row = row.filter(ReconciliationBatch.branch_id == context.branch_id)
    value = row.first()
    if not value:
        raise HTTPException(status_code=404, detail="Reconciliation line was not found")
    return value


def create_batch(db: Session, context: TenantContext, *, source_type: str, source_reference: str | None, account_reference: str | None, period_start: date, period_end: date, currency: str) -> ReconciliationBatch:
    source = source_type.strip().lower()
    if source not in SUPPORTED_SOURCES:
        raise HTTPException(status_code=422, detail="Unsupported reconciliation source type")
    if period_end < period_start:
        raise HTTPException(status_code=422, detail="Period end cannot be before period start")
    batch = ReconciliationBatch(
        company_id=context.company_id,
        branch_id=context.branch_id,
        batch_reference=f"REC-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{secrets.token_hex(3).upper()}",
        source_type=source,
        source_reference=(source_reference or "").strip() or None,
        account_reference=(account_reference or "").strip() or None,
        period_start=period_start,
        period_end=period_end,
        currency=currency.strip().upper() or "LSL",
        status="draft",
        methodology_snapshot={
            "matching_priority": [
                "exact_clearing_settlement_provider_reference",
                "exact_clearing_settlement_proof_reference",
                "exact_provider_reference",
                "exact_proof_reference",
                "exact_folio_or_loan_reference_with_unique_payment",
            ],
            "date_tolerance_days": 3,
            "free_text_name_matching": False,
            "ambiguous_matches": "exception",
        },
    )
    db.add(batch)
    db.flush()
    _event(db, batch, "batch_created", context.user.id, payload={"source_type": source, "period_start": period_start.isoformat(), "period_end": period_end.isoformat()})
    db.commit()
    db.refresh(batch)
    return batch


def _payment_payload(payment: PaymentTransaction) -> dict[str, Any]:
    return {
        "id": str(payment.id),
        "provider_reference": payment.provider_reference,
        "proof_reference": payment.proof_reference,
        "amount": float(payment.amount or 0),
        "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
        "loan_id": str(payment.loan_id) if payment.loan_id else None,
    }


def _payment_query(db: Session, batch: ReconciliationBatch):
    query = db.query(PaymentTransaction).filter(
        PaymentTransaction.company_id == batch.company_id,
        PaymentTransaction.status == PaymentStatus.SUCCEEDED,
        PaymentTransaction.direction == PaymentDirection.INBOUND,
        PaymentTransaction.purpose.in_([PaymentPurpose.LOAN_REPAYMENT, PaymentPurpose.DIRECT_DEBIT]),
    )
    if batch.branch_id:
        query = query.join(ClientCompanyLoan, ClientCompanyLoan.id == PaymentTransaction.loan_id).filter(ClientCompanyLoan.branch_id == batch.branch_id)
    return query


def _tokens(line: ReconciliationLine) -> list[str]:
    text = f"{line.reference or ''} {line.description or ''}".upper()
    return [item for item in re.findall(r"[A-Z0-9][A-Z0-9_-]{3,}", text) if len(item) >= 4]


def _classify_amount(line: ReconciliationLine, payment: PaymentTransaction, method: str, confidence: Decimal) -> None:
    expected = money(payment.amount)
    actual = money(line.amount)
    variance = money(actual - expected)

    expected_cents = int(expected * 100)
    actual_cents = int(actual * 100)
    python_status = (
        "matched" if variance == 0 else "shortage" if variance < 0 else "excess"
    )
    routing_mode = workload_routing_mode("rust_reconciliation")
    delegated = (
        rust_variance_classification(
            expected_cents=expected_cents,
            actual_cents=actual_cents,
        )
        if routing_mode != "off"
        else None
    )
    delegated_status = None
    if delegated:
        delegated_variance = int(delegated.get("variance_cents", 0))
        delegated_candidate = str(delegated.get("status") or "")
        parity_passed = (
            delegated_variance == int(variance * 100)
            and delegated_candidate == python_status
        )
        if parity_passed:
            delegated_status = delegated_candidate
        else:
            record_parity_mismatch("rust_compute")

    status_value = (
        delegated_status
        if routing_mode == "prefer-worker" and delegated_status
        else python_status
    )

    line.matched_payment_id = payment.id
    line.matched_loan_id = payment.loan_id
    line.matched_borrower_id = payment.borrower_id
    line.expected_amount = expected
    line.variance_amount = variance
    line.match_method = method
    line.match_confidence = confidence
    line.matched_at = datetime.now(timezone.utc)
    if status_value == "matched":
        line.status = "matched"
        line.exception_code = None
        line.exception_reason = None
    elif status_value == "shortage":
        line.status = "shortage"
        line.exception_code = "AMOUNT_SHORT"
        line.exception_reason = "External source amount is lower than the matched LoanHub payment"
    else:
        line.status = "excess"
        line.exception_code = "AMOUNT_EXCESS"
        line.exception_reason = "External source amount is higher than the matched LoanHub payment"


def _clearing_settlement_query(db: Session, batch: ReconciliationBatch):
    query = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.company_id == batch.company_id,
        CompanyOperatingRecord.module == "accounting",
        CompanyOperatingRecord.record_type == "electronic_clearing_settlement",
        CompanyOperatingRecord.status == "posted",
        CompanyOperatingRecord.is_archived.is_(False),
    )
    if batch.branch_id:
        query = query.filter(CompanyOperatingRecord.branch_id == batch.branch_id)
    return query


def _classify_clearing_settlement(
    line: ReconciliationLine,
    settlement: CompanyOperatingRecord,
    *,
    method: str,
    confidence: Decimal,
) -> None:
    data = dict(settlement.data or {})
    expected = money(settlement.amount)
    actual = money(line.amount)
    variance = money(actual - expected)
    expected_direction = "credit" if data.get("direction") == "provider_to_bank" else "debit"

    line.expected_amount = expected
    line.variance_amount = variance
    line.match_method = method
    line.match_confidence = confidence
    line.matched_at = datetime.now(timezone.utc)
    payload = dict(line.source_payload or {})
    payload["matched_clearing_settlement_id"] = str(settlement.id)
    payload["matched_clearing_journal_entry_id"] = data.get("journal_entry_id")
    payload["expected_bank_direction"] = expected_direction
    payload["clearing_provider_reference"] = settlement.reference
    payload["clearing_proof_reference"] = data.get("proof_reference")
    line.source_payload = payload

    if line.direction != expected_direction:
        line.status = "adjustment_required"
        line.exception_code = "CLEARING_DIRECTION_MISMATCH"
        line.exception_reason = (
            f"Bank statement direction {line.direction} does not agree with "
            f"clearing settlement direction {expected_direction}"
        )
    elif variance == 0:
        line.status = "matched"
        line.exception_code = None
        line.exception_reason = None
    elif variance < 0:
        line.status = "shortage"
        line.exception_code = "CLEARING_AMOUNT_SHORT"
        line.exception_reason = "Bank settlement is lower than the clearing settlement amount"
    else:
        line.status = "excess"
        line.exception_code = "CLEARING_AMOUNT_EXCESS"
        line.exception_reason = "Bank settlement is higher than the clearing settlement amount"


def _match_bank_line_to_clearing_settlement(
    db: Session,
    batch: ReconciliationBatch,
    line: ReconciliationLine,
) -> bool:
    if batch.source_type != "bank_statement":
        return False
    reference = (line.reference or "").strip()
    if not reference:
        return False

    rows = _clearing_settlement_query(db, batch).all()
    matches: list[tuple[CompanyOperatingRecord, str]] = []
    for row in rows:
        data = dict(row.data or {})
        proof_reference = str(data.get("proof_reference") or "").strip()
        if row.reference == reference:
            matches.append((row, "exact_clearing_settlement_provider_reference"))
        elif proof_reference and proof_reference == reference:
            matches.append((row, "exact_clearing_settlement_proof_reference"))

    unique = {row.id: (row, method) for row, method in matches}
    if len(unique) == 1:
        row, method = next(iter(unique.values()))
        _classify_clearing_settlement(line, row, method=method, confidence=Decimal("1.000"))
        return True
    if len(unique) > 1:
        line.status = "unmatched"
        line.exception_code = "AMBIGUOUS_CLEARING_SETTLEMENT"
        line.exception_reason = "Multiple electronic-clearing settlements share this bank reference"
        line.candidate_snapshot = [
            {
                "clearing_settlement_id": str(row.id),
                "provider_reference": row.reference,
                "proof_reference": dict(row.data or {}).get("proof_reference"),
                "amount": float(row.amount or 0),
            }
            for row, _ in unique.values()
        ]
        return True
    return False


def auto_match_line(db: Session, batch: ReconciliationBatch, line: ReconciliationLine) -> None:
    if line.source_kind != "external" or line.status in {"duplicate", "ignored"}:
        return
    if _match_bank_line_to_clearing_settlement(db, batch, line):
        return
    candidates: list[tuple[PaymentTransaction, str, Decimal]] = []
    reference = (line.reference or "").strip()
    payments = _payment_query(db, batch)
    if reference:
        exact = payments.filter(or_(PaymentTransaction.provider_reference == reference, PaymentTransaction.proof_reference == reference)).all()
        for payment in exact:
            method = "exact_provider_reference" if payment.provider_reference == reference else "exact_proof_reference"
            candidates.append((payment, method, Decimal("1.000")))
    if not candidates:
        tokens = _tokens(line)
        if tokens:
            loan_query = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.company_id == batch.company_id)
            if batch.branch_id:
                loan_query = loan_query.filter(ClientCompanyLoan.branch_id == batch.branch_id)
            loans = loan_query.filter(or_(ClientCompanyLoan.folio_number.in_(tokens), ClientCompanyLoan.loan_reference.in_(tokens))).all()
            if len(loans) == 1:
                loan = loans[0]
                start = datetime.combine(line.transaction_date - timedelta(days=3), datetime.min.time())
                end = datetime.combine(line.transaction_date + timedelta(days=4), datetime.min.time())
                matches = payments.filter(
                    PaymentTransaction.loan_id == loan.id,
                    PaymentTransaction.completed_at >= start,
                    PaymentTransaction.completed_at < end,
                    PaymentTransaction.amount == money(line.amount),
                ).all()
                if len(matches) == 1:
                    line.folio_number = loan.folio_number
                    candidates.append((matches[0], "exact_folio_or_loan_reference_unique_payment", Decimal("0.950")))
    unique = {item[0].id: item for item in candidates}
    if len(unique) == 1:
        payment, method, confidence = next(iter(unique.values()))
        _classify_amount(line, payment, method, confidence)
        return
    line.status = "unmatched"
    line.exception_code = "AMBIGUOUS_MATCH" if len(unique) > 1 else "NO_SAFE_MATCH"
    line.exception_reason = "Multiple safe payment candidates were found; manual review is required" if len(unique) > 1 else "No exact LoanHub payment match was found"
    line.candidate_snapshot = [_payment_payload(item[0]) for item in unique.values()]


def import_csv(db: Session, context: TenantContext, batch: ReconciliationBatch, content: bytes) -> dict[str, Any]:
    if batch.status in FINAL_BATCH_STATUSES:
        raise HTTPException(status_code=409, detail="Closed reconciliation batches are immutable")
    if batch.lines:
        raise HTTPException(status_code=409, detail="This batch already contains source rows. Create a new batch for a replacement import.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="Reconciliation CSV must be UTF-8 encoded") from exc
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=422, detail="CSV has no header row")
    headers = {normalize_header(item): item for item in reader.fieldnames}
    date_key = next((key for key in ("transaction_date", "date", "value_date") if key in headers), None)
    amount_key = next((key for key in ("amount", "transaction_amount", "credit_amount") if key in headers), None)
    if not date_key or not amount_key:
        raise HTTPException(status_code=422, detail="CSV must contain transaction_date/date and amount columns")

    seen: set[str] = set()
    imported_amount = Decimal("0.00")
    duplicate_count = 0
    now = datetime.now(timezone.utc)
    for row_number, raw in enumerate(reader, start=2):
        normalized = {normalize_header(k): str(v or "").strip() for k, v in raw.items() if k is not None}
        txn_date = parse_date(normalized.get(date_key, ""))
        if txn_date < batch.period_start or txn_date > batch.period_end:
            raise HTTPException(status_code=422, detail=f"CSV row {row_number} falls outside the reconciliation period")
        signed = money(normalized.get(amount_key, "0"))
        direction = (normalized.get("direction") or ("credit" if signed >= 0 else "debit")).lower()
        amount = abs(signed)
        reference = normalized.get("reference") or normalized.get("transaction_reference") or normalized.get("provider_reference") or None
        description = normalized.get("description") or normalized.get("narrative") or normalized.get("details") or None
        fingerprint = source_fingerprint(company_id=batch.company_id, source_type=batch.source_type, transaction_date=txn_date, reference=reference, description=description, amount=amount, direction=direction)
        duplicate = fingerprint in seen
        seen.add(fingerprint)
        line = ReconciliationLine(
            company_id=batch.company_id,
            batch_id=batch.id,
            source_kind="external",
            source_line_key=f"csv:{row_number}:{fingerprint[:16]}",
            transaction_date=txn_date,
            reference=reference,
            description=description,
            amount=amount,
            currency=(normalized.get("currency") or batch.currency).upper(),
            direction=direction,
            source_fingerprint=fingerprint,
            status="duplicate" if duplicate else "unmatched",
            exception_code="DUPLICATE_SOURCE_ROW" if duplicate else None,
            exception_reason="Duplicate row within the same imported source" if duplicate else None,
            source_payload=normalized,
        )
        db.add(line)
        db.flush()
        if duplicate:
            duplicate_count += 1
        elif direction == "credit":
            auto_match_line(db, batch, line)
        imported_amount += amount
    batch.imported_at = now
    batch.status = "imported"
    batch.imported_line_count = db.query(ReconciliationLine).filter(ReconciliationLine.batch_id == batch.id, ReconciliationLine.source_kind == "external").count()
    batch.duplicate_line_count = duplicate_count
    batch.imported_amount = money(imported_amount)
    _event(db, batch, "source_imported", context.user.id, payload={"lines": batch.imported_line_count, "duplicates": duplicate_count, "amount": str(batch.imported_amount)})
    db.commit()
    return summarize_batch(db, context, batch)


def _add_missing_clearing_settlement_lines(db: Session, batch: ReconciliationBatch) -> int:
    if batch.source_type != "bank_statement":
        return 0
    matched_ids = {
        str((row.source_payload or {}).get("matched_clearing_settlement_id"))
        for row in db.query(ReconciliationLine).filter(
            ReconciliationLine.batch_id == batch.id,
            ReconciliationLine.source_kind == "external",
        ).all()
        if (row.source_payload or {}).get("matched_clearing_settlement_id")
    }
    existing_expected = {
        str((row.source_payload or {}).get("clearing_settlement_id"))
        for row in db.query(ReconciliationLine).filter(
            ReconciliationLine.batch_id == batch.id,
            ReconciliationLine.source_kind == "system_expected",
        ).all()
        if (row.source_payload or {}).get("clearing_settlement_id")
    }

    created = 0
    for settlement in _clearing_settlement_query(db, batch).all():
        data = dict(settlement.data or {})
        settlement_date_text = data.get("settlement_date")
        if not settlement_date_text:
            continue
        settlement_date = date.fromisoformat(settlement_date_text)
        if settlement_date < batch.period_start or settlement_date > batch.period_end:
            continue
        sid = str(settlement.id)
        if sid in matched_ids or sid in existing_expected:
            continue
        direction = "credit" if data.get("direction") == "provider_to_bank" else "debit"
        db.add(ReconciliationLine(
            company_id=batch.company_id,
            batch_id=batch.id,
            source_kind="system_expected",
            source_line_key=f"clearing-settlement:{settlement.id}",
            transaction_date=settlement_date,
            reference=settlement.reference or data.get("proof_reference"),
            description="Electronic clearing settlement absent from imported bank statement",
            amount=money(settlement.amount),
            currency=settlement.currency,
            direction=direction,
            source_fingerprint=stable_sha256_text(
                correlation_id=f"reconciliation-clearing:{settlement.id}",
                payload=f"clearing-settlement:{settlement.id}",
            ),
            status="missing_source",
            expected_amount=money(settlement.amount),
            variance_amount=-money(settlement.amount),
            exception_code="MISSING_BANK_SETTLEMENT",
            exception_reason="Posted electronic clearing settlement was not present in the imported bank statement",
            source_payload={
                "clearing_settlement_id": sid,
                "journal_entry_id": data.get("journal_entry_id"),
                "provider_reference": settlement.reference,
                "proof_reference": data.get("proof_reference"),
                "direction": data.get("direction"),
            },
        ))
        created += 1
    return created


def _add_missing_source_lines(db: Session, batch: ReconciliationBatch) -> int:
    matched_ids = {row[0] for row in db.query(ReconciliationLine.matched_payment_id).filter(ReconciliationLine.batch_id == batch.id, ReconciliationLine.matched_payment_id.isnot(None)).all()}
    existing_system_ids = {row.source_payload.get("payment_id") for row in db.query(ReconciliationLine).filter(ReconciliationLine.batch_id == batch.id, ReconciliationLine.source_kind == "system_expected").all()}
    payments = _payment_query(db, batch).filter(
        PaymentTransaction.completed_at >= datetime.combine(batch.period_start, datetime.min.time()),
        PaymentTransaction.completed_at < datetime.combine(batch.period_end + timedelta(days=1), datetime.min.time()),
    ).all()
    created = 0
    for payment in payments:
        if payment.id in matched_ids or str(payment.id) in existing_system_ids:
            continue
        loan = db.get(ClientCompanyLoan, payment.loan_id) if payment.loan_id else None
        db.add(ReconciliationLine(
            company_id=batch.company_id,
            batch_id=batch.id,
            source_kind="system_expected",
            source_line_key=f"payment:{payment.id}",
            transaction_date=(payment.completed_at or payment.created_at).date(),
            reference=payment.provider_reference or payment.proof_reference,
            description="LoanHub successful inbound payment absent from imported reconciliation source",
            amount=money(payment.amount),
            currency=payment.currency,
            direction="credit",
            source_fingerprint=stable_sha256_text(
                correlation_id=f"reconciliation-payment:{payment.id}",
                payload=f"payment:{payment.id}",
            ),
            status="missing_source",
            matched_payment_id=payment.id,
            matched_loan_id=payment.loan_id,
            matched_borrower_id=payment.borrower_id,
            folio_number=loan.folio_number if loan else None,
            expected_amount=money(payment.amount),
            variance_amount=-money(payment.amount),
            exception_code="MISSING_EXTERNAL_SOURCE",
            exception_reason="Successful LoanHub payment was not present in the imported external source",
            source_payload={"payment_id": str(payment.id)},
        ))
        created += 1
    return created


def recalculate_batch(db: Session, batch: ReconciliationBatch) -> None:
    lines = db.query(ReconciliationLine).filter(ReconciliationLine.batch_id == batch.id).all()
    external = [row for row in lines if row.source_kind == "external"]
    batch.imported_line_count = len(external)
    batch.matched_line_count = sum(row.status == "matched" for row in external)
    batch.exception_line_count = sum(row.status in UNRESOLVED for row in lines)
    batch.duplicate_line_count = sum(row.status == "duplicate" for row in external)
    batch.missing_source_count = sum(row.status == "missing_source" for row in lines)
    batch.imported_amount = money(sum((money(row.amount) for row in external), Decimal("0")))
    batch.matched_amount = money(sum((money(row.amount) for row in external if row.status == "matched"), Decimal("0")))
    batch.shortage_amount = money(sum((-money(row.variance_amount) for row in lines if row.status == "shortage"), Decimal("0")))
    batch.excess_amount = money(sum((money(row.variance_amount) for row in lines if row.status == "excess"), Decimal("0")))
    batch.unmatched_amount = money(sum((money(row.amount) for row in lines if row.status in {"unmatched", "missing_source"}), Decimal("0")))


def reconcile(db: Session, context: TenantContext, batch: ReconciliationBatch) -> dict[str, Any]:
    if batch.status == "closed":
        raise HTTPException(status_code=409, detail="Closed reconciliation batches are immutable")
    if not batch.imported_at:
        raise HTTPException(status_code=409, detail="Import a reconciliation source before reconciling")
    for line in db.query(ReconciliationLine).filter(ReconciliationLine.batch_id == batch.id, ReconciliationLine.source_kind == "external", ReconciliationLine.status == "unmatched").all():
        auto_match_line(db, batch, line)
    created = _add_missing_source_lines(db, batch)
    clearing_created = _add_missing_clearing_settlement_lines(db, batch)
    db.flush()
    recalculate_batch(db, batch)
    batch.reconciled_at = datetime.now(timezone.utc)
    batch.reconciled_by_user_id = context.user.id
    batch.status = "exception" if batch.exception_line_count else "reconciled"
    _event(
        db,
        batch,
        "batch_reconciled",
        context.user.id,
        payload={
            "status": batch.status,
            "exceptions": batch.exception_line_count,
            "missing_source_added": created,
            "missing_clearing_settlements_added": clearing_created,
        },
    )
    db.commit()
    return summarize_batch(db, context, batch)


def manual_match(db: Session, context: TenantContext, batch: ReconciliationBatch, line: ReconciliationLine, *, payment_id: UUID, evidence_note: str) -> ReconciliationLine:
    if batch.status == "closed":
        raise HTTPException(status_code=409, detail="Closed reconciliation batches are immutable")
    if not evidence_note.strip():
        raise HTTPException(status_code=422, detail="A manual-match evidence note is required")
    payment = _payment_query(db, batch).filter(PaymentTransaction.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Eligible payment was not found in the active company/branch scope")
    _classify_amount(line, payment, "manual_evidence_match", Decimal("1.000"))
    line.is_manual_match = True
    line.matched_by_user_id = context.user.id
    line.resolution_note = evidence_note.strip()
    _event(db, batch, "manual_match_recorded", context.user.id, line_id=line.id, payload={"payment_id": str(payment.id), "note": evidence_note.strip(), "status": line.status})
    db.flush()
    recalculate_batch(db, batch)
    db.commit()
    db.refresh(line)
    return line


def resolve_line(db: Session, context: TenantContext, batch: ReconciliationBatch, line: ReconciliationLine, *, resolution: str, note: str) -> ReconciliationLine:
    if batch.status == "closed":
        raise HTTPException(status_code=409, detail="Closed reconciliation batches are immutable")
    if resolution not in {"ignored", "duplicate"}:
        raise HTTPException(status_code=422, detail="Resolution must be ignored or duplicate")
    if not note.strip():
        raise HTTPException(status_code=422, detail="A reconciliation resolution note is required")
    previous = line.status
    line.status = resolution
    line.resolution_note = note.strip()
    line.resolved_by_user_id = context.user.id
    line.resolved_at = datetime.now(timezone.utc)
    _event(db, batch, "line_resolved", context.user.id, line_id=line.id, payload={"previous": previous, "resolution": resolution, "note": note.strip()})
    db.flush()
    recalculate_batch(db, batch)
    db.commit()
    db.refresh(line)
    return line


def request_adjustment(db: Session, context: TenantContext, batch: ReconciliationBatch, line: ReconciliationLine, *, adjustment_type: str, amount: Decimal, reason: str) -> PaymentAdjustment:
    if batch.status == "closed":
        raise HTTPException(status_code=409, detail="Closed reconciliation batches are immutable")
    if not line.matched_payment_id:
        raise HTTPException(status_code=409, detail="A payment must be identified before requesting an adjustment")
    if not reason.strip():
        raise HTTPException(status_code=422, detail="An adjustment reason is required")
    key = f"reconciliation:{batch.id}:{line.id}:{adjustment_type}:{money(amount)}"
    approval = ApprovalRequest(
        company_id=batch.company_id,
        branch_id=batch.branch_id,
        action_type="payment_adjustment",
        resource_type="reconciliation_line",
        resource_id=str(line.id),
        payload={"batch_id": str(batch.id), "line_id": str(line.id), "payment_id": str(line.matched_payment_id), "adjustment_type": adjustment_type, "amount": str(money(amount))},
        status="pending",
        idempotency_key=key,
        requested_by_user_id=context.user.id,
    )
    db.add(approval)
    db.flush()
    adjustment = PaymentAdjustment(
        company_id=batch.company_id,
        payment_id=line.matched_payment_id,
        approval_request_id=approval.id,
        adjustment_type=adjustment_type,
        amount=money(amount),
        currency=line.currency,
        reason=reason.strip(),
        status="pending_approval",
        idempotency_key=key,
        requested_by_user_id=context.user.id,
    )
    db.add(adjustment)
    db.flush()
    line.payment_adjustment_id = adjustment.id
    line.status = "adjustment_required"
    line.resolution_note = reason.strip()
    _event(db, batch, "adjustment_requested", context.user.id, line_id=line.id, payload={"adjustment_id": str(adjustment.id), "approval_request_id": str(approval.id), "amount": str(adjustment.amount), "type": adjustment_type})
    db.flush()
    recalculate_batch(db, batch)
    db.commit()
    db.refresh(adjustment)
    return adjustment


def set_bank_statement_balances(
    db: Session,
    context: TenantContext,
    batch: ReconciliationBatch,
    *,
    opening_balance: Decimal,
    closing_balance: Decimal,
) -> ReconciliationBatch:
    if batch.source_type != "bank_statement":
        raise HTTPException(status_code=422, detail="Statement balances apply only to bank-statement reconciliation batches")
    if batch.status == "closed":
        raise HTTPException(status_code=409, detail="Closed reconciliation batches are immutable")

    methodology = dict(batch.methodology_snapshot or {})
    methodology["bank_statement_balances"] = {
        "opening_balance": str(money(opening_balance)),
        "closing_balance": str(money(closing_balance)),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "recorded_by_user_id": str(context.user.id),
    }
    batch.methodology_snapshot = methodology
    _event(
        db,
        batch,
        "bank_statement_balances_recorded",
        context.user.id,
        payload=methodology["bank_statement_balances"],
    )
    db.commit()
    db.refresh(batch)
    return batch


def bank_statement_balance_reconciliation(
    db: Session,
    batch: ReconciliationBatch,
) -> dict[str, Any]:
    if batch.source_type != "bank_statement":
        raise HTTPException(status_code=422, detail="Balance reconciliation applies only to bank-statement batches")

    declared = dict(batch.methodology_snapshot or {}).get("bank_statement_balances") or {}
    if "opening_balance" not in declared or "closing_balance" not in declared:
        return {
            "configured": False,
            "balanced": False,
            "reason": "Record the bank statement opening and closing balances",
        }

    statement_opening = money(declared["opening_balance"])
    statement_closing = money(declared["closing_balance"])
    lines = db.query(ReconciliationLine).filter(
        ReconciliationLine.batch_id == batch.id,
    ).all()
    external = [row for row in lines if row.source_kind == "external" and row.status != "duplicate"]

    statement_net = Decimal("0.00")
    for line in external:
        signed = money(line.amount) if line.direction == "credit" else -money(line.amount)
        statement_net += signed
    statement_net = money(statement_net)
    calculated_statement_closing = money(statement_opening + statement_net)
    statement_arithmetic_difference = money(statement_closing - calculated_statement_closing)

    scope_key_value = f"company:{batch.company_id}"
    bank_account = db.query(AccountingAccount).filter(
        AccountingAccount.scope_key == scope_key_value,
        AccountingAccount.code == "1010",
        AccountingAccount.is_active.is_(True),
    ).first()
    if not bank_account:
        return {
            "configured": True,
            "balanced": False,
            "reason": "Bank ledger account 1010 is not configured",
        }

    opening_q = db.query(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
        JournalLine.account_id == bank_account.id,
        JournalEntry.scope_key == scope_key_value,
        JournalEntry.status == "posted",
        JournalEntry.entry_date < batch.period_start,
    )
    closing_q = db.query(
        func.coalesce(func.sum(JournalLine.debit), 0),
        func.coalesce(func.sum(JournalLine.credit), 0),
    ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
        JournalLine.account_id == bank_account.id,
        JournalEntry.scope_key == scope_key_value,
        JournalEntry.status == "posted",
        JournalEntry.entry_date <= batch.period_end,
    )
    if batch.branch_id:
        opening_q = opening_q.filter(JournalEntry.branch_id == batch.branch_id)
        closing_q = closing_q.filter(JournalEntry.branch_id == batch.branch_id)
    opening_debit, opening_credit = opening_q.first()
    closing_debit, closing_credit = closing_q.first()
    ledger_opening = money(Decimal(opening_debit) - Decimal(opening_credit))
    ledger_closing = money(Decimal(closing_debit) - Decimal(closing_credit))
    ledger_movement = money(ledger_closing - ledger_opening)

    timing_adjustment = Decimal("0.00")
    timing_items = []
    for line in lines:
        if line.status != "ignored":
            continue
        signed = money(line.amount) if line.direction == "credit" else -money(line.amount)
        if line.source_kind == "system_expected":
            adjustment = signed
            kind = "ledger_item_not_yet_on_bank_statement"
        elif line.source_kind == "external":
            adjustment = -signed
            kind = "bank_statement_item_excluded_from_ledger"
        else:
            continue
        timing_adjustment += adjustment
        timing_items.append({
            "line_id": str(line.id),
            "source_kind": line.source_kind,
            "direction": line.direction,
            "amount": float(money(line.amount)),
            "adjustment": float(money(adjustment)),
            "reason": line.resolution_note,
            "kind": kind,
        })
    timing_adjustment = money(timing_adjustment)
    statement_reconciled_to_ledger = money(statement_closing + timing_adjustment)
    ledger_difference = money(ledger_closing - statement_reconciled_to_ledger)

    return {
        "configured": True,
        "batch_id": str(batch.id),
        "batch_reference": batch.batch_reference,
        "period_start": batch.period_start.isoformat(),
        "period_end": batch.period_end.isoformat(),
        "statement_opening_balance": float(statement_opening),
        "statement_net_movement": float(statement_net),
        "calculated_statement_closing_balance": float(calculated_statement_closing),
        "statement_closing_balance": float(statement_closing),
        "statement_arithmetic_difference": float(statement_arithmetic_difference),
        "statement_arithmetic_balanced": statement_arithmetic_difference == 0,
        "ledger_opening_balance": float(ledger_opening),
        "ledger_net_movement": float(ledger_movement),
        "ledger_closing_balance": float(ledger_closing),
        "timing_adjustment": float(timing_adjustment),
        "statement_reconciled_to_ledger": float(statement_reconciled_to_ledger),
        "ledger_difference": float(ledger_difference),
        "balanced": statement_arithmetic_difference == 0 and ledger_difference == 0,
        "timing_items": timing_items,
    }


def close_batch(db: Session, context: TenantContext, batch: ReconciliationBatch, *, note: str) -> ReconciliationBatch:
    if batch.status == "closed":
        return batch
    recalculate_batch(db, batch)
    if batch.exception_line_count:
        raise HTTPException(status_code=409, detail=f"{batch.exception_line_count} unresolved reconciliation exception(s) must be cleared before close-off")
    if batch.status not in {"reconciled", "exception"}:
        raise HTTPException(status_code=409, detail="Run reconciliation before closing the batch")
    if batch.source_type == "bank_statement":
        balance_control = bank_statement_balance_reconciliation(db, batch)
        if not balance_control.get("balanced"):
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Bank statement balances do not reconcile to account 1010",
                    "balance_reconciliation": balance_control,
                },
            )
    if not note.strip():
        raise HTTPException(status_code=422, detail="A close-off note is required")
    batch.status = "closed"
    batch.closed_at = datetime.now(timezone.utc)
    batch.closed_by_user_id = context.user.id
    batch.close_note = note.strip()
    _event(db, batch, "batch_closed", context.user.id, payload={"close_note": note.strip()})
    db.commit()
    db.refresh(batch)
    return batch


def line_payload(row: ReconciliationLine) -> dict[str, Any]:
    return {
        "id": str(row.id), "source_kind": row.source_kind, "transaction_date": row.transaction_date.isoformat(),
        "reference": row.reference, "description": row.description, "amount": float(row.amount or 0), "currency": row.currency,
        "direction": row.direction, "status": row.status, "match_method": row.match_method,
        "match_confidence": float(row.match_confidence) if row.match_confidence is not None else None,
        "matched_payment_id": str(row.matched_payment_id) if row.matched_payment_id else None,
        "matched_loan_id": str(row.matched_loan_id) if row.matched_loan_id else None,
        "folio_number": row.folio_number, "expected_amount": float(row.expected_amount) if row.expected_amount is not None else None,
        "variance_amount": float(row.variance_amount or 0), "exception_code": row.exception_code, "exception_reason": row.exception_reason,
        "candidate_snapshot": row.candidate_snapshot or [], "is_manual_match": bool(row.is_manual_match),
        "resolution_note": row.resolution_note, "payment_adjustment_id": str(row.payment_adjustment_id) if row.payment_adjustment_id else None,
    }


def batch_payload(batch: ReconciliationBatch) -> dict[str, Any]:
    return {
        "id": str(batch.id), "batch_reference": batch.batch_reference, "source_type": batch.source_type,
        "source_reference": batch.source_reference, "account_reference": batch.account_reference,
        "period_start": batch.period_start.isoformat(), "period_end": batch.period_end.isoformat(), "currency": batch.currency,
        "status": batch.status, "imported_line_count": batch.imported_line_count, "matched_line_count": batch.matched_line_count,
        "exception_line_count": batch.exception_line_count, "duplicate_line_count": batch.duplicate_line_count,
        "missing_source_count": batch.missing_source_count, "imported_amount": float(batch.imported_amount or 0),
        "matched_amount": float(batch.matched_amount or 0), "shortage_amount": float(batch.shortage_amount or 0),
        "excess_amount": float(batch.excess_amount or 0), "unmatched_amount": float(batch.unmatched_amount or 0),
        "imported_at": batch.imported_at.isoformat() if batch.imported_at else None,
        "reconciled_at": batch.reconciled_at.isoformat() if batch.reconciled_at else None,
        "closed_at": batch.closed_at.isoformat() if batch.closed_at else None, "close_note": batch.close_note,
    }


def summarize_batch(db: Session, context: TenantContext, batch: ReconciliationBatch) -> dict[str, Any]:
    recalculate_batch(db, batch)
    lines = db.query(ReconciliationLine).filter(ReconciliationLine.batch_id == batch.id).order_by(ReconciliationLine.transaction_date.asc(), ReconciliationLine.created_at.asc()).all()
    return {**batch_payload(batch), "lines": [line_payload(row) for row in lines]}


def dashboard(db: Session, context: TenantContext) -> dict[str, Any]:
    query = db.query(ReconciliationBatch).filter(ReconciliationBatch.company_id == context.company_id)
    if context.branch_id:
        query = query.filter(ReconciliationBatch.branch_id == context.branch_id)
    rows = query.order_by(ReconciliationBatch.created_at.desc()).limit(200).all()
    return {
        "summary": {
            "open_batches": sum(row.status != "closed" for row in rows),
            "exception_batches": sum(row.status == "exception" for row in rows),
            "unresolved_exceptions": sum(int(row.exception_line_count or 0) for row in rows if row.status != "closed"),
            "shortage_amount": float(money(sum((money(row.shortage_amount) for row in rows if row.status != "closed"), Decimal("0")))),
            "excess_amount": float(money(sum((money(row.excess_amount) for row in rows if row.status != "closed"), Decimal("0")))),
            "unmatched_amount": float(money(sum((money(row.unmatched_amount) for row in rows if row.status != "closed"), Decimal("0")))),
        },
        "batches": [batch_payload(row) for row in rows],
    }


def export_csv(db: Session, batch: ReconciliationBatch) -> str:
    stream = StringIO()
    writer = csv.writer(stream)
    writer.writerow(["LoanHub Reconciliation", batch.batch_reference])
    writer.writerow(["Source", batch.source_type, "Period", batch.period_start.isoformat(), batch.period_end.isoformat(), "Status", batch.status])
    writer.writerow([])
    writer.writerow(["Date", "Reference", "Description", "Amount", "Direction", "Status", "Match method", "Payment ID", "Folio", "Expected", "Variance", "Exception", "Resolution"])
    for row in db.query(ReconciliationLine).filter(ReconciliationLine.batch_id == batch.id).order_by(ReconciliationLine.transaction_date.asc()).all():
        writer.writerow([row.transaction_date.isoformat(), row.reference, row.description, row.amount, row.direction, row.status, row.match_method, row.matched_payment_id, row.folio_number, row.expected_amount, row.variance_amount, row.exception_reason, row.resolution_note])
    return stream.getvalue()
