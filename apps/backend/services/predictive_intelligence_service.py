from __future__ import annotations

import secrets
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.client_loan_company import ClientCompanyLoan
from database.models.collection_automation import CollectionWorkItem
from database.models.company import LoanCompany
from database.models.portfolio_risk import PortfolioRiskSnapshot
from database.models.predictive_intelligence import (
    PredictiveCashflowForecast,
    PredictiveIntelligenceRun,
    PredictiveLoanSignal,
)
from database.models.repayment import RepaymentInstallment
from services.portfolio_risk_service import dpd_bucket, generate_snapshot


MONEY = Decimal("0.01")
RATE = Decimal("0.0001")
LOOKBACK_DAYS = 90
ACTIVE_SNAPSHOT_STATUSES = {"approved", "active", "defaulted"}
BAND_ORDER = {"stable": 0, "watch": 1, "elevated": 2, "high": 3, "critical": 4}


def money(value: Any) -> Decimal:
    return Decimal(str(value or 0)).quantize(MONEY, rounding=ROUND_HALF_UP)


def ratio(value: Decimal) -> Decimal:
    return max(Decimal("0"), min(Decimal("1"), value)).quantize(RATE, rounding=ROUND_HALF_UP)


def risk_band(score: Decimal | int | float) -> str:
    value = Decimal(str(score or 0))
    if value >= 80:
        return "critical"
    if value >= 60:
        return "high"
    if value >= 40:
        return "elevated"
    if value >= 20:
        return "watch"
    return "stable"


def _previous_snapshot_date(db: Session, company_id: UUID, as_of: date) -> date | None:
    return db.query(func.max(PortfolioRiskSnapshot.snapshot_date)).filter(
        PortfolioRiskSnapshot.company_id == company_id,
        PortfolioRiskSnapshot.snapshot_date < as_of,
    ).scalar()


def _ensure_snapshot(db: Session, company_id: UUID, as_of: date, triggered_by_user_id: UUID | None) -> None:
    exists = db.query(PortfolioRiskSnapshot.id).filter(
        PortfolioRiskSnapshot.company_id == company_id,
        PortfolioRiskSnapshot.snapshot_date == as_of,
    ).first()
    if not exists:
        generate_snapshot(
            db,
            company_id=company_id,
            snapshot_date=as_of,
            triggered_by_user_id=triggered_by_user_id,
        )


def _collection_work_by_loan(db: Session, company_id: UUID, branch_id: UUID | None) -> dict[UUID, CollectionWorkItem]:
    query = db.query(CollectionWorkItem).filter(
        CollectionWorkItem.company_id == company_id,
        CollectionWorkItem.status.in_(["open", "in_progress"]),
    )
    if branch_id:
        query = query.filter(CollectionWorkItem.branch_id == branch_id)
    rows = query.order_by(CollectionWorkItem.priority_score.desc(), CollectionWorkItem.due_at.asc()).all()
    result: dict[UUID, CollectionWorkItem] = {}
    for row in rows:
        result.setdefault(row.loan_id, row)
    return result


def _score_signal(
    current: PortfolioRiskSnapshot,
    previous: PortfolioRiskSnapshot | None,
    work_item: CollectionWorkItem | None,
) -> tuple[Decimal, str, bool, str, list[str], str]:
    score = Decimal("0")
    reasons: list[str] = []
    dpd = int(current.days_past_due or 0)

    if dpd >= 90:
        score += 75
        reasons.append(f"Current delinquency is {dpd} days past due")
    elif dpd >= 60:
        score += 60
        reasons.append(f"Current delinquency is {dpd} days past due")
    elif dpd >= 30:
        score += 45
        reasons.append(f"Current delinquency is {dpd} days past due")
    elif dpd >= 8:
        score += 25
        reasons.append(f"Loan is already {dpd} days past due")
    elif dpd >= 1:
        score += 12
        reasons.append(f"Loan is {dpd} days past due")

    previous_dpd = int(previous.days_past_due) if previous else None
    dpd_change = dpd - previous_dpd if previous_dpd is not None else None
    if dpd_change is not None and dpd_change >= 15:
        score += 15
        reasons.append(f"DPD increased by {dpd_change} days since the prior stored snapshot")
    elif dpd_change is not None and dpd_change >= 7:
        score += 10
        reasons.append(f"DPD increased by {dpd_change} days since the prior stored snapshot")

    if previous and previous.delinquency_bucket != current.delinquency_bucket:
        bucket_order = {"current": 0, "1-7": 1, "8-30": 2, "31-60": 3, "61-90": 4, "90+": 5}
        if bucket_order.get(current.delinquency_bucket, 0) > bucket_order.get(previous.delinquency_bucket, 0):
            score += 8
            reasons.append(f"Delinquency bucket worsened from {previous.delinquency_bucket} to {current.delinquency_bucket}")

    if current.first_payment_default:
        score += 20
        reasons.append("First-payment-default evidence is present")
    if current.is_top_up and dpd > 0:
        score += 5
        reasons.append("This is a top-up exposure already showing repayment stress")

    if work_item:
        if work_item.priority in {"critical", "urgent"}:
            score += 10
            reasons.append(f"Collections already has a {work_item.priority} work item")
        elif work_item.priority == "high" or Decimal(str(work_item.priority_score or 0)) >= Decimal("70"):
            score += 6
            reasons.append("Collections already has a high-priority work item")

    score = min(Decimal("100"), score)
    band = risk_band(score)
    projected_par30 = 1 <= dpd < 30 and (
        dpd >= 8
        or bool(current.first_payment_default)
        or (dpd_change is not None and dpd_change >= 7)
    )
    stress_bucket = dpd_bucket(dpd + 30) if dpd > 0 else current.delinquency_bucket

    if band in {"critical", "high"}:
        action = "Review the loan and active collection evidence now, then assign or reprioritise the appropriate human recovery action."
    elif band == "elevated":
        action = "Prioritise a human account review and borrower contact before the next repayment date or collection cycle."
    elif band == "watch":
        action = "Monitor the next scheduled repayment and confirm that the collection route remains valid."
    else:
        action = "No predictive escalation is indicated; continue normal servicing and monitoring."

    return score, band, projected_par30, stress_bucket, reasons, action


def _cashflow_forecasts(
    db: Session,
    *,
    run: PredictiveIntelligenceRun,
    company_id: UUID,
    branch_id: UUID | None,
    as_of: date,
) -> list[PredictiveCashflowForecast]:
    history_start = as_of - timedelta(days=LOOKBACK_DAYS)
    history_query = db.query(RepaymentInstallment).join(
        ClientCompanyLoan, ClientCompanyLoan.id == RepaymentInstallment.loan_id
    ).filter(
        ClientCompanyLoan.company_id == company_id,
        RepaymentInstallment.is_superseded.is_(False),
        RepaymentInstallment.due_date >= history_start,
        RepaymentInstallment.due_date < as_of,
    )
    if branch_id:
        history_query = history_query.filter(ClientCompanyLoan.branch_id == branch_id)
    history = history_query.all()
    history_due = sum((money(row.total_due) for row in history), Decimal("0.00"))
    history_paid = sum((min(money(row.paid_amount), money(row.total_due)) for row in history), Decimal("0.00"))
    observed_rate = ratio(history_paid / history_due) if history_due > 0 else Decimal("0.0000")
    history_count = len(history)
    if history_count >= 50:
        confidence = "high"
    elif history_count >= 15:
        confidence = "medium"
    else:
        confidence = "low"
    method = "historical_collection_rate" if history_due > 0 else "contractual_no_history"

    results: list[PredictiveCashflowForecast] = []
    for horizon in (30, 60, 90):
        period_end = as_of + timedelta(days=horizon)
        future_query = db.query(RepaymentInstallment).join(
            ClientCompanyLoan, ClientCompanyLoan.id == RepaymentInstallment.loan_id
        ).filter(
            ClientCompanyLoan.company_id == company_id,
            RepaymentInstallment.is_superseded.is_(False),
            RepaymentInstallment.due_date >= as_of,
            RepaymentInstallment.due_date <= period_end,
            ClientCompanyLoan.balance > 0,
        )
        if branch_id:
            future_query = future_query.filter(ClientCompanyLoan.branch_id == branch_id)
        due_rows = future_query.all()
        contractual = sum(
            (max(money(row.total_due) - money(row.paid_amount), Decimal("0.00")) for row in due_rows),
            Decimal("0.00"),
        )
        expected = money(contractual * observed_rate) if history_due > 0 else money(contractual)
        note = (
            "Expected collection is contractual due multiplied by the observed lookback collection rate; it is not a guarantee."
            if history_due > 0
            else "No repayment history was available in the lookback window, so expected collection is shown as contractual due with low confidence."
        )
        forecast = PredictiveCashflowForecast(
            run_id=run.id,
            company_id=company_id,
            branch_id=branch_id,
            horizon_days=horizon,
            period_end=period_end,
            contractual_due=money(contractual),
            expected_collection=expected,
            observed_collection_rate=observed_rate,
            due_installment_count=len(due_rows),
            history_installment_count=history_count,
            confidence_band=confidence,
            method=method,
            evidence={
                "lookback_days": LOOKBACK_DAYS,
                "historical_due": str(money(history_due)),
                "historical_paid_against_due": str(money(history_paid)),
                "note": note,
            },
        )
        db.add(forecast)
        results.append(forecast)
    run.observed_collection_rate = observed_rate
    return results


def _employer_stress_alerts(snapshots: list[PortfolioRiskSnapshot]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = defaultdict(lambda: {"loan_count": 0, "exposure": Decimal("0.00"), "par30": Decimal("0.00")})
    for row in snapshots:
        if row.outstanding_balance <= 0:
            continue
        label = row.employer_label or "No employer group"
        group = groups[label]
        group["loan_count"] += 1
        group["exposure"] += money(row.outstanding_balance)
        if row.days_past_due >= 30:
            group["par30"] += money(row.outstanding_balance)
    alerts: list[dict[str, Any]] = []
    for label, group in groups.items():
        exposure = money(group["exposure"])
        par30 = money(group["par30"])
        par30_rate = float((par30 / exposure * Decimal("100")).quantize(Decimal("0.01"))) if exposure > 0 else 0.0
        if group["loan_count"] >= 2 and par30_rate >= 25:
            alerts.append({
                "employer_group": label,
                "loan_count": group["loan_count"],
                "exposure": float(exposure),
                "par30_exposure": float(par30),
                "par30_percent": par30_rate,
            })
    return sorted(alerts, key=lambda row: row["par30_exposure"], reverse=True)[:10]


def generate_predictive_run(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None = None,
    as_of: date | None = None,
    run_type: str = "on_demand",
    triggered_by_user_id: UUID | None = None,
) -> PredictiveIntelligenceRun:
    target = as_of or date.today()
    if target != date.today():
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Predictive runs use today's stored/live portfolio state; historical forecasts are not reconstructed")

    _ensure_snapshot(db, company_id, target, triggered_by_user_id)
    previous_date = _previous_snapshot_date(db, company_id, target)

    current_query = db.query(PortfolioRiskSnapshot).filter(
        PortfolioRiskSnapshot.company_id == company_id,
        PortfolioRiskSnapshot.snapshot_date == target,
        PortfolioRiskSnapshot.loan_status.in_(list(ACTIVE_SNAPSHOT_STATUSES)),
        PortfolioRiskSnapshot.outstanding_balance > 0,
    )
    if branch_id:
        current_query = current_query.filter(PortfolioRiskSnapshot.branch_id == branch_id)
    current_rows = current_query.all()

    previous_by_loan: dict[UUID, PortfolioRiskSnapshot] = {}
    if previous_date:
        previous_query = db.query(PortfolioRiskSnapshot).filter(
            PortfolioRiskSnapshot.company_id == company_id,
            PortfolioRiskSnapshot.snapshot_date == previous_date,
        )
        if branch_id:
            previous_query = previous_query.filter(PortfolioRiskSnapshot.branch_id == branch_id)
        previous_by_loan = {row.loan_id: row for row in previous_query.all()}

    now = datetime.now(timezone.utc)
    run = PredictiveIntelligenceRun(
        company_id=company_id,
        branch_id=branch_id,
        branch_scope_key=str(branch_id) if branch_id else "ALL",
        as_of_date=target,
        source_snapshot_date=target,
        previous_snapshot_date=previous_date,
        run_reference=f"PRED-{target:%Y%m%d}-{secrets.token_hex(4).upper()}",
        run_type=run_type,
        model_version="transparent-rules-v1",
        lookback_days=LOOKBACK_DAYS,
        triggered_by_user_id=triggered_by_user_id,
        generated_at=now,
    )
    db.add(run)
    db.flush()

    work_items = _collection_work_by_loan(db, company_id, branch_id)
    counts = defaultdict(int)
    projected_par30 = 0
    for current in current_rows:
        previous = previous_by_loan.get(current.loan_id)
        score, band, entering_par30, stress_bucket, reasons, action = _score_signal(
            current,
            previous,
            work_items.get(current.loan_id),
        )
        counts[band] += 1
        projected_par30 += int(entering_par30)
        evidence = current.evidence_snapshot or {}
        signal = PredictiveLoanSignal(
            run_id=run.id,
            company_id=company_id,
            branch_id=current.branch_id,
            loan_id=current.loan_id,
            borrower_id=current.borrower_id,
            folio_number=str(evidence.get("folio_number") or current.loan_id),
            loan_reference=evidence.get("loan_reference"),
            risk_score=score,
            risk_band=band,
            current_dpd=int(current.days_past_due or 0),
            previous_dpd=int(previous.days_past_due) if previous else None,
            dpd_change=(int(current.days_past_due or 0) - int(previous.days_past_due or 0)) if previous else None,
            current_bucket=current.delinquency_bucket,
            previous_bucket=previous.delinquency_bucket if previous else None,
            first_payment_default=bool(current.first_payment_default),
            projected_par30_entry=entering_par30,
            stress_bucket_30d=stress_bucket,
            outstanding_balance=money(current.outstanding_balance),
            rationale=reasons,
            recommended_action=action,
            evidence={
                "source_snapshot_date": target.isoformat(),
                "previous_snapshot_date": previous_date.isoformat() if previous_date else None,
                "overdue_amount": str(money(current.overdue_amount)),
                "collection_channel": current.collection_channel,
                "employer_label": current.employer_label,
                "is_top_up": bool(current.is_top_up),
                "scenario_note": "stress_bucket_30d shows the bucket reached if the current delinquency remains uncured for 30 more days; it is not a certainty.",
            },
        )
        db.add(signal)

    forecasts = _cashflow_forecasts(
        db,
        run=run,
        company_id=company_id,
        branch_id=branch_id,
        as_of=target,
    )
    run.loan_count = len(current_rows)
    run.stable_count = counts["stable"]
    run.watch_count = counts["watch"]
    run.elevated_count = counts["elevated"]
    run.high_count = counts["high"]
    run.critical_count = counts["critical"]
    run.projected_par30_entry_count = projected_par30
    run.summary = {
        "advisory_only": True,
        "calibrated_probability_model": False,
        "automatic_credit_decisions": False,
        "automatic_collection_actions": False,
        "method": "transparent rules over stored portfolio snapshots plus observed 90-day installment collection rate",
        "employer_stress_alerts": _employer_stress_alerts(current_rows),
        "cashflow": {
            str(row.horizon_days): {
                "contractual_due": float(row.contractual_due),
                "expected_collection": float(row.expected_collection),
                "confidence_band": row.confidence_band,
                "method": row.method,
            }
            for row in forecasts
        },
    }
    db.commit()
    db.refresh(run)
    return run


def run_payload(run: PredictiveIntelligenceRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "run_reference": run.run_reference,
        "run_type": run.run_type,
        "status": run.status,
        "model_version": run.model_version,
        "as_of_date": run.as_of_date.isoformat(),
        "source_snapshot_date": run.source_snapshot_date.isoformat(),
        "previous_snapshot_date": run.previous_snapshot_date.isoformat() if run.previous_snapshot_date else None,
        "loan_count": run.loan_count,
        "stable_count": run.stable_count,
        "watch_count": run.watch_count,
        "elevated_count": run.elevated_count,
        "high_count": run.high_count,
        "critical_count": run.critical_count,
        "projected_par30_entry_count": run.projected_par30_entry_count,
        "observed_collection_rate": float(run.observed_collection_rate or 0),
        "summary": run.summary or {},
        "generated_at": run.generated_at.isoformat(),
    }


def signal_payload(row: PredictiveLoanSignal) -> dict[str, Any]:
    return {
        "id": str(row.id), "run_id": str(row.run_id), "loan_id": str(row.loan_id),
        "borrower_id": str(row.borrower_id), "folio_number": row.folio_number,
        "loan_reference": row.loan_reference, "risk_score": float(row.risk_score or 0),
        "risk_band": row.risk_band, "current_dpd": row.current_dpd,
        "previous_dpd": row.previous_dpd, "dpd_change": row.dpd_change,
        "current_bucket": row.current_bucket, "previous_bucket": row.previous_bucket,
        "first_payment_default": row.first_payment_default,
        "projected_par30_entry": row.projected_par30_entry,
        "stress_bucket_30d": row.stress_bucket_30d,
        "outstanding_balance": float(row.outstanding_balance or 0),
        "rationale": row.rationale or [], "recommended_action": row.recommended_action,
        "evidence": row.evidence or {},
    }


def cashflow_payload(row: PredictiveCashflowForecast) -> dict[str, Any]:
    return {
        "id": str(row.id), "run_id": str(row.run_id), "horizon_days": row.horizon_days,
        "period_end": row.period_end.isoformat(), "contractual_due": float(row.contractual_due or 0),
        "expected_collection": float(row.expected_collection or 0),
        "observed_collection_rate": float(row.observed_collection_rate or 0),
        "due_installment_count": row.due_installment_count,
        "history_installment_count": row.history_installment_count,
        "confidence_band": row.confidence_band, "method": row.method, "evidence": row.evidence or {},
    }


def run_scheduled_predictive_intelligence(db: Session, local_date: date) -> dict[str, int]:
    result = {"companies_checked": 0, "runs_created": 0, "runs_skipped": 0}
    companies = db.query(LoanCompany).filter(LoanCompany.is_active.is_(True)).all()
    for company in companies:
        result["companies_checked"] += 1
        exists = db.query(PredictiveIntelligenceRun.id).filter(
            PredictiveIntelligenceRun.company_id == company.id,
            PredictiveIntelligenceRun.as_of_date == local_date,
            PredictiveIntelligenceRun.branch_scope_key == "ALL",
            PredictiveIntelligenceRun.run_type == "scheduled",
        ).first()
        if exists:
            result["runs_skipped"] += 1
            continue
        generate_predictive_run(
            db,
            company_id=company.id,
            as_of=local_date,
            run_type="scheduled",
            triggered_by_user_id=None,
        )
        result["runs_created"] += 1
    return result
