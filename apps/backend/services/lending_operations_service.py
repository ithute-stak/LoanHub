from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from database.models.accounting import JournalEntry
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus, PaymentMethod, PaymentPurpose, PaymentStatus
from database.models.lending_operations import (
    CDASDeductionMandate,
    CDASPayrollProfile,
    CDASRemittanceBatch,
    CDASRemittanceLine,
    CollectionCase,
    ComplianceCase,
    CreditBureauEnquiry,
    CreditDecision,
    CreditDecisionPolicy,
    ReconciliationException,
    ReconciliationRun,
    RegulatorySubmission,
    WorkflowInstance,
    WorkflowTemplate,
)
from database.models.origination import BorrowerEmploymentProfile, BorrowerKYCProfile
from database.models.payment import PaymentTransaction
from database.models.professional_lending import DirectLoanApplication, PaymentReceipt
from database.models.repayment import PaymentAllocation, RepaymentInstallment
from services.loan_service import record_cash_repayment

MONEY = Decimal("0.01")


def money(value: Any) -> Decimal:
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def make_reference(prefix: str) -> str:
    now = datetime.now(timezone.utc)
    return f"{prefix}-{now:%Y%m%d%H%M%S}-{uuid4().hex[:8].upper()}"


def calculate_cdas_affordability(
    *,
    net_salary: Decimal,
    existing_deductions: Decimal,
    proposed_deduction: Decimal,
    maximum_deduction_percent: Decimal,
    minimum_take_home: Decimal = Decimal("0"),
) -> dict[str, Any]:
    net_salary = money(net_salary)
    existing_deductions = money(existing_deductions)
    proposed_deduction = money(proposed_deduction)
    maximum_deduction_percent = Decimal(maximum_deduction_percent or 0)
    maximum_total = money(net_salary * maximum_deduction_percent / Decimal("100"))
    total_after = money(existing_deductions + proposed_deduction)
    take_home_after = money(net_salary - total_after)
    available_capacity = money(max(maximum_total - existing_deductions, Decimal("0")))
    ratio = Decimal("0") if net_salary <= 0 else (total_after / net_salary * Decimal("100")).quantize(Decimal("0.001"))
    reasons: list[str] = []
    if net_salary <= 0:
        reasons.append("Verified net salary must be greater than zero.")
    if proposed_deduction > available_capacity:
        reasons.append("The proposed deduction exceeds the available payroll-deduction capacity.")
    if take_home_after < money(minimum_take_home):
        reasons.append("The remaining take-home pay is below the configured minimum.")
    return {
        "affordable": not reasons,
        "net_salary": net_salary,
        "existing_deductions": existing_deductions,
        "proposed_deduction": proposed_deduction,
        "maximum_total_deductions": maximum_total,
        "total_deductions_after": total_after,
        "take_home_after": take_home_after,
        "available_deduction_capacity": available_capacity,
        "deduction_ratio_percent": ratio,
        "reasons": reasons,
    }


def reconcile_cdas_batch(db: Session, batch: CDASRemittanceBatch, user_id: UUID) -> ReconciliationRun:
    if batch.status == "reconciled":
        existing = (
            db.query(ReconciliationRun)
            .filter(
                ReconciliationRun.company_id == batch.company_id,
                ReconciliationRun.run_type == "cdas",
                ReconciliationRun.summary["batch_id"].astext == str(batch.id),
            )
            .order_by(ReconciliationRun.created_at.desc())
            .first()
        )
        if existing:
            return existing

    run = ReconciliationRun(
        company_id=batch.company_id,
        run_reference=make_reference("REC-CDAS"),
        run_type="cdas",
        period_start=batch.payroll_month,
        period_end=batch.payroll_month,
        status="running",
        started_at=datetime.now(timezone.utc),
        created_by_user_id=user_id,
        summary={"batch_id": str(batch.id), "batch_reference": batch.batch_reference},
    )
    db.add(run)
    db.flush()

    lines = db.query(CDASRemittanceLine).filter(CDASRemittanceLine.batch_id == batch.id).all()
    matched_amount = Decimal("0")
    exception_amount = Decimal("0")
    matched_count = 0
    exception_count = 0

    for line in lines:
        mandate = (
            db.query(CDASDeductionMandate)
            .filter(
                CDASDeductionMandate.company_id == batch.company_id,
                CDASDeductionMandate.employee_number == line.employee_number,
                CDASDeductionMandate.status.in_(["accepted", "active", "rescheduled"]),
            )
            .order_by(CDASDeductionMandate.created_at.desc())
            .first()
        )
        if not mandate:
            line.status = "unmatched"
            line.reason = "No active CDAS mandate matches this employee number."
            line.variance_amount = money(line.deducted_amount)
            exception_count += 1
            exception_amount += money(line.deducted_amount)
            db.add(
                ReconciliationException(
                    run_id=run.id,
                    company_id=batch.company_id,
                    exception_type="unknown_employee_or_mandate",
                    severity="high",
                    source_entity_type="cdas_remittance_line",
                    source_entity_id=line.id,
                    reference=line.line_reference,
                    expected_amount=0,
                    actual_amount=line.deducted_amount,
                    variance_amount=line.deducted_amount,
                    description=f"No active CDAS mandate was found for employee {line.employee_number}.",
                )
            )
            continue

        expected = money(line.expected_amount or mandate.monthly_deduction)
        actual = money(line.deducted_amount)
        variance = money(actual - expected)
        line.mandate_id = mandate.id
        line.borrower_id = mandate.borrower_id
        line.loan_id = mandate.loan_id
        line.expected_amount = expected
        line.variance_amount = variance
        if actual <= 0:
            line.status = "missing"
            line.reason = "No deduction was received."
        elif variance == 0:
            line.status = "matched"
        elif actual < expected:
            line.status = "partial"
            line.reason = "The received deduction is lower than the mandate amount."
        else:
            line.status = "excess"
            line.reason = "The received deduction is higher than the mandate amount."

        try:
            loan = db.get(ClientCompanyLoan, mandate.loan_id)
            if not loan:
                raise HTTPException(status_code=404, detail="Mandate loan not found")
            if actual > 0:
                payment, _, _ = record_cash_repayment(
                    db,
                    loan=loan,
                    amount_tendered=actual,
                    overpayment_action="carry_forward",
                    installment_number=None,
                    initiated_by_user_id=user_id,
                    payment_method=PaymentMethod.CDAS,
                    proof_reference=f"{batch.batch_reference}:{line.line_reference}",
                    proof_notes=f"CDAS payroll remittance for {batch.payroll_month:%Y-%m}",
                    idempotency_key=f"cdas:{batch.id}:{line.id}",
                )
                line.payment_transaction_id = payment.id
                mandate.deductions_received = int(mandate.deductions_received or 0) + 1
                mandate.total_received = money(mandate.total_received + actual)
                if mandate.total_received >= money(mandate.total_expected):
                    mandate.status = "completed"
                    mandate.completed_at = datetime.now(timezone.utc)
        except Exception as exc:
            db.rollback()
            # Re-attach rows after rollback.
            batch = db.get(CDASRemittanceBatch, batch.id)
            run = db.get(ReconciliationRun, run.id)
            line = db.get(CDASRemittanceLine, line.id)
            line.status = "posting_failed"
            line.reason = str(exc)

        if line.status == "matched":
            matched_count += 1
            matched_amount += actual
        else:
            exception_count += 1
            exception_amount += abs(variance) if variance else expected
            db.add(
                ReconciliationException(
                    run_id=run.id,
                    company_id=batch.company_id,
                    exception_type=f"cdas_{line.status}",
                    severity="medium" if line.status in {"partial", "excess"} else "high",
                    source_entity_type="cdas_remittance_line",
                    source_entity_id=line.id,
                    reference=line.line_reference,
                    expected_amount=expected,
                    actual_amount=actual,
                    variance_amount=variance,
                    description=line.reason or "CDAS remittance variance detected.",
                )
            )

    run.records_checked = len(lines)
    run.matched_records = matched_count
    run.exception_records = exception_count
    run.matched_amount = money(matched_amount)
    run.exception_amount = money(exception_amount)
    run.status = "completed_with_exceptions" if exception_count else "completed"
    run.completed_at = datetime.now(timezone.utc)
    run.summary = {
        **(run.summary or {}),
        "line_count": len(lines),
        "matched_count": matched_count,
        "exception_count": exception_count,
    }
    batch.line_count = len(lines)
    batch.matched_count = matched_count
    batch.exception_count = exception_count
    batch.matched_amount = money(matched_amount)
    batch.exception_amount = money(exception_amount)
    batch.status = "reconciled_with_exceptions" if exception_count else "reconciled"
    batch.reconciled_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


def run_reconciliation(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None,
    run_type: str,
    period_start: date,
    period_end: date,
    user_id: UUID,
) -> ReconciliationRun:
    now = datetime.now(timezone.utc)
    run = ReconciliationRun(
        company_id=company_id,
        branch_id=branch_id,
        run_reference=make_reference("REC"),
        run_type=run_type,
        period_start=period_start,
        period_end=period_end,
        status="running",
        started_at=now,
        created_by_user_id=user_id,
    )
    db.add(run)
    db.flush()

    checked = matched = exceptions = 0
    matched_amount = exception_amount = Decimal("0")
    summary: dict[str, Any] = {}

    loan_query = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.company_id == company_id)
    if branch_id:
        loan_query = loan_query.filter(ClientCompanyLoan.branch_id == branch_id)
    loans = loan_query.all() if run_type in {"full", "loans", "accounting"} else []
    for loan in loans:
        checked += 1
        expected_balance = money(max(Decimal(loan.total_repayable or 0) - Decimal(loan.amount_paid or 0), Decimal("0")))
        actual_balance = money(loan.balance)
        if expected_balance != actual_balance:
            variance = money(actual_balance - expected_balance)
            exceptions += 1
            exception_amount += abs(variance)
            db.add(ReconciliationException(
                run_id=run.id,
                company_id=company_id,
                branch_id=loan.branch_id,
                exception_type="loan_balance_mismatch",
                severity="high",
                source_entity_type="client_company_loan",
                source_entity_id=loan.id,
                reference=loan.loan_reference,
                expected_amount=expected_balance,
                actual_amount=actual_balance,
                variance_amount=variance,
                description="Loan balance does not equal total repayable less successful repayments.",
            ))
        else:
            matched += 1
            matched_amount += actual_balance

    if run_type in {"full", "payments", "accounting"}:
        payment_query = db.query(PaymentTransaction).filter(
            PaymentTransaction.company_id == company_id,
            PaymentTransaction.created_at >= datetime.combine(period_start, datetime.min.time()),
            PaymentTransaction.created_at < datetime.combine(period_end + timedelta(days=1), datetime.min.time()),
            PaymentTransaction.status == PaymentStatus.SUCCEEDED,
        )
        if branch_id:
            payment_query = payment_query.join(ClientCompanyLoan, ClientCompanyLoan.id == PaymentTransaction.loan_id).filter(ClientCompanyLoan.branch_id == branch_id)
        payments = payment_query.all()
        for payment in payments:
            checked += 1
            if payment.purpose == PaymentPurpose.LOAN_REPAYMENT and payment.loan_id:
                allocation_total = money(
                    db.query(func.coalesce(func.sum(PaymentAllocation.amount), 0))
                    .filter(PaymentAllocation.payment_id == payment.id)
                    .scalar()
                )
                if allocation_total != money(payment.amount):
                    variance = money(payment.amount - allocation_total)
                    exceptions += 1
                    exception_amount += abs(variance)
                    db.add(ReconciliationException(
                        run_id=run.id,
                        company_id=company_id,
                        branch_id=branch_id,
                        exception_type="unallocated_payment",
                        severity="critical",
                        source_entity_type="payment_transaction",
                        source_entity_id=payment.id,
                        reference=payment.provider_reference,
                        expected_amount=payment.amount,
                        actual_amount=allocation_total,
                        variance_amount=variance,
                        description="Successful repayment is not fully allocated to repayment instalments.",
                    ))
                    continue
            receipt = db.query(PaymentReceipt).filter(PaymentReceipt.payment_id == payment.id).first()
            if not receipt:
                exceptions += 1
                exception_amount += money(payment.amount)
                db.add(ReconciliationException(
                    run_id=run.id,
                    company_id=company_id,
                    branch_id=branch_id,
                    exception_type="missing_receipt",
                    severity="medium",
                    source_entity_type="payment_transaction",
                    source_entity_id=payment.id,
                    reference=payment.provider_reference,
                    expected_amount=payment.amount,
                    actual_amount=0,
                    variance_amount=payment.amount,
                    description="Successful payment has no generated receipt record.",
                ))
                continue
            journal = db.query(JournalEntry).filter(
                JournalEntry.company_id == company_id,
                JournalEntry.reference_type == "payment_transaction",
                JournalEntry.reference_id == str(payment.id),
            ).first()
            if not journal:
                exceptions += 1
                exception_amount += money(payment.amount)
                db.add(ReconciliationException(
                    run_id=run.id,
                    company_id=company_id,
                    branch_id=branch_id,
                    exception_type="missing_journal_entry",
                    severity="high",
                    source_entity_type="payment_transaction",
                    source_entity_id=payment.id,
                    reference=payment.provider_reference,
                    expected_amount=payment.amount,
                    actual_amount=0,
                    variance_amount=payment.amount,
                    description="Successful payment has no linked accounting journal entry.",
                ))
                continue
            matched += 1
            matched_amount += money(payment.amount)

    if run_type in {"full", "cdas"}:
        active_mandates = db.query(CDASDeductionMandate).filter(
            CDASDeductionMandate.company_id == company_id,
            CDASDeductionMandate.status.in_(["accepted", "active", "rescheduled"]),
            CDASDeductionMandate.start_date <= period_end,
            or_(CDASDeductionMandate.end_date.is_(None), CDASDeductionMandate.end_date >= period_start),
        ).all()
        for mandate in active_mandates:
            checked += 1
            found = db.query(CDASRemittanceLine).join(CDASRemittanceBatch, CDASRemittanceBatch.id == CDASRemittanceLine.batch_id).filter(
                CDASRemittanceLine.company_id == company_id,
                CDASRemittanceLine.mandate_id == mandate.id,
                CDASRemittanceBatch.payroll_month >= period_start,
                CDASRemittanceBatch.payroll_month <= period_end,
            ).first()
            if not found:
                exceptions += 1
                exception_amount += money(mandate.monthly_deduction)
                db.add(ReconciliationException(
                    run_id=run.id,
                    company_id=company_id,
                    branch_id=mandate.branch_id,
                    exception_type="missing_cdas_deduction",
                    severity="high",
                    source_entity_type="cdas_deduction_mandate",
                    source_entity_id=mandate.id,
                    reference=mandate.mandate_number,
                    expected_amount=mandate.monthly_deduction,
                    actual_amount=0,
                    variance_amount=mandate.monthly_deduction,
                    description="No CDAS remittance line was received for an active mandate in the selected period.",
                ))
            else:
                matched += 1
                matched_amount += money(found.deducted_amount)

    summary.update({
        "loans_checked": len(loans),
        "records_checked": checked,
        "matched_records": matched,
        "exception_records": exceptions,
    })
    run.records_checked = checked
    run.matched_records = matched
    run.exception_records = exceptions
    run.matched_amount = money(matched_amount)
    run.exception_amount = money(exception_amount)
    run.summary = summary
    run.status = "completed_with_exceptions" if exceptions else "completed"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(run)
    return run


def sync_overdue_collection_cases(db: Session, company_id: UUID) -> int:
    """Synchronise collection cases with the authoritative repayment schedule.

    The collection queue is operational state, not a second ledger. This keeps
    days past due, overdue totals and priority aligned with unpaid instalments,
    reopens a previously recovered case if arrears return, and marks arrears as
    recovered when the loan is no longer overdue.
    """
    today = date.today()
    loans = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.status.in_([LoanStatus.ACTIVE, LoanStatus.DEFAULTED]),
        ClientCompanyLoan.balance > 0,
    ).all()
    created = 0
    seen_loan_ids: set[UUID] = set()

    for loan in loans:
        seen_loan_ids.add(loan.id)
        overdue_installments = db.query(RepaymentInstallment).filter(
            RepaymentInstallment.loan_id == loan.id,
            RepaymentInstallment.is_superseded.is_(False),
            RepaymentInstallment.due_date < today,
            RepaymentInstallment.paid_amount < RepaymentInstallment.total_due,
        ).all()
        case = db.query(CollectionCase).filter(
            CollectionCase.company_id == company_id,
            CollectionCase.loan_id == loan.id,
        ).first()

        if not overdue_installments:
            if case and case.status not in {"closed", "written_off"}:
                case.status = "recovered"
                case.stage = "recovery"
                case.priority = "normal"
                case.days_past_due = 0
                case.overdue_amount = money(0)
                case.outstanding_balance = money(loan.balance)
                case.next_action_at = None
                if case.promise_status == "pending":
                    case.promise_status = "kept"
            continue

        earliest = min(item.due_date for item in overdue_installments)
        overdue_amount = sum(
            (money(item.total_due) - money(item.paid_amount) for item in overdue_installments),
            Decimal("0"),
        )
        days = max((today - earliest).days, 0)
        stage = "early_arrears" if days <= 30 else "late_arrears" if days <= 90 else "pre_legal"
        priority = "normal" if days <= 30 else "high" if days <= 90 else "urgent"

        if case:
            case.days_past_due = days
            case.overdue_amount = money(overdue_amount)
            case.outstanding_balance = money(loan.balance)
            if case.status == "recovered":
                case.status = "open"
            if case.status not in {"closed", "written_off"}:
                if case.stage != "legal":
                    case.stage = stage
                case.priority = priority
            if case.promise_status == "pending" and case.promise_date and case.promise_date < today:
                case.promise_status = "broken"
        else:
            db.add(CollectionCase(
                company_id=company_id,
                branch_id=loan.branch_id,
                borrower_id=loan.borrower_id,
                loan_id=loan.id,
                case_reference=make_reference("COL"),
                stage=stage,
                days_past_due=days,
                overdue_amount=money(overdue_amount),
                outstanding_balance=money(loan.balance),
                priority=priority,
            ))
            created += 1

    # Cases can outlive an active loan. Keep their audit trail but remove them
    # from the live arrears queue when the loan is settled/completed.
    existing_cases = db.query(CollectionCase).filter(CollectionCase.company_id == company_id).all()
    for case in existing_cases:
        if case.loan_id in seen_loan_ids:
            continue
        loan = db.get(ClientCompanyLoan, case.loan_id)
        if not loan:
            continue
        if money(loan.balance) <= 0 or loan.status == LoanStatus.COMPLETED:
            if case.status not in {"closed", "written_off"}:
                case.status = "recovered"
                case.stage = "recovery"
                case.priority = "normal"
                case.days_past_due = 0
                case.overdue_amount = money(0)
                case.outstanding_balance = money(loan.balance)
                case.next_action_at = None
                if case.promise_status == "pending":
                    case.promise_status = "kept"

    db.commit()
    return created


def generate_regulatory_payload(db: Session, submission: RegulatorySubmission) -> dict[str, Any]:
    loans = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.company_id == submission.company_id,
        ClientCompanyLoan.created_at >= datetime.combine(submission.period_start, datetime.min.time()),
        ClientCompanyLoan.created_at < datetime.combine(submission.period_end + timedelta(days=1), datetime.min.time()),
    ).all()
    payments = db.query(PaymentTransaction).filter(
        PaymentTransaction.company_id == submission.company_id,
        PaymentTransaction.created_at >= datetime.combine(submission.period_start, datetime.min.time()),
        PaymentTransaction.created_at < datetime.combine(submission.period_end + timedelta(days=1), datetime.min.time()),
    ).all()
    collection_cases = db.query(CollectionCase).filter(CollectionCase.company_id == submission.company_id).all()
    compliance_cases = db.query(ComplianceCase).filter(
        ComplianceCase.company_id == submission.company_id,
        ComplianceCase.created_at >= datetime.combine(submission.period_start, datetime.min.time()),
        ComplianceCase.created_at < datetime.combine(submission.period_end + timedelta(days=1), datetime.min.time()),
    ).all()
    return {
        "report_type": submission.report_type,
        "period": {"start": str(submission.period_start), "end": str(submission.period_end)},
        "portfolio": {
            "loan_count": len(loans),
            "principal_originated": str(money(sum((Decimal(item.principal_amount or 0) for item in loans), Decimal("0")))),
            "total_repayable": str(money(sum((Decimal(item.total_repayable or 0) for item in loans), Decimal("0")))),
            "outstanding_balance": str(money(sum((Decimal(item.balance or 0) for item in loans), Decimal("0")))),
            "active": sum(1 for item in loans if item.status == LoanStatus.ACTIVE),
            "completed": sum(1 for item in loans if item.status == LoanStatus.COMPLETED),
            "defaulted": sum(1 for item in loans if item.status == LoanStatus.DEFAULTED),
        },
        "payments": {
            "count": len(payments),
            "successful_count": sum(1 for item in payments if item.status == PaymentStatus.SUCCEEDED),
            "successful_amount": str(money(sum((Decimal(item.amount or 0) for item in payments if item.status == PaymentStatus.SUCCEEDED), Decimal("0")))),
            "failed_count": sum(1 for item in payments if item.status == PaymentStatus.FAILED),
        },
        "arrears": {
            "case_count": len(collection_cases),
            "overdue_amount": str(money(sum((Decimal(item.overdue_amount or 0) for item in collection_cases), Decimal("0")))),
            "legal_cases": sum(1 for item in collection_cases if item.stage == "legal" or item.status == "legal"),
            "written_off": sum(1 for item in collection_cases if item.status == "written_off"),
        },
        "compliance": {
            "case_count": len(compliance_cases),
            "open_cases": sum(1 for item in compliance_cases if item.status not in {"cleared", "closed"}),
            "critical_cases": sum(1 for item in compliance_cases if item.severity == "critical"),
            "aml_cases": sum(1 for item in compliance_cases if item.case_type == "aml"),
            "fraud_cases": sum(1 for item in compliance_cases if item.case_type == "fraud"),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def evaluate_credit_decision(
    db: Session,
    *,
    company_id: UUID,
    borrower_id: UUID,
    application_id: UUID | None,
    policy: CreditDecisionPolicy,
    requested_amount: Decimal | None,
    proposed_installment: Decimal | None,
    additional_inputs: dict[str, Any],
) -> CreditDecision:
    rules = policy.rules or {}
    kyc = db.query(BorrowerKYCProfile).filter(
        BorrowerKYCProfile.company_id == company_id,
        BorrowerKYCProfile.borrower_id == borrower_id,
    ).first()
    employment = db.query(BorrowerEmploymentProfile).filter(
        BorrowerEmploymentProfile.company_id == company_id,
        BorrowerEmploymentProfile.borrower_id == borrower_id,
    ).first()
    bureau = db.query(CreditBureauEnquiry).filter(
        CreditBureauEnquiry.company_id == company_id,
        CreditBureauEnquiry.borrower_id == borrower_id,
        CreditBureauEnquiry.status == "completed",
    ).order_by(CreditBureauEnquiry.completed_at.desc()).first()
    payroll = db.query(CDASPayrollProfile).filter(
        CDASPayrollProfile.company_id == company_id,
        CDASPayrollProfile.borrower_id == borrower_id,
    ).first()
    application = db.get(DirectLoanApplication, application_id) if application_id else None

    net_income = money(
        additional_inputs.get("net_income")
        or (employment.verified_net_income if employment else 0)
        or (payroll.net_salary if payroll else 0)
    )
    monthly_obligations = money(
        additional_inputs.get("monthly_obligations")
        or (bureau.monthly_obligations if bureau else 0)
        or 0
    )
    installment = money(proposed_installment or additional_inputs.get("proposed_installment") or 0)
    score = int(additional_inputs.get("credit_score") or (bureau.score if bureau else 0) or 0)
    dti = Decimal("0") if net_income <= 0 else ((monthly_obligations + installment) / net_income * Decimal("100")).quantize(Decimal("0.001"))

    decline: list[str] = []
    refer: list[str] = []
    conditions: list[str] = []
    if rules.get("require_kyc", True) and (not kyc or kyc.status not in {"verified", "approved"}):
        refer.append("KYC verification is incomplete.")
    if rules.get("decline_on_sanctions", True) and kyc and kyc.sanctions_hit:
        decline.append("Sanctions screening returned a match.")
    if rules.get("decline_on_fraud", True) and kyc and kyc.fraud_flag:
        decline.append("The borrower has an active fraud flag.")
    minimum_score = int(rules.get("minimum_credit_score", 0) or 0)
    if minimum_score and score < minimum_score:
        action = rules.get("low_score_action", "refer")
        (decline if action == "decline" else refer).append(f"Credit score {score} is below the minimum {minimum_score}.")
    max_dti = Decimal(str(rules.get("maximum_dti_percent", 40)))
    if dti > max_dti:
        action = rules.get("high_dti_action", "decline")
        (decline if action == "decline" else refer).append(f"Debt-service ratio {dti}% exceeds the maximum {max_dti}%.")
    min_income = money(rules.get("minimum_net_income", 0))
    if net_income < min_income:
        decline.append(f"Verified net income is below {min_income}.")
    if payroll and rules.get("require_cdas_verified_for_payroll", False) and not payroll.verified:
        refer.append("CDAS payroll profile is not verified.")
    max_amount = money(rules.get("maximum_loan_amount", 0))
    amount = money(requested_amount or (application.requested_amount if application else 0))
    if max_amount > 0 and amount > max_amount:
        refer.append("Requested amount exceeds the automatic approval limit.")
        conditions.append(f"Reduce the amount to {max_amount} or obtain a manager override.")

    decision_value = "decline" if decline else "refer" if refer else "approve"
    reasons = decline + refer
    base_score = Decimal(str(policy.scorecard.get("base_score", 50) if policy.scorecard else 50))
    score_value = base_score
    if score:
        score_value += Decimal(str(min(max((score - 300) / 14, 0), 50)))
    score_value -= min(dti, Decimal("50")) / Decimal("2")
    score_value = max(min(score_value, Decimal("100")), Decimal("0")).quantize(Decimal("0.001"))

    input_snapshot = {
        "requested_amount": str(amount),
        "proposed_installment": str(installment),
        "net_income": str(net_income),
        "monthly_obligations": str(monthly_obligations),
        "dti_percent": str(dti),
        "credit_score": score,
        "kyc_status": kyc.status if kyc else None,
        "sanctions_hit": bool(kyc.sanctions_hit) if kyc else False,
        "fraud_flag": bool(kyc.fraud_flag) if kyc else False,
        "cdas_verified": bool(payroll.verified) if payroll else False,
        **additional_inputs,
    }
    decision = CreditDecision(
        company_id=company_id,
        borrower_id=borrower_id,
        application_id=application_id,
        policy_id=policy.id,
        decision_reference=make_reference("DEC"),
        decision=decision_value,
        score=score_value,
        reasons=reasons,
        conditions=conditions,
        input_snapshot=input_snapshot,
        output_snapshot={"decision": decision_value, "score": str(score_value), "reasons": reasons, "conditions": conditions},
        decided_by="rules_engine",
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


def start_workflow_instance(
    db: Session,
    *,
    company_id: UUID,
    template: WorkflowTemplate,
    application_id: UUID | None,
    loan_id: UUID | None,
    borrower_id: UUID | None,
    assigned_user_id: UUID | None,
    context_snapshot: dict[str, Any],
    due_at: datetime | None,
) -> WorkflowInstance:
    steps = template.steps or []
    first = steps[0] if steps else {}
    instance = WorkflowInstance(
        company_id=company_id,
        template_id=template.id,
        application_id=application_id,
        loan_id=loan_id,
        borrower_id=borrower_id,
        instance_reference=make_reference("WF"),
        status="active" if steps else "completed",
        current_step_index=0,
        current_step_key=first.get("key") or first.get("name") if steps else None,
        assigned_role=first.get("role") if steps else None,
        assigned_user_id=assigned_user_id,
        history=[],
        context_snapshot=context_snapshot,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc) if not steps else None,
        due_at=due_at,
    )
    db.add(instance)
    db.commit()
    db.refresh(instance)
    return instance


def advance_workflow_instance(
    db: Session,
    *,
    instance: WorkflowInstance,
    template: WorkflowTemplate,
    action: str,
    notes: str | None,
    user_id: UUID,
    assigned_user_id: UUID | None,
) -> WorkflowInstance:
    steps = template.steps or []
    history = list(instance.history or [])
    current = steps[instance.current_step_index] if steps and instance.current_step_index < len(steps) else {}
    history.append({
        "step_index": instance.current_step_index,
        "step_key": instance.current_step_key,
        "action": action,
        "notes": notes,
        "performed_by_user_id": str(user_id),
        "performed_at": datetime.now(timezone.utc).isoformat(),
    })
    instance.history = history
    if action == "reject":
        instance.status = "rejected"
        instance.completed_at = datetime.now(timezone.utc)
    elif action == "return":
        instance.current_step_index = max(instance.current_step_index - 1, 0)
    elif action == "complete":
        instance.status = "completed"
        instance.completed_at = datetime.now(timezone.utc)
    else:
        instance.current_step_index += 1
        if instance.current_step_index >= len(steps):
            instance.status = "completed"
            instance.current_step_key = None
            instance.assigned_role = None
            instance.completed_at = datetime.now(timezone.utc)
        else:
            nxt = steps[instance.current_step_index]
            instance.current_step_key = nxt.get("key") or nxt.get("name")
            instance.assigned_role = nxt.get("role")
    if assigned_user_id:
        instance.assigned_user_id = assigned_user_id
    db.commit()
    db.refresh(instance)
    return instance
