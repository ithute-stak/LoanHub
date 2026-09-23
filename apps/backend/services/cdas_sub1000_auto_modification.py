from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.cdas_booking import CdasBookingOpportunity
from database.models.cdas_official import CdasOfficialMandateState
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus, RepaymentType
from database.models.lending_operations import CDASDeductionMandate
from database.models.origination import OriginationIntegrationConfiguration
from integrations.cdas import CdasClient, CdasError
from services.cdas_config_service import CDAS_PROVIDER, get_company_cdas_client
from services.cdas_deduction_lifecycle import (
    CdasLifecycleError,
    _apply_provider_response,
    _mark_uncertain_failure,
    _record_event,
    _utcnow,
)
from services.cdas_monthly_automation import (
    AUTOMATION_AUTHORIZATION_BASIS,
    AUTOMATION_SOURCE,
    get_monthly_automation_configuration,
    is_monthly_automation_window,
    local_now,
    next_effective_month,
)


AUTO_MODIFY_TARGET = Decimal("1000.00")
AUTO_MODIFY_OPERATION = "SUB_1000_AUTO_MODIFY"
_MONEY_QUANTUM = Decimal("0.01")
_ELIGIBLE_LOAN_STATUSES = {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}


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


def calculate_sub1000_modification(
    *,
    current_deduction: object,
    outstanding: object,
    affordability: object,
    target: object = AUTO_MODIFY_TARGET,
) -> tuple[Decimal, Decimal, int]:
    """Return target amount, incremental capacity required and revised term.

    Existing CDAS deductions already consume payroll capacity. Therefore an
    increase from M650 to M1,000 needs M350 of *additional* affordability, not
    another M1,000. The target is capped at the remaining LoanHub balance so the
    automation never schedules a monthly deduction above the debt still owing.
    """

    current = max(_money(current_deduction), Decimal("0.00"))
    balance = max(_money(outstanding), Decimal("0.00"))
    available = max(_money(affordability), Decimal("0.00"))
    ceiling = max(_money(target), Decimal("0.00"))

    if current <= 0:
        raise ValueError("An existing positive CDAS deduction is required")
    if balance <= 0:
        raise ValueError("A positive outstanding balance is required")
    if ceiling <= 0:
        raise ValueError("The automatic CDAS modification target must be positive")

    desired = min(ceiling, balance)
    if current >= desired:
        raise ValueError("This deduction does not require an automatic increase")

    increase = desired - current
    if increase > available:
        raise ValueError("Additional CDAS affordability is insufficient for the automatic increase")

    installments = int((balance / desired).to_integral_value(rounding=ROUND_CEILING))
    if installments <= 0:
        raise ValueError("A CDAS loan deduction requires at least one installment")
    if installments > 600:
        raise ValueError("Calculated CDAS term exceeds the 600-installment safety limit")
    return desired, increase, installments


def _provider_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _find_provider_deduction(payload: Any, deduction_id: int) -> dict[str, Any] | None:
    matches = [
        item
        for item in _provider_rows(payload)
        if _to_int(_value(item, "DeductionID", "DeductionId", "deduction_id")) == deduction_id
    ]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise CdasLifecycleError(409, "CDAS returned duplicate active/approved deductions for the same DeductionID")
    return None


def _marker_reference(state_id: UUID, run_date: date) -> str:
    return f"AUTO-MOD:{state_id}:{run_date.isoformat()}"


def _marker_exists(db: Session, *, company_id: UUID, state_id: UUID, run_date: date) -> bool:
    return (
        db.query(CdasBookingOpportunity.id)
        .filter(
            CdasBookingOpportunity.company_id == company_id,
            CdasBookingOpportunity.client_reference == _marker_reference(state_id, run_date),
        )
        .first()
        is not None
    )


def _create_marker(
    db: Session,
    *,
    company_id: UUID,
    state: CdasOfficialMandateState,
    mandate: CDASDeductionMandate,
    loan: ClientCompanyLoan,
    run_date: date,
) -> CdasBookingOpportunity:
    marker = CdasBookingOpportunity(
        company_id=company_id,
        client_reference=_marker_reference(state.id, run_date),
        status="monitoring",
        pipeline_stage="identified",
        opportunity_item_code=state.item_code,
        opportunity_reference_no=state.reference_no,
        opportunity_deduction_amount=mandate.monthly_deduction,
        analysis_snapshot={
            "source": AUTOMATION_SOURCE,
            "operation": AUTO_MODIFY_OPERATION,
            "authorization_basis": AUTOMATION_AUTHORIZATION_BASIS,
            "borrower_id": str(mandate.borrower_id),
            "loan_id": str(loan.id),
            "state_id": str(state.id),
            "deduction_id": state.deduction_id,
            "last_check_date": run_date.isoformat(),
            "last_check_status": "started",
            "modified": 0,
            "provider_writes": 0,
        },
    )
    db.add(marker)
    db.commit()
    db.refresh(marker)
    return marker


def _finish_marker(db: Session, marker: CdasBookingOpportunity, snapshot: dict[str, Any]) -> None:
    marker.analysis_snapshot = snapshot
    marker.status = "booked" if snapshot.get("modified", 0) else "monitoring"
    marker.pipeline_stage = "booked" if snapshot.get("modified", 0) else "identified"
    if snapshot.get("modified", 0):
        marker.booked_at = _utcnow()
    db.commit()


async def _modify_candidate(
    db: Session,
    *,
    client: CdasClient,
    company_id: UUID,
    state: CdasOfficialMandateState,
    mandate: CDASDeductionMandate,
    loan: ClientCompanyLoan,
    affordability: Decimal,
    run_date: date,
) -> dict[str, Any]:
    if state.lifecycle_status not in {"approved", "active"}:
        raise CdasLifecycleError(409, "Only an approved or active CDAS deduction can be auto-modified")
    if state.requires_reconciliation:
        raise CdasLifecycleError(409, "Reconcile this CDAS deduction before automatic modification")
    if not state.deduction_id:
        raise CdasLifecycleError(409, "CDAS DeductionID is required before automatic modification")
    if loan.status not in _ELIGIBLE_LOAN_STATUSES:
        raise CdasLifecycleError(409, "The linked LoanHub loan is not eligible for automatic CDAS collection")
    if loan.repayment_type != RepaymentType.MONTHLY:
        raise CdasLifecycleError(422, "Automatic CDAS modification requires a monthly loan")

    provider_payload = await client.active_and_approved_deductions(mandate.employee_number)
    provider_deduction = _find_provider_deduction(provider_payload, int(state.deduction_id))
    if provider_deduction is None:
        raise CdasLifecycleError(
            409,
            "The local CDAS deduction could not be confirmed in CDAS active/approved deductions; no automatic write was sent",
        )

    provider_amount = _money(_value(provider_deduction, "DeductionAmount", "deduction_amount"))
    if provider_amount <= 0:
        raise CdasLifecycleError(502, "CDAS returned an invalid active/approved deduction amount")

    desired, increase, installments = calculate_sub1000_modification(
        current_deduction=provider_amount,
        outstanding=loan.balance,
        affordability=affordability,
    )
    outstanding = max(_money(loan.balance), Decimal("0.00"))
    effective_date = f"{next_effective_month(run_date)}-01"
    original_lifecycle = state.lifecycle_status

    request_payload = {
        "EmployeeNo": mandate.employee_number,
        "ItemCode": state.item_code,
        "TotalInstallment": installments,
        "DeductionAmount": float(desired),
        "PrincipalAmount": float(outstanding),
        "DeductionID": state.deduction_id,
        "EffectiveDate": effective_date,
    }
    audit_payload = {
        **request_payload,
        "Automation": True,
        "AuthorizationBasis": AUTOMATION_AUTHORIZATION_BASIS,
        "PreviousDeductionAmount": float(provider_amount),
        "TargetDeductionAmount": float(desired),
        "AdditionalAffordabilityRequired": float(increase),
        "AffordabilityAtDecision": float(affordability),
        "OutstandingBalanceAtDecision": float(outstanding),
    }

    state.last_request_type = 10
    try:
        response = await client.modify_active_deduction(request_payload)
    except CdasError as exc:
        _mark_uncertain_failure(state, exc)
        _record_event(
            db,
            state=state,
            actor_user_id=None,
            event_type="automatic_modify_active",
            request_type=10,
            request_snapshot=audit_payload,
            provider_status_code=exc.status_code,
            success=False,
            message=exc.message,
        )
        db.commit()
        raise

    mandate.monthly_deduction = desired
    mandate.expected_installments = installments
    mandate.total_expected = outstanding
    state.principal_amount = outstanding
    complete = _apply_provider_response(
        state,
        mandate,
        response,
        requested_lifecycle=original_lifecycle,
    )
    _record_event(
        db,
        state=state,
        actor_user_id=None,
        event_type="automatic_modify_active",
        request_type=10,
        request_snapshot=audit_payload,
        response_snapshot=response,
        provider_status_code=200,
        success=complete,
        message=None if complete else state.last_error,
    )
    db.commit()
    db.refresh(state)
    db.refresh(mandate)
    if not complete:
        raise CdasLifecycleError(502, state.last_error or "CDAS returned an incomplete automatic modification response")

    return {
        "previous_amount": provider_amount,
        "new_amount": desired,
        "increase": increase,
        "installments": installments,
        "effective_date": effective_date,
        "provider_response": response,
    }


async def process_company_sub1000_modifications(
    db: Session,
    *,
    company_id: UUID,
    run_date: date,
) -> dict[str, int]:
    summary = {
        "candidates": 0,
        "checked": 0,
        "modified": 0,
        "no_capacity": 0,
        "skipped": 0,
        "failed": 0,
        "provider_writes": 0,
    }
    config_row = (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == company_id,
            OriginationIntegrationConfiguration.provider == CDAS_PROVIDER,
        )
        .one_or_none()
    )
    config = get_monthly_automation_configuration(config_row)
    if config_row is None or not config_row.is_enabled or not config["enabled"]:
        return summary

    rows = (
        db.query(CdasOfficialMandateState, CDASDeductionMandate, ClientCompanyLoan)
        .join(CDASDeductionMandate, CDASDeductionMandate.id == CdasOfficialMandateState.mandate_id)
        .join(ClientCompanyLoan, ClientCompanyLoan.id == CDASDeductionMandate.loan_id)
        .filter(
            CdasOfficialMandateState.company_id == company_id,
            CDASDeductionMandate.company_id == company_id,
            ClientCompanyLoan.company_id == company_id,
            CdasOfficialMandateState.lifecycle_status.in_(("approved", "active")),
            CdasOfficialMandateState.requires_reconciliation.is_(False),
            CdasOfficialMandateState.deduction_id.isnot(None),
            CDASDeductionMandate.monthly_deduction < AUTO_MODIFY_TARGET,
            ClientCompanyLoan.balance > 0,
            ClientCompanyLoan.status.in_(tuple(_ELIGIBLE_LOAN_STATUSES)),
            ClientCompanyLoan.repayment_type == RepaymentType.MONTHLY,
        )
        .order_by(CDASDeductionMandate.id.asc())
        .all()
    )
    summary["candidates"] = len(rows)
    if not rows:
        return summary

    client = get_company_cdas_client(db, company_id)
    for state, mandate, loan in rows:
        if state.registered_at is not None and state.registered_at.date() == run_date:
            summary["skipped"] += 1
            continue
        if _marker_exists(db, company_id=company_id, state_id=state.id, run_date=run_date):
            summary["skipped"] += 1
            continue

        marker = _create_marker(
            db,
            company_id=company_id,
            state=state,
            mandate=mandate,
            loan=loan,
            run_date=run_date,
        )
        snapshot = dict(marker.analysis_snapshot or {})
        snapshot["last_check_status"] = "success"
        try:
            affordability = max(_money(await client.affordability(mandate.employee_number)), Decimal("0.00"))
            summary["checked"] += 1
            snapshot["available_affordability"] = float(affordability)

            balance = max(_money(loan.balance), Decimal("0.00"))
            current = max(_money(mandate.monthly_deduction), Decimal("0.00"))
            desired = min(AUTO_MODIFY_TARGET, balance)
            increase = max(desired - current, Decimal("0.00"))
            snapshot["current_deduction"] = float(current)
            snapshot["target_deduction"] = float(desired)
            snapshot["additional_affordability_required"] = float(increase)

            if desired <= current:
                summary["skipped"] += 1
                snapshot["recommended_action"] = "NO_INCREASE_REQUIRED"
                _finish_marker(db, marker, snapshot)
                continue
            if affordability < increase:
                summary["no_capacity"] += 1
                snapshot["recommended_action"] = "MONITOR_UNTIL_INCREMENTAL_CAPACITY_AVAILABLE"
                _finish_marker(db, marker, snapshot)
                continue

            result = await _modify_candidate(
                db,
                client=client,
                company_id=company_id,
                state=state,
                mandate=mandate,
                loan=loan,
                affordability=affordability,
                run_date=run_date,
            )
            summary["modified"] += 1
            summary["provider_writes"] += 1
            snapshot["modified"] = 1
            snapshot["provider_writes"] = 1
            snapshot["previous_deduction"] = float(result["previous_amount"])
            snapshot["new_deduction"] = float(result["new_amount"])
            snapshot["additional_affordability_used"] = float(result["increase"])
            snapshot["new_installments"] = int(result["installments"])
            snapshot["effective_date"] = result["effective_date"]
            snapshot["recommended_action"] = "AUTO_MODIFIED_TO_TARGET"
        except ValueError as exc:
            summary["no_capacity"] += 1
            snapshot["last_check_status"] = "success"
            snapshot["recommended_action"] = "NO_MODIFICATION"
            snapshot["reason"] = str(exc)
        except (CdasLifecycleError, CdasError) as exc:
            summary["failed"] += 1
            snapshot["last_check_status"] = "degraded"
            snapshot["error"] = getattr(exc, "message", None) or str(exc)
        except Exception as exc:
            summary["failed"] += 1
            snapshot["last_check_status"] = "failed"
            snapshot["error"] = str(exc)
        _finish_marker(db, marker, snapshot)

    return summary


async def run_sub1000_auto_modifications(
    db: Session,
    *,
    now: datetime | None = None,
    enforce_window: bool = True,
) -> dict[str, Any]:
    current = now or local_now()
    local_current = (
        current.astimezone(ZoneInfo(settings.APP_TIMEZONE))
        if current.tzinfo
        else current.replace(tzinfo=ZoneInfo(settings.APP_TIMEZONE))
    )
    if enforce_window and not is_monthly_automation_window(local_current):
        return {
            "ran": False,
            "reason": "outside_monthly_window",
            "local_time": local_current.isoformat(),
        }

    rows = (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.provider == CDAS_PROVIDER,
            OriginationIntegrationConfiguration.is_enabled.is_(True),
        )
        .all()
    )
    companies: dict[str, Any] = {}
    for row in rows:
        try:
            companies[str(row.company_id)] = await process_company_sub1000_modifications(
                db,
                company_id=row.company_id,
                run_date=local_current.date(),
            )
        except Exception as exc:
            db.rollback()
            companies[str(row.company_id)] = {"failed": 1, "error": str(exc)}

    return {
        "ran": True,
        "local_date": local_current.date().isoformat(),
        "timezone": settings.APP_TIMEZONE,
        "target_deduction": float(AUTO_MODIFY_TARGET),
        "companies": companies,
    }
