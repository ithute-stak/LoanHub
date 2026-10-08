from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.cdas_official import CdasOfficialMandateState
from database.models.lending_operations import CDASDeductionMandate, CDASRemittanceBatch
from services.cdas_config_service import get_configuration, selected_environment
from services.cdas_roster_intelligence import latest_roster_snapshot


ACTIVE_LIFECYCLES = {"approved", "active", "changed"}
PENDING_LIFECYCLES = {"registration_pending", "registered", "reviewed", "change_pending", "settlement_pending"}


def _money(value: Any) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def _month_start(value: date) -> date:
    return value.replace(day=1)


def _next_month(value: date) -> date:
    first = _month_start(value)
    return date(first.year + 1, 1, 1) if first.month == 12 else date(first.year, first.month + 1, 1)


def build_cdas_operations_kpis(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    current_date = today or date.today()
    configuration = get_configuration(db, company_id)
    environment = selected_environment(configuration)

    query = (
        db.query(CdasOfficialMandateState, CDASDeductionMandate)
        .join(CDASDeductionMandate, CDASDeductionMandate.id == CdasOfficialMandateState.mandate_id)
        .filter(
            CdasOfficialMandateState.company_id == company_id,
            CdasOfficialMandateState.environment == environment,
            CDASDeductionMandate.company_id == company_id,
        )
    )
    if branch_id is not None:
        query = query.filter(CDASDeductionMandate.branch_id == branch_id)
    rows = query.all()

    active_rows = []
    pending_rows = []
    reconciliation_rows = []
    settled_rows = []
    monthly_active = Decimal("0.00")
    active_clients: set[UUID] = set()
    due_to_end_60 = 0
    due_to_start_30 = 0

    start_window_end = current_date + timedelta(days=30)
    end_window_end = current_date + timedelta(days=60)

    for state, mandate in rows:
        lifecycle = str(state.lifecycle_status or "").strip().lower()
        if state.requires_reconciliation:
            reconciliation_rows.append((state, mandate))
        if lifecycle in ACTIVE_LIFECYCLES:
            active_rows.append((state, mandate))
            monthly_active += max(_money(mandate.monthly_deduction), Decimal("0.00"))
            active_clients.add(mandate.borrower_id)
            if mandate.end_date and current_date <= mandate.end_date <= end_window_end:
                due_to_end_60 += 1
        elif lifecycle in PENDING_LIFECYCLES:
            pending_rows.append((state, mandate))
            if current_date <= mandate.start_date <= start_window_end:
                due_to_start_30 += 1
        elif lifecycle == "settled":
            settled_rows.append((state, mandate))

    batch_query = db.query(CDASRemittanceBatch).filter(CDASRemittanceBatch.company_id == company_id)
    if branch_id is not None:
        # CDASRemittanceBatch is company-wide; keep the KPI company-wide rather
        # than pretending branch attribution exists where the schema does not.
        pass
    latest_batch = batch_query.order_by(CDASRemittanceBatch.payroll_month.desc(), CDASRemittanceBatch.created_at.desc()).first()

    next_month = _next_month(current_date)
    projected_next = Decimal("0.00")
    for state, mandate in rows:
        lifecycle = str(state.lifecycle_status or "").strip().lower()
        if lifecycle not in ACTIVE_LIFECYCLES | {"approved"}:
            continue
        if mandate.start_date >= _next_month(next_month):
            continue
        if mandate.end_date and mandate.end_date < next_month:
            continue
        projected_next += max(_money(mandate.monthly_deduction), Decimal("0.00"))

    roster = latest_roster_snapshot(db, company_id=company_id)
    roster_employee_count = int((roster or {}).get("employee_count") or 0)
    roster_total = _money((roster or {}).get("total_monthly_deductions"))

    reconciliation_amount = sum(
        (max(_money(mandate.monthly_deduction), Decimal("0.00")) for _, mandate in reconciliation_rows),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    return {
        "environment": environment,
        "as_of": current_date.isoformat(),
        "currency": "LSL",
        "active_deduction_count": len(active_rows),
        "active_client_count": len(active_clients),
        "monthly_active_deductions": float(monthly_active.quantize(Decimal("0.01"))),
        "pending_lifecycle_count": len(pending_rows),
        "requires_reconciliation_count": len(reconciliation_rows),
        "requires_reconciliation_monthly_amount": float(reconciliation_amount),
        "settled_count": len(settled_rows),
        "starting_within_30_days": due_to_start_30,
        "ending_within_60_days": due_to_end_60,
        "projected_next_month": {
            "month": next_month.strftime("%Y-%m"),
            "monthly_amount": float(projected_next.quantize(Decimal("0.01"))),
        },
        "roster": {
            "available": roster is not None,
            "captured_at": (roster or {}).get("captured_at"),
            "employee_count": roster_employee_count,
            "monthly_deductions": float(roster_total),
            "provider_year": (roster or {}).get("provider_year"),
            "provider_month": (roster or {}).get("provider_month"),
        },
        "latest_remittance": {
            "available": latest_batch is not None,
            "payroll_month": latest_batch.payroll_month.isoformat() if latest_batch else None,
            "status": latest_batch.status if latest_batch else None,
            "expected_amount": float(_money(latest_batch.expected_amount)) if latest_batch else 0.0,
            "received_amount": float(_money(latest_batch.received_amount)) if latest_batch else 0.0,
            "matched_amount": float(_money(latest_batch.matched_amount)) if latest_batch else 0.0,
            "exception_amount": float(_money(latest_batch.exception_amount)) if latest_batch else 0.0,
            "exception_count": int(latest_batch.exception_count or 0) if latest_batch else 0,
        },
        "methodology": (
            "Operational CDAS run-rate based on LoanHub-linked mandate/provider state. "
            "Roster intelligence is provider-document evidence; cash receipt remains governed by remittance reconciliation."
        ),
    }
