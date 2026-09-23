from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.branch import CompanyBranch
from database.models.cdas_booking import CdasBookingOpportunity
from database.models.cdas_official import CdasOfficialMandateState
from database.models.company_staff import CompanyStaff
from database.models.lending_operations import CDASDeductionMandate, CDASPayrollProfile
from database.models.person import Person
from database.models.user import User
from services.cdas_config_service import get_configuration


ACTIVE_LIFECYCLES = {"active", "changed"}
PENDING_LIFECYCLES = {"registered", "reserved", "reviewed", "approved"}
FORECAST_PENDING_LIFECYCLES = {"approved"}


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(Decimal("0.01"))
    except Exception:
        return Decimal("0.00")


def month_bounds(value: date) -> tuple[date, date]:
    start = value.replace(day=1)
    if start.month == 12:
        next_start = date(start.year + 1, 1, 1)
    else:
        next_start = date(start.year, start.month + 1, 1)
    return start, next_start - timedelta(days=1)


def shift_month(value: date, offset: int) -> date:
    month_index = value.year * 12 + (value.month - 1) + offset
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 1)


def movement(current: object, previous: object) -> dict[str, Any]:
    current_value = _money(current)
    previous_value = _money(previous)
    difference = current_value - previous_value
    if previous_value > 0:
        percent: float | None = float((difference / previous_value * Decimal("100")).quantize(Decimal("0.01")))
    elif current_value > 0:
        percent = None
    else:
        percent = 0.0

    if current_value > 0 and previous_value <= 0:
        direction = "new_book"
    elif difference > 0:
        direction = "growth"
    elif difference < 0:
        direction = "decay"
    else:
        direction = "stable"

    return {
        "amount": float(difference),
        "percent": percent,
        "direction": direction,
    }


def _date_value(value: datetime | date | None) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value


def _stop_date(state: CdasOfficialMandateState, mandate: CDASDeductionMandate) -> date | None:
    candidates = [
        mandate.end_date,
        _date_value(state.settled_at),
        _date_value(state.cancelled_at),
        _date_value(mandate.completed_at),
    ]
    values = [candidate for candidate in candidates if candidate is not None]
    return min(values) if values else None


def _was_active_during(
    state: CdasOfficialMandateState,
    mandate: CDASDeductionMandate,
    period_start: date,
    period_end: date,
) -> bool:
    activated = _date_value(mandate.activated_at)
    if activated is None or activated > period_end:
        return False
    start = max(mandate.start_date, activated)
    stop = _stop_date(state, mandate)
    return start <= period_end and (stop is None or stop >= period_start)


def run_rate_for_period(
    rows: Iterable[tuple[CdasOfficialMandateState, CDASDeductionMandate]],
    period_start: date,
    period_end: date,
) -> Decimal:
    total = Decimal("0.00")
    for state, mandate in rows:
        if _was_active_during(state, mandate, period_start, period_end):
            total += max(_money(mandate.monthly_deduction), Decimal("0.00"))
    return total.quantize(Decimal("0.01"))


def _active_today(state: CdasOfficialMandateState, mandate: CDASDeductionMandate, today: date) -> bool:
    if str(state.lifecycle_status or "").lower() not in ACTIVE_LIFECYCLES:
        return False
    activated = _date_value(mandate.activated_at)
    if activated is None or activated > today or mandate.start_date > today:
        return False
    stop = _stop_date(state, mandate)
    return stop is None or stop >= today


def _snapshot_matches_environment(snapshot: dict[str, Any], environment: str | None) -> bool:
    snapshot_environment = str(snapshot.get("environment") or "").strip().lower()
    if snapshot_environment:
        return snapshot_environment == str(environment or "").lower()
    # Existing snapshots created before environment tagging came from the Test
    # integration. Never carry an untagged snapshot into Live reporting.
    return str(environment or "test").lower() == "test"


def summarize_active_book(
    rows: Iterable[tuple[CdasOfficialMandateState, CDASDeductionMandate]],
    *,
    branch_names: dict[UUID, str] | None = None,
    officer_names: dict[UUID, str] | None = None,
    limit: int = 5,
) -> dict[str, list[dict[str, Any]]]:
    """Summarize active CDAS book by branch and mandate-registering officer.

    Input rows are already tenant/environment/branch scoped by the caller. Keeping
    aggregation here makes the ranking deterministic and unit-testable without
    loading raw mandate detail into the browser.
    """
    branch_names = branch_names or {}
    officer_names = officer_names or {}
    branch_totals: dict[UUID | None, dict[str, Any]] = defaultdict(
        lambda: {"active_deduction_count": 0, "client_ids": set(), "monthly_amount": Decimal("0.00")}
    )
    officer_totals: dict[UUID, dict[str, Any]] = defaultdict(
        lambda: {"active_deduction_count": 0, "client_ids": set(), "monthly_amount": Decimal("0.00")}
    )

    for _, mandate in rows:
        amount = max(_money(mandate.monthly_deduction), Decimal("0.00"))
        branch_bucket = branch_totals[getattr(mandate, "branch_id", None)]
        branch_bucket["active_deduction_count"] += 1
        branch_bucket["client_ids"].add(mandate.borrower_id)
        branch_bucket["monthly_amount"] += amount

        officer_id = getattr(mandate, "created_by_user_id", None)
        if officer_id:
            officer_bucket = officer_totals[officer_id]
            officer_bucket["active_deduction_count"] += 1
            officer_bucket["client_ids"].add(mandate.borrower_id)
            officer_bucket["monthly_amount"] += amount

    branches = [
        {
            "branch_id": str(branch_id) if branch_id else None,
            "name": branch_names.get(branch_id, "Unassigned branch") if branch_id else "Unassigned branch",
            "active_deduction_count": values["active_deduction_count"],
            "active_client_count": len(values["client_ids"]),
            "monthly_amount": float(values["monthly_amount"].quantize(Decimal("0.01"))),
        }
        for branch_id, values in branch_totals.items()
    ]
    officers = [
        {
            "user_id": str(user_id),
            "name": officer_names.get(user_id, "Company staff"),
            "active_deduction_count": values["active_deduction_count"],
            "active_client_count": len(values["client_ids"]),
            "monthly_amount": float(values["monthly_amount"].quantize(Decimal("0.01"))),
        }
        for user_id, values in officer_totals.items()
    ]

    sort_key = lambda item: (-float(item["monthly_amount"]), -int(item["active_deduction_count"]), str(item["name"]).casefold())
    branches.sort(key=sort_key)
    officers.sort(key=sort_key)
    return {"branches": branches[:limit], "officers": officers[:limit]}


def _active_book_names(
    db: Session,
    *,
    company_id: UUID,
    rows: Iterable[tuple[CdasOfficialMandateState, CDASDeductionMandate]],
) -> tuple[dict[UUID, str], dict[UUID, str]]:
    mandates = [mandate for _, mandate in rows]
    branch_ids = {mandate.branch_id for mandate in mandates if mandate.branch_id}
    officer_ids = {mandate.created_by_user_id for mandate in mandates if mandate.created_by_user_id}

    branch_names: dict[UUID, str] = {}
    if branch_ids:
        branch_names = {
            branch.id: branch.name
            for branch in db.query(CompanyBranch)
            .filter(CompanyBranch.company_id == company_id, CompanyBranch.id.in_(branch_ids))
            .all()
        }

    officer_names: dict[UUID, str] = {}
    if officer_ids:
        staff_rows = (
            db.query(CompanyStaff, User, Person)
            .join(User, User.id == CompanyStaff.user_id)
            .outerjoin(Person, Person.user_id == User.id)
            .filter(
                CompanyStaff.company_id == company_id,
                CompanyStaff.user_id.in_(officer_ids),
                CompanyStaff.is_active.is_(True),
            )
            .all()
        )
        for staff, user, person in staff_rows:
            if staff.user_id in officer_names:
                continue
            if person:
                name = person.full_name
            else:
                name = str(user.email or user.phone or "Company staff")
            officer_names[staff.user_id] = name

    return branch_names, officer_names


def build_company_cdas_dashboard_kpis(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    today = today or date.today()
    configuration = get_configuration(db, company_id)
    environment = str(getattr(configuration, "environment", "test") or "test").strip().lower()
    configured = bool(configuration and configuration.is_enabled)

    query = (
        db.query(CdasOfficialMandateState, CDASDeductionMandate)
        .join(CDASDeductionMandate, CDASDeductionMandate.id == CdasOfficialMandateState.mandate_id)
        .filter(
            CdasOfficialMandateState.company_id == company_id,
            CDASDeductionMandate.company_id == company_id,
            CdasOfficialMandateState.environment == environment,
        )
    )
    if branch_id:
        query = query.filter(CDASDeductionMandate.branch_id == branch_id)
    rows = query.all()

    current_active = [
        (state, mandate)
        for state, mandate in rows
        if _active_today(state, mandate, today)
    ]
    current_total = sum(
        (max(_money(mandate.monthly_deduction), Decimal("0.00")) for _, mandate in current_active),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    active_clients = len({mandate.borrower_id for _, mandate in current_active})
    branch_names, officer_names = _active_book_names(
        db,
        company_id=company_id,
        rows=current_active,
    )
    active_book = summarize_active_book(
        current_active,
        branch_names=branch_names,
        officer_names=officer_names,
    )

    current_start, current_end = month_bounds(today)
    previous_start = shift_month(current_start, -1)
    previous_start, previous_end = month_bounds(previous_start)
    next_start = shift_month(current_start, 1)
    next_start, next_end = month_bounds(next_start)

    previous_total = run_rate_for_period(rows, previous_start, previous_end)
    current_movement = movement(current_total, previous_total)

    soon_start = today
    soon_end = today + timedelta(days=30)
    expiring_end = today + timedelta(days=60)

    soon_commencing_rows = []
    for state, mandate in rows:
        lifecycle = str(state.lifecycle_status or "").lower()
        if lifecycle in PENDING_LIFECYCLES and soon_start <= mandate.start_date <= soon_end:
            soon_commencing_rows.append((state, mandate))

    soon_expiring_rows = []
    for state, mandate in current_active:
        if mandate.end_date and today <= mandate.end_date <= expiring_end:
            soon_expiring_rows.append((state, mandate))

    soon_commencing_amount = sum(
        (max(_money(mandate.monthly_deduction), Decimal("0.00")) for _, mandate in soon_commencing_rows),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    soon_expiring_amount = sum(
        (max(_money(mandate.monthly_deduction), Decimal("0.00")) for _, mandate in soon_expiring_rows),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    projected_next = run_rate_for_period(rows, next_start, next_end)
    for state, mandate in rows:
        lifecycle = str(state.lifecycle_status or "").lower()
        if lifecycle not in FORECAST_PENDING_LIFECYCLES:
            continue
        if mandate.start_date > next_end:
            continue
        stop = _stop_date(state, mandate)
        if stop is not None and stop < next_start:
            continue
        projected_next += max(_money(mandate.monthly_deduction), Decimal("0.00"))
    projected_next = projected_next.quantize(Decimal("0.01"))
    projected_movement = movement(projected_next, current_total)

    borrower_ids: set[UUID] | None = None
    if branch_id:
        borrower_ids = {
            row[0]
            for row in db.query(CDASPayrollProfile.borrower_id)
            .filter(
                CDASPayrollProfile.company_id == company_id,
                CDASPayrollProfile.branch_id == branch_id,
                CDASPayrollProfile.verified.is_(True),
            )
            .all()
        }

    opportunities = (
        db.query(CdasBookingOpportunity)
        .filter(CdasBookingOpportunity.company_id == company_id)
        .all()
    )
    ready_for_review = 0
    no_capacity = 0
    potential_additional = Decimal("0.00")
    latest_daily_check: str | None = None
    daily_failures = 0
    for opportunity in opportunities:
        snapshot = dict(opportunity.analysis_snapshot or {})
        if snapshot.get("source") != "CDAS_DAILY_INTELLIGENCE":
            continue
        if not _snapshot_matches_environment(snapshot, environment):
            continue
        if borrower_ids is not None:
            try:
                snapshot_borrower = UUID(str(snapshot.get("borrower_id")))
            except Exception:
                continue
            if snapshot_borrower not in borrower_ids:
                continue

        check_date = str(snapshot.get("last_check_date") or snapshot.get("local_date") or "")
        if check_date and (latest_daily_check is None or check_date > latest_daily_check):
            latest_daily_check = check_date
        if str(snapshot.get("last_check_status") or "success").lower() == "failed":
            if check_date == today.isoformat():
                daily_failures += 1
            continue

        action = str(snapshot.get("recommended_action") or "")
        if action == "READY_FOR_COLLECTION_REVIEW":
            ready_for_review += 1
            potential_additional += max(_money(snapshot.get("suggested_monthly_deduction")), Decimal("0.00"))
        elif action == "MONITOR_NO_CAPACITY":
            no_capacity += 1

    history = []
    for offset in range(-5, 1):
        month_start = shift_month(current_start, offset)
        month_start, month_end = month_bounds(month_start)
        value = current_total if offset == 0 else run_rate_for_period(rows, month_start, month_end)
        history.append({"month": month_start.strftime("%Y-%m"), "amount": float(value)})

    nearest_commencement = min((mandate.start_date for _, mandate in soon_commencing_rows), default=None)
    nearest_expiry = min((mandate.end_date for _, mandate in soon_expiring_rows if mandate.end_date), default=None)

    return {
        "configured": configured,
        "environment": environment,
        "as_of": today.isoformat(),
        "currency": "LSL",
        "active_deduction_count": len(current_active),
        "active_client_count": active_clients,
        "monthly_active_deductions": float(current_total),
        "previous_month_deductions": float(previous_total),
        "month_movement": current_movement,
        "soon_commencing": {
            "days": 30,
            "count": len(soon_commencing_rows),
            "monthly_amount": float(soon_commencing_amount),
            "nearest_date": nearest_commencement.isoformat() if nearest_commencement else None,
        },
        "soon_expiring": {
            "days": 60,
            "count": len(soon_expiring_rows),
            "monthly_amount": float(soon_expiring_amount),
            "nearest_date": nearest_expiry.isoformat() if nearest_expiry else None,
        },
        "projected_next_month": {
            "month": next_start.strftime("%Y-%m"),
            "monthly_amount": float(projected_next),
            "movement": projected_movement,
            "basis": "Known active schedules plus approved deductions expected to remain in force next month",
        },
        "ready_for_collection_review": ready_for_review,
        "monitor_no_capacity": no_capacity,
        "potential_additional_monthly_deduction": float(potential_additional.quantize(Decimal("0.01"))),
        "latest_daily_check": latest_daily_check,
        "daily_check_failures_today": daily_failures,
        "run_rate_history": history,
        "top_branches": active_book["branches"],
        "top_officers": active_book["officers"],
        "methodology": "Contracted CDAS monthly run-rate from LoanHub-linked mandates. This is not proof of payroll cash receipt; actual receipts remain subject to remittance/payment reconciliation.",
    }
