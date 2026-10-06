from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.models.accounting import AccountingAccount, JournalEntry, JournalLine
from database.models.credit_loss_provisioning import (
    CreditLossProvisionLine,
    CreditLossProvisionPolicy,
    CreditLossProvisionRun,
)
from database.models.portfolio_risk import PortfolioRiskSnapshot
from services.accounting_service import account_by_code, create_entry, ensure_chart, loan_source_principal_outstanding, scope_key


MONEY = Decimal("0.01")
DEFAULT_POLICY_RATES = {
    "current": "0.02",
    "1-7": "0.05",
    "8-30": "0.10",
    "31-60": "0.25",
    "61-90": "0.50",
    "90+": "1.00",
    "defaulted": "1.00",
    "first_payment_default_floor": "0.25",
    "write_off_candidate_dpd": 180,
}


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def get_or_create_policy(db: Session, context: TenantContext) -> CreditLossProvisionPolicy:
    policy = (
        db.query(CreditLossProvisionPolicy)
        .filter(
            CreditLossProvisionPolicy.company_id == context.company_id,
            CreditLossProvisionPolicy.status == "active",
        )
        .order_by(CreditLossProvisionPolicy.version.desc())
        .first()
    )
    if policy:
        return policy
    policy = CreditLossProvisionPolicy(
        company_id=context.company_id,
        name="Standard loan-loss provision policy",
        version=1,
        status="active",
        rates=DEFAULT_POLICY_RATES,
        description="Configurable operational provisioning policy based on stored LoanHub portfolio-risk evidence. It is not labelled as statutory IFRS 9 compliance without an institution-specific accounting policy review.",
        configured_by_user_id=context.user.id,
        effective_from=datetime.now(timezone.utc),
    )
    db.add(policy)
    db.flush()
    return policy


def stage_for_snapshot(row: PortfolioRiskSnapshot) -> int:
    status = str(row.loan_status or "").lower()
    if row.is_written_off or status == "defaulted" or int(row.days_past_due or 0) > 90:
        return 3
    if row.first_payment_default or int(row.days_past_due or 0) >= 8:
        return 2
    return 1


def rate_for_snapshot(row: PortfolioRiskSnapshot, policy: CreditLossProvisionPolicy) -> Decimal:
    rates = dict(DEFAULT_POLICY_RATES)
    rates.update(policy.rates or {})
    key = "defaulted" if str(row.loan_status or "").lower() == "defaulted" else str(row.delinquency_bucket or "current")
    rate = Decimal(str(rates.get(key, rates["current"])))
    if row.first_payment_default:
        rate = max(rate, Decimal(str(rates.get("first_payment_default_floor", "0.25"))))
    return min(max(rate, Decimal("0")), Decimal("1"))


def _posted_allowance_balance(
    db: Session,
    *,
    company_id: UUID,
    as_of_date: date,
    branch_id: UUID | None,
) -> Decimal:
    """Return the actual posted credit balance of account 1150 as of the run date.

    This deliberately uses the ledger rather than the previous provision run so
    write-offs, releases and other approved allowance movements are reflected.
    """
    key, _ = scope_key(company_id)
    ensure_chart(db, company_id=company_id)
    allowance = db.query(AccountingAccount).filter(
        AccountingAccount.scope_key == key,
        AccountingAccount.code == "1150",
        AccountingAccount.is_active.is_(True),
    ).first()
    if not allowance:
        return Decimal("0.00")
    query = db.query(
        func.coalesce(func.sum(JournalLine.credit), 0),
        func.coalesce(func.sum(JournalLine.debit), 0),
    ).join(JournalEntry, JournalEntry.id == JournalLine.journal_entry_id).filter(
        JournalLine.account_id == allowance.id,
        JournalEntry.scope_key == key,
        JournalEntry.status == "posted",
        JournalEntry.entry_date <= as_of_date,
    )
    if branch_id:
        query = query.filter(JournalEntry.branch_id == branch_id)
    credit, debit = query.first()
    return money(Decimal(credit) - Decimal(debit))


def _assert_provision_scope_consistency(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None,
    as_of_date: date,
) -> None:
    """Prevent overlapping company-wide and branch-specific allowance regimes."""
    if branch_id is None:
        conflict = db.query(CreditLossProvisionRun.id).filter(
            CreditLossProvisionRun.company_id == company_id,
            CreditLossProvisionRun.as_of_date == as_of_date,
            CreditLossProvisionRun.branch_scope_key != "ALL",
            CreditLossProvisionRun.status.in_(["draft", "approved", "posted"]),
        ).first()
        if conflict:
            raise HTTPException(
                status_code=409,
                detail="Company-wide provisioning cannot overlap branch-scoped runs for the same date",
            )
    else:
        conflict = db.query(CreditLossProvisionRun.id).filter(
            CreditLossProvisionRun.company_id == company_id,
            CreditLossProvisionRun.as_of_date == as_of_date,
            CreditLossProvisionRun.branch_scope_key == "ALL",
            CreditLossProvisionRun.status.in_(["draft", "approved", "posted"]),
        ).first()
        if conflict:
            raise HTTPException(
                status_code=409,
                detail="Branch provisioning cannot overlap a company-wide run for the same date",
            )


def generate_run(
    db: Session,
    context: TenantContext,
    *,
    as_of_date: date,
    management_overlay: Decimal = Decimal("0"),
    overlay_reason: str | None = None,
) -> CreditLossProvisionRun:
    branch_scope_key = str(context.branch_id) if context.branch_id else "ALL"
    _assert_provision_scope_consistency(
        db,
        company_id=context.company_id,
        branch_id=context.branch_id,
        as_of_date=as_of_date,
    )
    existing = db.query(CreditLossProvisionRun).filter(
        CreditLossProvisionRun.company_id == context.company_id,
        CreditLossProvisionRun.as_of_date == as_of_date,
        CreditLossProvisionRun.branch_scope_key == branch_scope_key,
    ).first()
    if existing:
        if existing.status in {"approved", "posted"}:
            raise HTTPException(status_code=409, detail="The provision run for this scope/date is already approved and locked")
        db.query(CreditLossProvisionLine).filter(CreditLossProvisionLine.run_id == existing.id).delete(synchronize_session=False)
        run = existing
    else:
        run = CreditLossProvisionRun(
            company_id=context.company_id,
            branch_id=context.branch_id,
            branch_scope_key=branch_scope_key,
            run_reference=f"CLP-{as_of_date:%Y%m%d}-{secrets.token_hex(4).upper()}",
            as_of_date=as_of_date,
            generated_by_user_id=context.user.id,
            generated_at=datetime.now(timezone.utc),
        )
        db.add(run)
        db.flush()

    policy = get_or_create_policy(db, context)
    run.policy_id = policy.id
    overlay = money(management_overlay)
    if overlay != 0 and not (overlay_reason or "").strip():
        raise HTTPException(status_code=422, detail="A management-overlay reason is required when the overlay is non-zero")

    query = db.query(PortfolioRiskSnapshot).filter(
        PortfolioRiskSnapshot.company_id == context.company_id,
        PortfolioRiskSnapshot.snapshot_date == as_of_date,
    )
    if context.branch_id:
        query = query.filter(PortfolioRiskSnapshot.branch_id == context.branch_id)
    snapshots = query.all()
    if not snapshots:
        raise HTTPException(status_code=409, detail="Generate the portfolio-risk snapshot for this date before running provisions")

    eligible = [row for row in snapshots if money(row.outstanding_balance) > 0 and not row.is_written_off]
    stage_totals: dict[int, Decimal] = defaultdict(lambda: Decimal("0.00"))
    gross = Decimal("0.00")
    base_total = Decimal("0.00")
    write_off_candidates = 0
    candidate_dpd = int((policy.rates or {}).get("write_off_candidate_dpd", DEFAULT_POLICY_RATES["write_off_candidate_dpd"]))

    recognized_rows = []
    for row in eligible:
        exposure = loan_source_principal_outstanding(
            db,
            company_id=context.company_id,
            loan_id=row.loan_id,
            as_of=as_of_date,
        )
        if exposure <= 0:
            continue
        recognized_rows.append(row)
        stage = stage_for_snapshot(row)
        rate = rate_for_snapshot(row, policy)
        allowance = money(exposure * rate)
        reasons = [f"DPD {int(row.days_past_due or 0)}", f"Delinquency bucket {row.delinquency_bucket}", f"Policy rate {rate * 100}%"]
        if row.first_payment_default:
            reasons.append("First-payment-default floor applied")
        if str(row.loan_status or "").lower() == "defaulted":
            reasons.append("Loan status is defaulted")
        write_off_candidate = int(row.days_past_due or 0) >= candidate_dpd
        if write_off_candidate:
            write_off_candidates += 1
            reasons.append(f"DPD reached write-off-review threshold of {candidate_dpd} days")

        db.add(CreditLossProvisionLine(
            run_id=run.id,
            company_id=context.company_id,
            branch_id=row.branch_id,
            loan_id=row.loan_id,
            borrower_id=row.borrower_id,
            folio_number=(row.evidence_snapshot or {}).get("folio_number") or "UNASSIGNED",
            stage=stage,
            days_past_due=int(row.days_past_due or 0),
            exposure=exposure,
            provision_rate=rate,
            base_allowance=allowance,
            overlay_amount=0,
            required_allowance=allowance,
            rationale=reasons,
            evidence={
                "snapshot_date": row.snapshot_date.isoformat(),
                "delinquency_bucket": row.delinquency_bucket,
                "loan_status": row.loan_status,
                "overdue_amount": str(money(row.overdue_amount)),
                "risk_snapshot_outstanding_balance": str(money(row.outstanding_balance)),
                "recognized_principal_exposure": str(exposure),
                "exposure_basis": "successful_disbursements_less_principal_repayments",
                "first_payment_default": bool(row.first_payment_default),
                "collection_channel": row.collection_channel,
                "employer_label": row.employer_label,
            },
            write_off_candidate=write_off_candidate,
        ))
        gross += exposure
        base_total += allowance
        stage_totals[stage] += allowance

    prior = _posted_allowance_balance(
        db,
        company_id=context.company_id,
        as_of_date=as_of_date,
        branch_id=context.branch_id,
    )
    required = max(money(base_total + overlay), Decimal("0.00"))
    run.status = "draft"
    run.loan_count = len(recognized_rows)
    run.gross_exposure = money(gross)
    run.required_allowance = required
    run.prior_allowance = prior
    run.allowance_movement = money(required - prior)
    run.stage_1_allowance = money(stage_totals[1])
    run.stage_2_allowance = money(stage_totals[2])
    run.stage_3_allowance = money(stage_totals[3])
    run.management_overlay = overlay
    run.overlay_reason = (overlay_reason or "").strip() or None
    run.generated_at = datetime.now(timezone.utc)
    run.summary = {
        "method": "configurable_dpd_stage_policy",
        "prior_allowance_basis": "actual_posted_1150_ledger_balance",
        "exposure_basis": "recognized_principal_control_subledger",
        "policy_name": policy.name,
        "policy_version": policy.version,
        "rates": policy.rates,
        "write_off_candidates": write_off_candidates,
        "note": "Operational impairment estimate. Formal accounting/regulatory classification remains subject to the institution's approved accounting policy.",
    }
    db.commit()
    db.refresh(run)
    return run


def approve_and_post(db: Session, context: TenantContext, run_id: UUID) -> CreditLossProvisionRun:
    run = db.query(CreditLossProvisionRun).filter(
        CreditLossProvisionRun.id == run_id,
        CreditLossProvisionRun.company_id == context.company_id,
    ).with_for_update().first()
    if not run or (context.branch_id and run.branch_id != context.branch_id):
        raise HTTPException(status_code=404, detail="Credit-loss provision run not found")
    if run.status != "draft":
        raise HTTPException(status_code=409, detail="Only a draft provision run can be approved")
    if run.generated_by_user_id == context.user.id:
        raise HTTPException(status_code=409, detail="Maker-checker control requires a different user to approve this provision run")

    movement = money(run.allowance_movement)
    journal: JournalEntry | None = None
    if movement != 0:
        ensure_chart(db, company_id=context.company_id)
        key, _ = scope_key(context.company_id)
        expense = account_by_code(db, key, "5510")
        allowance = account_by_code(db, key, "1150")
        amount = abs(movement)
        if movement > 0:
            lines = [
                {"account_id": expense.id, "debit": amount, "credit": 0, "description": "Credit-loss provision expense"},
                {"account_id": allowance.id, "debit": 0, "credit": amount, "description": "Allowance for credit losses"},
            ]
        else:
            lines = [
                {"account_id": allowance.id, "debit": amount, "credit": 0, "description": "Release of credit-loss allowance"},
                {"account_id": expense.id, "debit": 0, "credit": amount, "description": "Credit-loss provision release"},
            ]
        journal = create_entry(
            db,
            company_id=context.company_id,
            branch_id=run.branch_id,
            created_by_user_id=context.user.id,
            entry_date=run.as_of_date,
            description=f"Credit-loss allowance movement {run.run_reference}",
            reference_type="credit_loss_provision_run",
            reference_id=str(run.id),
            status_value="posted",
            lines=lines,
        )

    now = datetime.now(timezone.utc)
    run.status = "posted"
    run.approved_by_user_id = context.user.id
    run.approved_at = now
    run.locked_at = now
    run.journal_entry_id = journal.id if journal else None
    db.commit()
    db.refresh(run)
    return run


def run_payload(db: Session, run: CreditLossProvisionRun, *, include_lines: bool = False) -> dict[str, Any]:
    data = {
        "id": str(run.id), "run_reference": run.run_reference, "as_of_date": run.as_of_date.isoformat(), "status": run.status,
        "loan_count": run.loan_count, "gross_exposure": float(run.gross_exposure or 0), "required_allowance": float(run.required_allowance or 0),
        "prior_allowance": float(run.prior_allowance or 0), "allowance_movement": float(run.allowance_movement or 0),
        "stage_1_allowance": float(run.stage_1_allowance or 0), "stage_2_allowance": float(run.stage_2_allowance or 0), "stage_3_allowance": float(run.stage_3_allowance or 0),
        "management_overlay": float(run.management_overlay or 0), "overlay_reason": run.overlay_reason, "summary": run.summary or {},
        "journal_entry_id": str(run.journal_entry_id) if run.journal_entry_id else None,
        "generated_at": run.generated_at.isoformat(), "approved_at": run.approved_at.isoformat() if run.approved_at else None,
    }
    if include_lines:
        rows = db.query(CreditLossProvisionLine).filter(CreditLossProvisionLine.run_id == run.id).order_by(CreditLossProvisionLine.stage.desc(), CreditLossProvisionLine.days_past_due.desc()).all()
        data["lines"] = [{
            "id": str(row.id), "loan_id": str(row.loan_id), "folio_number": row.folio_number, "stage": row.stage,
            "days_past_due": row.days_past_due, "exposure": float(row.exposure or 0), "provision_rate": float(row.provision_rate or 0),
            "required_allowance": float(row.required_allowance or 0), "rationale": row.rationale or [], "evidence": row.evidence or {},
            "write_off_candidate": bool(row.write_off_candidate),
        } for row in rows]
    return data
