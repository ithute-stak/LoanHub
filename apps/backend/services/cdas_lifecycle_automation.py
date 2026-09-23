from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session

from database.models.cdas_booking import CdasBookingOpportunity
from database.models.cdas_official import CdasOfficialMandateState
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus
from database.models.lending_operations import CDASDeductionMandate
from database.models.origination import OriginationIntegrationConfiguration
from integrations.cdas import CdasClient, CdasError
from services.cdas_config_service import CDAS_PROVIDER, get_company_cdas_client
from services.cdas_crash_safe_lifecycle import settle_linked_deduction
from services.cdas_deduction_lifecycle import (
    CdasLifecycleError,
    _apply_provider_response,
    _record_event,
    _utcnow,
)
from services.cdas_monthly_automation import (
    AUTOMATION_AUTHORIZATION_BASIS,
    AUTOMATION_SOURCE,
    get_monthly_automation_configuration,
    is_monthly_automation_window,
    local_now,
)


RECONCILIATION_OPERATION = "FULL_STATUS_RECONCILIATION"
AUTO_SETTLEMENT_OPERATION = "AUTO_SETTLEMENT"
SETTLEMENT_REASON_PAID_BY_EMPLOYEE = 2
SETTLEMENT_REASON_CONSOLIDATION = 3
_MONEY_QUANTUM = Decimal("0.01")

# CDAS v1.5 lifecycle/status codes that can be supplied to view-deduction.
_ALL_RECONCILIATION_STATUSES = (1, 2, 3, 4, 5, 10, 6, 7, 8, 9)
_RECONCILABLE_LIFECYCLES = {
    "registration_submission_pending",
    "registration_pending",
    "registered",
    "reserved",
    "reviewed",
    "approved",
    "active",
    "changed",
    "reconciliation_required",
}


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(_MONEY_QUANTUM)
    except Exception:
        return Decimal("0.00")


def _value(payload: Any, *keys: str) -> Any:
    if not isinstance(payload, dict):
        return None
    values = {str(key).lower(): value for key, value in payload.items()}
    for key in keys:
        if key.lower() in values:
            return values[key.lower()]
    return None


def _to_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def reconciliation_status_order(lifecycle_status: str | None, cdas_status: int | None = None) -> tuple[int, ...]:
    """Return a call-efficient, forward-looking provider status search order.

    The own-deduction endpoint requires a status code. We search the local/current
    state first and then only plausible forward/terminal states. A mandate already
    flagged for reconciliation receives the full documented status search.
    """

    lifecycle = str(lifecycle_status or "").strip().lower()
    orders: dict[str, tuple[int, ...]] = {
        "registration_submission_pending": (1, 2, 3, 4, 5, 10, 6, 7, 8, 9),
        "registration_pending": (1, 2, 3, 4, 5, 10, 6, 7, 8, 9),
        "registered": (1, 2, 3, 4, 5, 10, 6, 7, 8, 9),
        "reserved": (2, 3, 4, 5, 10, 6, 7, 8, 9),
        "reviewed": (3, 4, 5, 10, 6, 7, 8, 9),
        "approved": (4, 5, 10, 7, 8, 6, 9),
        "active": (5, 10, 7, 8, 6, 9),
        "changed": (10, 5, 7, 8, 6, 9),
        "cancelled_or_rejected": (6, 9),
        "settled": (7, 8, 9),
        "expired_or_auto_settled": (8, 7, 9),
        "deleted": (9,),
        "reconciliation_required": _ALL_RECONCILIATION_STATUSES,
    }
    requested = orders.get(lifecycle, _ALL_RECONCILIATION_STATUSES)

    values: list[int] = []
    if cdas_status in _ALL_RECONCILIATION_STATUSES:
        values.append(int(cdas_status))
    for status in requested:
        if status not in values:
            values.append(status)
    return tuple(values)


def automatic_settlement_reason(*, outstanding_balance: object, has_consolidation_successor: bool) -> int | None:
    """Return a safe automatic settlement reason or None.

    Automatic settlement is intentionally stricter than the manual endpoint: the
    LoanHub balance must already be zero. A disbursed top-up that explicitly
    settled this loan is treated as consolidation; otherwise the debt is treated
    as paid by the employee. Policy-expiry and deceased-employee reasons remain
    outside automatic processing because they require different evidence.
    """

    if _money(outstanding_balance) > Decimal("0.00"):
        return None
    return SETTLEMENT_REASON_CONSOLIDATION if has_consolidation_successor else SETTLEMENT_REASON_PAID_BY_EMPLOYEE


def _marker_reference(operation: str, state_id: UUID, run_date: date) -> str:
    return f"{operation}:{state_id}:{run_date.isoformat()}"


def _marker_exists(
    db: Session,
    *,
    company_id: UUID,
    operation: str,
    state_id: UUID,
    run_date: date,
) -> bool:
    return (
        db.query(CdasBookingOpportunity.id)
        .filter(
            CdasBookingOpportunity.company_id == company_id,
            CdasBookingOpportunity.client_reference == _marker_reference(operation, state_id, run_date),
        )
        .first()
        is not None
    )


def _create_marker(
    db: Session,
    *,
    company_id: UUID,
    operation: str,
    state: CdasOfficialMandateState,
    mandate: CDASDeductionMandate,
    run_date: date,
) -> CdasBookingOpportunity:
    marker = CdasBookingOpportunity(
        company_id=company_id,
        client_reference=_marker_reference(operation, state.id, run_date),
        status="monitoring",
        pipeline_stage="identified",
        opportunity_item_code=state.item_code,
        opportunity_reference_no=state.reference_no,
        opportunity_deduction_amount=mandate.monthly_deduction,
        analysis_snapshot={
            "source": AUTOMATION_SOURCE,
            "operation": operation,
            "authorization_basis": AUTOMATION_AUTHORIZATION_BASIS,
            "state_id": str(state.id),
            "mandate_id": str(mandate.id),
            "borrower_id": str(mandate.borrower_id),
            "loan_id": str(mandate.loan_id),
            "employee_no": mandate.employee_number,
            "deduction_id": state.deduction_id,
            "last_check_date": run_date.isoformat(),
            "last_check_status": "started",
            "provider_reads": 0,
            "provider_writes": 0,
        },
    )
    db.add(marker)
    db.commit()
    db.refresh(marker)
    return marker


def _finish_marker(db: Session, marker: CdasBookingOpportunity, snapshot: dict[str, Any]) -> None:
    marker.analysis_snapshot = snapshot
    if snapshot.get("settled", 0) or snapshot.get("reconciled", 0):
        marker.status = "booked"
        marker.pipeline_stage = "booked"
        marker.booked_at = marker.booked_at or _utcnow()
    else:
        marker.status = "monitoring"
        marker.pipeline_stage = "identified"
    db.commit()


def _match_provider_item(
    items: list[dict[str, Any]],
    *,
    state: CdasOfficialMandateState,
) -> dict[str, Any] | None:
    id_matches: list[dict[str, Any]] = []
    reference_matches: list[dict[str, Any]] = []
    local_id = int(state.deduction_id) if state.deduction_id is not None else None
    local_reference = str(state.reference_no or "").strip()

    for item in items:
        provider_id = _to_int(_value(item, "DeductionID", "DeductionId", "deduction_id"))
        provider_reference = str(_value(item, "ReferenceNo", "ReferenceNumber", "reference_no") or "").strip()
        if local_id is not None and provider_id == local_id:
            id_matches.append(item)
        elif local_reference and provider_reference == local_reference:
            reference_matches.append(item)

    if len(id_matches) > 1 or (not id_matches and len(reference_matches) > 1):
        raise CdasLifecycleError(409, "CDAS returned duplicate deductions matching the same LoanHub mandate")
    if id_matches:
        return id_matches[0]
    if reference_matches:
        return reference_matches[0]
    return None


def _provider_effective_month(item: dict[str, Any]) -> str | None:
    raw = _value(item, "EffectiveMonth", "effective_month", "EffectiveDate", "effective_date")
    if raw is None:
        return None
    text = str(raw).strip()
    if len(text) >= 7 and text[4:5] == "-" and text[:4].isdigit() and text[5:7].isdigit():
        month = int(text[5:7])
        if 1 <= month <= 12:
            return text[:7]
    return None


def _sync_provider_snapshot(
    *,
    state: CdasOfficialMandateState,
    mandate: CDASDeductionMandate,
    item: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    before = {
        "lifecycle_status": state.lifecycle_status,
        "cdas_status": state.cdas_status,
        "deduction_id": state.deduction_id,
        "deduction_amount": float(_money(mandate.monthly_deduction)),
        "principal_amount": float(_money(state.principal_amount)),
        "total_installment": int(mandate.expected_installments or 0),
        "effective_month": state.effective_month,
    }

    complete = _apply_provider_response(
        state,
        mandate,
        item,
        requested_lifecycle=str(state.lifecycle_status or "reconciled"),
        require_status=True,
    )
    if not complete:
        raise CdasLifecycleError(502, state.last_error or "CDAS returned an incomplete reconciliation response")

    provider_amount = _value(item, "DeductionAmount", "deduction_amount")
    if provider_amount is not None:
        amount = _money(provider_amount)
        if amount > Decimal("0.00"):
            mandate.monthly_deduction = amount

    provider_principal = _value(item, "PrincipalAmount", "principal_amount")
    if provider_principal is not None:
        principal = _money(provider_principal)
        if principal > Decimal("0.00"):
            state.principal_amount = principal
            mandate.total_expected = principal

    provider_installments = _to_int(_value(item, "TotalInstallment", "TotalInstalment", "total_installment"))
    if provider_installments is not None and provider_installments > 0:
        mandate.expected_installments = provider_installments

    effective_month = _provider_effective_month(item)
    if effective_month:
        state.effective_month = effective_month
        year, month = (int(part) for part in effective_month.split("-"))
        mandate.start_date = date(year, month, 1)

    after = {
        "lifecycle_status": state.lifecycle_status,
        "cdas_status": state.cdas_status,
        "deduction_id": state.deduction_id,
        "deduction_amount": float(_money(mandate.monthly_deduction)),
        "principal_amount": float(_money(state.principal_amount)),
        "total_installment": int(mandate.expected_installments or 0),
        "effective_month": state.effective_month,
    }
    return {
        key: {"before": before[key], "after": after[key]}
        for key in before
        if before[key] != after[key]
    }


def _company_automation_enabled(db: Session, company_id: UUID) -> bool:
    row = (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == company_id,
            OriginationIntegrationConfiguration.provider == CDAS_PROVIDER,
        )
        .one_or_none()
    )
    if row is None or not row.is_enabled:
        return False
    return bool(get_monthly_automation_configuration(row)["enabled"])


async def process_company_status_reconciliation(
    db: Session,
    *,
    company_id: UUID,
    run_date: date,
) -> dict[str, int]:
    summary = {
        "candidates": 0,
        "checked": 0,
        "reconciled": 0,
        "status_updates": 0,
        "mirror_updates": 0,
        "missing_provider": 0,
        "failed": 0,
        "skipped": 0,
        "provider_reads": 0,
    }
    if not _company_automation_enabled(db, company_id):
        return summary

    rows = (
        db.query(CdasOfficialMandateState, CDASDeductionMandate)
        .join(CDASDeductionMandate, CDASDeductionMandate.id == CdasOfficialMandateState.mandate_id)
        .filter(
            CdasOfficialMandateState.company_id == company_id,
            CDASDeductionMandate.company_id == company_id,
            or_(
                CdasOfficialMandateState.requires_reconciliation.is_(True),
                CdasOfficialMandateState.lifecycle_status.in_(tuple(_RECONCILABLE_LIFECYCLES)),
            ),
        )
        .order_by(CDASDeductionMandate.employee_number.asc(), CdasOfficialMandateState.id.asc())
        .all()
    )
    summary["candidates"] = len(rows)
    if not rows:
        return summary

    client = get_company_cdas_client(db, company_id)
    cache: dict[tuple[str, int], list[dict[str, Any]]] = {}

    for state, mandate in rows:
        if _marker_exists(
            db,
            company_id=company_id,
            operation=RECONCILIATION_OPERATION,
            state_id=state.id,
            run_date=run_date,
        ):
            summary["skipped"] += 1
            continue

        marker = _create_marker(
            db,
            company_id=company_id,
            operation=RECONCILIATION_OPERATION,
            state=state,
            mandate=mandate,
            run_date=run_date,
        )
        snapshot = dict(marker.analysis_snapshot or {})
        snapshot["last_check_status"] = "success"
        local_reads = 0
        searched: list[int] = []

        try:
            employee_no = str(mandate.employee_number or "").strip()
            if not employee_no:
                raise CdasLifecycleError(422, "Stored CDAS employee number is required for reconciliation")

            matched: dict[str, Any] | None = None
            matched_status: int | None = None
            for status in reconciliation_status_order(state.lifecycle_status, state.cdas_status):
                searched.append(status)
                key = (employee_no, status)
                if key not in cache:
                    cache[key] = await client.own_deductions(employee_no, status)
                    summary["provider_reads"] += 1
                    local_reads += 1
                matched = _match_provider_item(cache[key], state=state)
                if matched is not None:
                    matched_status = status
                    break

            summary["checked"] += 1
            snapshot["provider_reads"] = local_reads
            snapshot["searched_statuses"] = searched

            if matched is None:
                state.requires_reconciliation = True
                state.lifecycle_status = "reconciliation_required"
                state.last_error = (
                    "LoanHub could not find this mandate in CDAS own deductions across the documented lifecycle statuses"
                )
                state.last_synced_at = _utcnow()
                _record_event(
                    db,
                    state=state,
                    actor_user_id=None,
                    event_type="automatic_reconciliation",
                    request_type=None,
                    request_snapshot={
                        "Automation": True,
                        "EmployeeNo": employee_no,
                        "SearchedStatuses": searched,
                    },
                    success=False,
                    message=state.last_error,
                )
                summary["missing_provider"] += 1
                snapshot["last_check_status"] = "degraded"
                snapshot["recommended_action"] = "RECONCILIATION_REQUIRED_PROVIDER_RECORD_NOT_FOUND"
                db.commit()
                _finish_marker(db, marker, snapshot)
                continue

            previous_lifecycle = str(state.lifecycle_status or "")
            changes = _sync_provider_snapshot(state=state, mandate=mandate, item=matched)
            if "lifecycle_status" in changes or "cdas_status" in changes:
                summary["status_updates"] += 1
            if any(
                key in changes
                for key in {"deduction_id", "deduction_amount", "principal_amount", "total_installment", "effective_month"}
            ):
                summary["mirror_updates"] += 1

            _record_event(
                db,
                state=state,
                actor_user_id=None,
                event_type="automatic_reconciliation",
                request_type=None,
                request_snapshot={
                    "Automation": True,
                    "EmployeeNo": employee_no,
                    "SearchedStatuses": searched,
                    "PreviousLifecycle": previous_lifecycle,
                },
                response_snapshot=matched,
                provider_status_code=200,
                success=True,
                message="LoanHub CDAS mirror reconciled with the provider",
            )
            db.commit()
            summary["reconciled"] += 1
            snapshot["reconciled"] = 1
            snapshot["matched_status"] = matched_status
            snapshot["provider_status"] = state.cdas_status
            snapshot["lifecycle_status"] = state.lifecycle_status
            snapshot["changes"] = changes
            snapshot["recommended_action"] = "RECONCILED"
        except CdasError as exc:
            summary["failed"] += 1
            snapshot["last_check_status"] = "failed"
            snapshot["provider_reads"] = local_reads
            snapshot["searched_statuses"] = searched
            snapshot["error"] = exc.message
            snapshot["provider_status_code"] = exc.status_code
            snapshot["recommended_action"] = "RETRY_ON_NEXT_MONTHLY_WINDOW_CHECK"
        except CdasLifecycleError as exc:
            state.requires_reconciliation = True
            state.lifecycle_status = "reconciliation_required"
            state.last_error = exc.message
            state.last_synced_at = _utcnow()
            _record_event(
                db,
                state=state,
                actor_user_id=None,
                event_type="automatic_reconciliation",
                request_type=None,
                request_snapshot={
                    "Automation": True,
                    "SearchedStatuses": searched,
                },
                success=False,
                message=exc.message,
            )
            db.commit()
            summary["failed"] += 1
            snapshot["last_check_status"] = "degraded"
            snapshot["provider_reads"] = local_reads
            snapshot["searched_statuses"] = searched
            snapshot["error"] = exc.message
            snapshot["recommended_action"] = "RECONCILIATION_REQUIRED"

        _finish_marker(db, marker, snapshot)

    return summary


def _has_disbursed_consolidation_successor(
    db: Session,
    *,
    company_id: UUID,
    loan_id: UUID,
) -> bool:
    return (
        db.query(ClientCompanyLoan.id)
        .filter(
            ClientCompanyLoan.company_id == company_id,
            ClientCompanyLoan.parent_loan_id == loan_id,
            ClientCompanyLoan.is_top_up.is_(True),
            ClientCompanyLoan.top_up_settlement_amount > 0,
            ClientCompanyLoan.disbursed_at.isnot(None),
            ClientCompanyLoan.status.in_((LoanStatus.ACTIVE, LoanStatus.DEFAULTED, LoanStatus.COMPLETED)),
        )
        .first()
        is not None
    )


def _settlement_effective_date(run_date: date) -> str:
    return datetime.combine(run_date, time.min, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


async def process_company_automatic_settlements(
    db: Session,
    *,
    company_id: UUID,
    run_date: date,
) -> dict[str, int]:
    summary = {
        "candidates": 0,
        "settled": 0,
        "paid_settlements": 0,
        "consolidation_settlements": 0,
        "failed": 0,
        "skipped": 0,
        "provider_writes": 0,
    }
    if not _company_automation_enabled(db, company_id):
        return summary

    rows = (
        db.query(CdasOfficialMandateState, CDASDeductionMandate, ClientCompanyLoan)
        .join(CDASDeductionMandate, CDASDeductionMandate.id == CdasOfficialMandateState.mandate_id)
        .join(ClientCompanyLoan, ClientCompanyLoan.id == CDASDeductionMandate.loan_id)
        .filter(
            CdasOfficialMandateState.company_id == company_id,
            CDASDeductionMandate.company_id == company_id,
            ClientCompanyLoan.company_id == company_id,
            CdasOfficialMandateState.requires_reconciliation.is_(False),
            CdasOfficialMandateState.deduction_id.isnot(None),
            CdasOfficialMandateState.lifecycle_status.in_(("approved", "active", "changed")),
            ClientCompanyLoan.balance <= 0,
        )
        .order_by(CdasOfficialMandateState.id.asc())
        .all()
    )
    summary["candidates"] = len(rows)
    if not rows:
        return summary

    client = get_company_cdas_client(db, company_id)
    for state, mandate, loan in rows:
        if _marker_exists(
            db,
            company_id=company_id,
            operation=AUTO_SETTLEMENT_OPERATION,
            state_id=state.id,
            run_date=run_date,
        ):
            summary["skipped"] += 1
            continue

        marker = _create_marker(
            db,
            company_id=company_id,
            operation=AUTO_SETTLEMENT_OPERATION,
            state=state,
            mandate=mandate,
            run_date=run_date,
        )
        snapshot = dict(marker.analysis_snapshot or {})
        snapshot["last_check_status"] = "success"

        try:
            consolidation = _has_disbursed_consolidation_successor(
                db,
                company_id=company_id,
                loan_id=loan.id,
            )
            reason = automatic_settlement_reason(
                outstanding_balance=loan.balance,
                has_consolidation_successor=consolidation,
            )
            if reason is None:
                summary["skipped"] += 1
                snapshot["recommended_action"] = "NO_AUTOMATIC_SETTLEMENT"
                _finish_marker(db, marker, snapshot)
                continue

            effective_date = _settlement_effective_date(run_date)
            result = await settle_linked_deduction(
                db,
                client=client,
                company_id=company_id,
                actor_user_id=None,  # system actor; never impersonate staff
                state_id=state.id,
                effective_date=effective_date,
                settlement_reason=reason,
            )
            db.refresh(state)
            db.refresh(mandate)
            _record_event(
                db,
                state=state,
                actor_user_id=None,
                event_type="automatic_settlement_decision",
                request_type=7,
                request_snapshot={
                    "Automation": True,
                    "AuthorizationBasis": AUTOMATION_AUTHORIZATION_BASIS,
                    "OutstandingBalanceAtDecision": float(_money(loan.balance)),
                    "SettlementReason": reason,
                    "EffectiveDate": effective_date,
                    "ConsolidationSuccessor": consolidation,
                },
                response_snapshot=result,
                provider_status_code=200,
                success=True,
                message=(
                    "Automatically settled consolidated CDAS deduction"
                    if reason == SETTLEMENT_REASON_CONSOLIDATION
                    else "Automatically settled fully paid CDAS deduction"
                ),
            )
            db.commit()

            summary["settled"] += 1
            summary["provider_writes"] += 1
            if reason == SETTLEMENT_REASON_CONSOLIDATION:
                summary["consolidation_settlements"] += 1
                reason_label = "CONSOLIDATION"
            else:
                summary["paid_settlements"] += 1
                reason_label = "PAID_BY_EMPLOYEE"

            snapshot["settled"] = 1
            snapshot["provider_writes"] = 1
            snapshot["settlement_reason"] = reason
            snapshot["settlement_reason_label"] = reason_label
            snapshot["effective_date"] = effective_date
            snapshot["outstanding_balance"] = float(_money(loan.balance))
            snapshot["recommended_action"] = "AUTO_SETTLED"
        except CdasError as exc:
            summary["failed"] += 1
            snapshot["last_check_status"] = "failed"
            snapshot["error"] = exc.message
            snapshot["provider_status_code"] = exc.status_code
            snapshot["recommended_action"] = (
                "RECONCILIATION_REQUIRED"
                if state.requires_reconciliation
                else "RETRY_ON_NEXT_MONTHLY_WINDOW_CHECK"
            )
        except CdasLifecycleError as exc:
            summary["failed"] += 1
            snapshot["last_check_status"] = "degraded"
            snapshot["error"] = exc.message
            snapshot["recommended_action"] = (
                "RECONCILIATION_REQUIRED"
                if state.requires_reconciliation
                else "MANUAL_REVIEW"
            )

        _finish_marker(db, marker, snapshot)

    return summary


async def run_monthly_cdas_lifecycle_automation(
    db: Session,
    *,
    now: datetime | None = None,
    enforce_window: bool = True,
) -> dict[str, Any]:
    local_value = now or local_now()
    if enforce_window and not is_monthly_automation_window(local_value):
        return {"status": "outside_window", "companies": []}

    company_rows = (
        db.query(OriginationIntegrationConfiguration.company_id)
        .filter(
            OriginationIntegrationConfiguration.provider == CDAS_PROVIDER,
            OriginationIntegrationConfiguration.is_enabled.is_(True),
        )
        .distinct()
        .all()
    )
    results: list[dict[str, Any]] = []
    for (company_id,) in company_rows:
        reconciliation = await process_company_status_reconciliation(
            db,
            company_id=company_id,
            run_date=local_value.date(),
        )
        settlements = await process_company_automatic_settlements(
            db,
            company_id=company_id,
            run_date=local_value.date(),
        )
        results.append(
            {
                "company_id": str(company_id),
                "reconciliation": reconciliation,
                "settlements": settlements,
            }
        )
    return {"status": "completed", "companies": results}
