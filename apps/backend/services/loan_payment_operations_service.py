from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.accounting import JournalEntry
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import (
    InstallmentStatus,
    LoanStatus,
    NotificationType,
    PaymentDirection,
    PaymentMethod,
    PaymentProvider,
    PaymentPurpose,
    PaymentStatus,
)
from database.models.loan_payment_operations import (
    AccountingExport,
    BorrowerReminderPreference,
    LoanRestructureRequest,
    OnlineRepaymentMandate,
    RepaymentReminder,
)
from database.models.notification import Notification
from database.models.payment import PaymentTransaction
from database.models.repayment import RepaymentInstallment
from integrations.lelefa_paygate import LelefaPayGateClient, LelefaPayGateError
from services.interest_calculation_service import calculate_loan_terms, generate_monthly_due_dates


MONEY = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY)


def create_online_mandate(db: Session, *, loan: ClientCompanyLoan, user_id: UUID, payload) -> OnlineRepaymentMandate:
    if loan.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}:
        raise HTTPException(status_code=409, detail="Only an active or defaulted loan can use automatic repayment")
    if money(payload.amount) > money(loan.balance):
        raise HTTPException(status_code=422, detail="Mandate amount cannot exceed the outstanding loan balance")
    active = db.query(OnlineRepaymentMandate).filter(
        OnlineRepaymentMandate.loan_id == loan.id,
        OnlineRepaymentMandate.status.in_(["processing", "active", "approved"]),
    ).first()
    if active:
        return active
    phone = loan.borrower.user.phone if loan.borrower and loan.borrower.user else None
    if not phone:
        raise HTTPException(status_code=422, detail="A verified borrower phone number is required")
    row = OnlineRepaymentMandate(
        company_id=loan.company_id, borrower_id=loan.borrower_id, loan_id=loan.id,
        provider=payload.provider.strip().lower(), status="processing", amount=money(payload.amount),
        next_debit_date=payload.first_debit_date, expiry_date=payload.expiry_date,
        max_debits=loan.repayment_period, consent_reference=payload.consent_reference.strip(),
        consented_at=datetime.now(timezone.utc), metadata_json={"source": "LoanHub borrower portal"},
    )
    db.add(row); db.commit(); db.refresh(row)
    try:
        response = LelefaPayGateClient().create_mandate(
            provider=row.provider, phone=phone, reference=f"LH{loan.id.hex[:26]}",
            first_payment_date=payload.first_debit_date, expiry_date=payload.expiry_date,
            metadata={"loanhub_mandate_id": str(row.id), "loan_id": str(loan.id), "borrower_id": str(loan.borrower_id)},
            idempotency_key=f"loanhub-mandate-{row.id}",
        )
    except LelefaPayGateError as exc:
        row.status = "processing" if exc.retryable else "failed"
        row.failure_reason = exc.detail
        db.add(row); db.commit(); db.refresh(row)
        if not exc.retryable:
            raise HTTPException(status_code=exc.status_code or 502, detail=f"LelefaPayGate mandate failed: {exc.detail}") from exc
        return row
    row.gateway_mandate_id = str(response.get("public_id") or response.get("id") or "") or None
    row.status = str(response.get("status") or "processing")
    row.metadata_json = {**(row.metadata_json or {}), "gateway_status": row.status}
    db.add(row); db.commit(); db.refresh(row)
    return row


def cancel_online_mandate(db: Session, *, row: OnlineRepaymentMandate) -> OnlineRepaymentMandate:
    if row.status in {"cancelled", "completed", "failed"}:
        return row
    if row.gateway_mandate_id:
        try:
            response = LelefaPayGateClient().cancel_mandate(row.gateway_mandate_id)
            row.status = str(response.get("status") or "cancelled")
        except LelefaPayGateError as exc:
            if exc.retryable:
                raise HTTPException(status_code=503, detail="Mandate cancellation outcome is unknown; retry safely") from exc
            raise HTTPException(status_code=exc.status_code or 502, detail=exc.detail) from exc
    else:
        row.status = "cancelled"
    row.revoked_at = datetime.now(timezone.utc)
    db.add(row); db.commit(); db.refresh(row)
    return row


def run_due_mandate_collections(db: Session, *, company_id: UUID, user_id: UUID) -> dict:
    """Create each due debit once and let the signed gateway result post the loan."""
    today = date.today()
    created = 0
    succeeded = 0
    processing = 0
    failed = 0
    rows = db.query(OnlineRepaymentMandate).filter(
        OnlineRepaymentMandate.company_id == company_id,
        OnlineRepaymentMandate.status == "active",
        OnlineRepaymentMandate.next_debit_date <= today,
    ).all()
    for row in rows:
        if not row.gateway_mandate_id:
            row.status = "failed"
            row.failure_reason = "Active mandate is missing its gateway resource ID"
            db.add(row)
            failed += 1
            continue
        loan = db.get(ClientCompanyLoan, row.loan_id)
        if not loan or loan.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED} or money(loan.balance) <= 0:
            row.status = "completed"
            db.add(row)
            continue
        debit_date = row.next_debit_date or today
        key = f"mandate-charge:{row.id}:{debit_date.isoformat()}"
        existing = db.query(PaymentTransaction).filter(PaymentTransaction.idempotency_key == key).first()
        if existing:
            continue
        amount = min(money(row.amount), money(loan.balance))
        payment = PaymentTransaction(
            company_id=loan.company_id,
            borrower_id=loan.borrower_id,
            loan_request_id=loan.loan_request_id,
            loan_id=loan.id,
            initiated_by_user_id=user_id,
            provider=PaymentProvider.LELEFAPAYGATE,
            payment_method=PaymentMethod.LELEFAPAYGATE,
            direction=PaymentDirection.INBOUND,
            purpose=PaymentPurpose.LOAN_REPAYMENT,
            status=PaymentStatus.PROCESSING,
            amount=amount,
            currency="LSL",
            configuration_scope="server",
            provider_operation="mandate_charge",
            idempotency_key=key,
            provider_reference=f"LPG-PENDING-{row.id.hex.upper()}-{debit_date:%Y%m%d}",
            provider_payload={
                "gateway": "lelefapaygate",
                "resource_type": "mandate_charge",
                "gateway_mandate_id": row.gateway_mandate_id,
                "loanhub_mandate_id": str(row.id),
                "branch_id": str(loan.branch_id) if loan.branch_id else None,
            },
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)
        created += 1
        try:
            response = LelefaPayGateClient().charge_mandate(
                row.gateway_mandate_id,
                amount=f"{amount:.2f}",
                reference=f"LH-{loan.loan_reference}-{debit_date:%Y%m%d}"[:100],
                idempotency_key=key,
            )
            public_id = str(response.get("public_id") or response.get("id") or "").strip()
            if not public_id:
                raise LelefaPayGateError("Mandate charge did not return a resource ID")
            payment.provider_reference = public_id
            payment.provider_payload = {
                **(payment.provider_payload or {}),
                "gateway_public_id": public_id,
                "gateway_status": response.get("status"),
            }
            from services.lelefa_paygate_service import apply_gateway_resource

            apply_gateway_resource(db, payment, response)
            if payment.status == PaymentStatus.SUCCEEDED:
                row.debits_completed += 1
                succeeded += 1
            else:
                processing += 1
            future = sorted(
                item.due_date for item in loan.installments
                if not item.is_superseded
                and item.status not in {InstallmentStatus.PAID, InstallmentStatus.WAIVED}
                and item.due_date > debit_date
            )
            row.next_debit_date = future[0] if future else None
            if row.next_debit_date is None or (row.max_debits and row.debits_completed >= row.max_debits):
                row.status = "completed" if payment.status == PaymentStatus.SUCCEEDED else row.status
            db.add(row)
            db.add(payment)
            db.commit()
        except (LelefaPayGateError, HTTPException) as exc:
            payment.status = PaymentStatus.PROCESSING if getattr(exc, "retryable", False) else PaymentStatus.FAILED
            payment.failure_reason = str(getattr(exc, "detail", exc))[:1000]
            db.add(payment)
            db.commit()
            processing += int(payment.status == PaymentStatus.PROCESSING)
            failed += int(payment.status == PaymentStatus.FAILED)
    db.commit()
    return {"created": created, "succeeded": succeeded, "processing": processing, "failed": failed}


def schedule_repayment_reminders(db: Session, *, company_id: UUID, run_by_user_id: UUID) -> dict:
    today = date.today()
    created = 0
    configuration_required = 0
    loans = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
    ).all()
    for loan in loans:
        preference = db.query(BorrowerReminderPreference).filter(
            BorrowerReminderPreference.company_id == company_id,
            BorrowerReminderPreference.borrower_id == loan.borrower_id,
        ).first()
        if not preference:
            preference = BorrowerReminderPreference(company_id=company_id, borrower_id=loan.borrower_id)
            db.add(preference); db.flush()
        channels = []
        if preference.in_app_enabled: channels.append("in_app")
        if preference.sms_enabled: channels.append("sms")
        if preference.email_enabled: channels.append("email")
        if preference.whatsapp_enabled: channels.append("whatsapp")
        for installment in loan.installments:
            if installment.is_superseded or installment.status in {InstallmentStatus.PAID, InstallmentStatus.WAIVED}:
                continue
            days = (installment.due_date - today).days
            if days > preference.days_before_due:
                continue
            if days == 0 and not preference.remind_on_due_date:
                continue
            if days < 0 and abs(days) % preference.overdue_interval_days != 0:
                continue
            kind = "overdue" if days < 0 else "due_today" if days == 0 else "upcoming"
            amount = money(installment.total_due - installment.paid_amount)
            message = f"Loan {loan.loan_reference}: {amount:.2f} LSL is {kind.replace('_', ' ')} for instalment {installment.installment_number}."
            for channel in channels:
                key = f"repayment:{installment.id}:{channel}:{kind}:{today.isoformat()}"
                if db.query(RepaymentReminder.id).filter(RepaymentReminder.deduplication_key == key).first():
                    continue
                status = "sent" if channel == "in_app" else "configuration_required"
                row = RepaymentReminder(
                    company_id=company_id, borrower_id=loan.borrower_id, loan_id=loan.id,
                    installment_id=installment.id, channel=channel, reminder_type=kind,
                    scheduled_for=datetime.now(timezone.utc), status=status, deduplication_key=key,
                    message=message, sent_at=datetime.now(timezone.utc) if status == "sent" else None,
                    failure_reason=None if status == "sent" else "Configure an approved external messaging connector",
                    metadata_json={"payment_url": "/borrower/payments" if preference.payment_link_enabled else None},
                )
                db.add(row)
                if channel == "in_app" and loan.borrower and loan.borrower.user_id:
                    db.add(Notification(
                        user_id=loan.borrower.user_id, company_id=company_id, branch_id=loan.branch_id,
                        title="Loan repayment reminder", message=message, notification_type=NotificationType.SYSTEM,
                        event_type="loan.repayment.reminder", action="view", entity_type="loan",
                        entity_id=str(loan.id), action_url="/borrower/payments", icon="wallet-cards",
                        priority="high" if days <= 0 else "normal", data={"loan_reference": loan.loan_reference, "amount": str(amount)},
                        deduplication_key=key,
                    ))
                created += 1
                configuration_required += int(status == "configuration_required")
    db.commit()
    return {"created": created, "configuration_required": configuration_required}


def create_restructure_request(db: Session, *, loan: ClientCompanyLoan, user_id: UUID, payload) -> LoanRestructureRequest:
    if loan.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}:
        raise HTTPException(status_code=409, detail="Only active or defaulted loans can be restructured")
    existing = db.query(LoanRestructureRequest).filter(
        LoanRestructureRequest.loan_id == loan.id,
        LoanRestructureRequest.status.in_(["requested", "approved"]),
    ).first()
    if existing:
        return existing
    start = date.today() + timedelta(days=payload.payment_holiday_days)
    due_dates = generate_monthly_due_dates(start, payload.requested_term_months)
    installment, total, details = calculate_loan_terms(
        principal=money(loan.balance), rate_percent=Decimal(str(loan.interest_rate)),
        term_months=payload.requested_term_months, processing_fee=Decimal("0"),
        interest_method=loan.calculation_method, start_date=start, due_dates=due_dates,
    )
    row = LoanRestructureRequest(
        company_id=loan.company_id, borrower_id=loan.borrower_id, loan_id=loan.id,
        requested_term_months=payload.requested_term_months, payment_holiday_days=payload.payment_holiday_days,
        reason=payload.reason.strip(), borrower_accepted=payload.borrower_accepted,
        requested_by_user_id=user_id,
        original_snapshot={"balance": str(money(loan.balance)), "total_repayable": str(money(loan.total_repayable)), "term_months": loan.repayment_period, "installment_amount": str(money(loan.installment_amount)), "maturity_date": loan.maturity_date.isoformat() if loan.maturity_date else None, "calculation_breakdown": loan.calculation_breakdown or {}},
        preview={**details, "monthly_installment": str(installment), "restructured_balance": str(total)},
    )
    db.add(row); db.commit(); db.refresh(row)
    return row


def approve_restructure(db: Session, *, row: LoanRestructureRequest, user_id: UUID, approved_rate: Decimal | None, agreement_reference: str) -> LoanRestructureRequest:
    if row.status != "requested" or not row.borrower_accepted:
        raise HTTPException(status_code=409, detail="Only an accepted pending restructure request can be approved")
    loan = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.id == row.loan_id).with_for_update().first()
    if not loan or loan.status not in {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}:
        raise HTTPException(status_code=409, detail="The loan is no longer eligible for restructuring")
    if money(loan.balance) != money(row.original_snapshot.get("balance")):
        raise HTTPException(status_code=409, detail="The loan balance changed; create a fresh restructure request")
    rate = Decimal(str(approved_rate if approved_rate is not None else loan.interest_rate))
    start = date.today() + timedelta(days=row.payment_holiday_days)
    due_dates = generate_monthly_due_dates(start, row.requested_term_months)
    installment, total, details = calculate_loan_terms(
        principal=money(loan.balance), rate_percent=rate, term_months=row.requested_term_months,
        processing_fee=Decimal("0"), interest_method=loan.calculation_method, start_date=start, due_dates=due_dates,
    )
    now = datetime.now(timezone.utc)
    max_number = max((item.installment_number for item in loan.installments), default=0)
    for item in loan.installments:
        if not item.is_superseded and item.status not in {InstallmentStatus.PAID, InstallmentStatus.WAIVED}:
            item.is_superseded = True
            item.superseded_at = now
            db.add(item)
    for offset, schedule in enumerate(details["schedule_rows"], start=1):
        db.add(RepaymentInstallment(
            loan_id=loan.id, installment_number=max_number + offset, due_date=date.fromisoformat(schedule["due_date"]),
            principal_due=money(schedule["principal_due"]), interest_due=money(schedule["interest_due"]),
            fee_due=money(schedule["fee_due"]), total_due=money(schedule["total_due"]), paid_amount=Decimal("0"),
            status=InstallmentStatus.PENDING,
        ))
    loan.interest_rate = rate
    loan.repayment_period = row.requested_term_months
    loan.installment_amount = installment
    loan.balance = total
    loan.total_repayable = money(loan.amount_paid) + total
    loan.first_payment_due = due_dates[0]
    loan.maturity_date = due_dates[-1]
    loan.calculation_breakdown = {**details, "restructure_request_id": str(row.id), "previous_contract": row.original_snapshot}
    row.status = "applied"
    row.approved_rate_percent = rate
    row.approved_by_user_id = user_id
    row.approved_at = now
    row.applied_at = now
    row.agreement_reference = agreement_reference.strip()
    row.preview = {**details, "monthly_installment": str(installment), "restructured_balance": str(total)}
    db.add(loan); db.add(row); db.commit(); db.refresh(row)
    return row


def create_accounting_export(db: Session, *, company_id: UUID, user_id: UUID, payload) -> AccountingExport:
    entries = db.query(JournalEntry).filter(
        JournalEntry.company_id == company_id,
        JournalEntry.entry_date >= payload.period_start,
        JournalEntry.entry_date <= payload.period_end,
        JournalEntry.status == "posted",
    ).order_by(JournalEntry.entry_date, JournalEntry.entry_number).limit(5000).all()
    rows = [{"entry_number": item.entry_number, "date": item.entry_date.isoformat(), "description": item.description, "reference_type": item.reference_type, "reference_id": item.reference_id, "debit": str(money(item.total_debit)), "credit": str(money(item.total_credit))} for item in entries]
    total_debit = money(sum((money(item.total_debit) for item in entries), Decimal("0")))
    total_credit = money(sum((money(item.total_credit) for item in entries), Decimal("0")))
    status = "ready" if payload.destination == "manual" else "configuration_required"
    row = AccountingExport(
        company_id=company_id, period_start=payload.period_start, period_end=payload.period_end,
        format=payload.format, destination=payload.destination, status=status, entry_count=len(entries),
        total_debit=total_debit, total_credit=total_credit,
        payload={"schema": "loanhub.accounting.v1", "balanced": total_debit == total_credit, "entries": rows},
        generated_by_user_id=user_id, generated_at=datetime.now(timezone.utc),
        failure_reason=None if status == "ready" else "Configure an approved accounting connector before delivery",
    )
    db.add(row); db.commit(); db.refresh(row)
    return row
