from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_CEILING
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.cdas_booking import CdasBookingOpportunity
from database.models.cdas_official import CdasOfficialMandateState
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus, RepaymentType
from database.models.lending_operations import CDASDeductionMandate, CDASPayrollProfile
from database.models.origination import OriginationIntegrationConfiguration
from database.models.professional_lending import DirectLoanApplication
from integrations.cdas import CdasClient, CdasError
from services.cdas_config_service import CDAS_PROVIDER, get_company_cdas_client
from services.cdas_crash_safe_lifecycle import perform_linked_action
from services.cdas_deduction_lifecycle import (
    CdasLifecycleError,
    _apply_provider_response,
    _configuration_environment,
    _effective_month_start,
    _mark_uncertain_failure,
    _record_event,
    _utcnow,
    get_official_mandate,
    get_official_mandate_for_loan,
    serialize_official_mandate,
)
from services.cdas_registration_workflow import _validate_employee_identity


AUTOMATION_KEY = "monthly_auto_deductions"
AUTOMATION_SOURCE = "CDAS_MONTHLY_AUTO_DEDUCTION"
AUTOMATION_AUTHORIZATION_BASIS = "STORED_CDAS_EMPLOYEE_NUMBER_AGREEMENT"
WINDOW_START_DAY = 14
WINDOW_END_DAY = 20
WINDOW_HOUR = 6
_ELIGIBLE_LOAN_STATUSES = {LoanStatus.ACTIVE, LoanStatus.DEFAULTED}
_MONEY_QUANTUM = Decimal("0.01")


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0)).quantize(_MONEY_QUANTUM)
    except Exception:
        return Decimal("0.00")


def local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.APP_TIMEZONE))


def is_monthly_automation_window(value: datetime) -> bool:
    """Return True only during 06:00-06:59 on the 14th through 20th."""
    local_value = value.astimezone(ZoneInfo(settings.APP_TIMEZONE)) if value.tzinfo else value.replace(tzinfo=ZoneInfo(settings.APP_TIMEZONE))
    return WINDOW_START_DAY <= local_value.day <= WINDOW_END_DAY and local_value.hour == WINDOW_HOUR


def next_effective_month(value: date) -> str:
    year = value.year + (1 if value.month == 12 else 0)
    month = 1 if value.month == 12 else value.month + 1
    return f"{year:04d}-{month:02d}"


def calculate_automatic_terms(*, outstanding: object, affordability: object) -> tuple[Decimal, int]:
    balance = max(_money(outstanding), Decimal("0.00"))
    available = max(_money(affordability), Decimal("0.00"))
    deduction = min(balance, available)
    if balance <= 0 or deduction <= 0:
        raise ValueError("A positive outstanding balance and CDAS affordability are required")
    installments = int((balance / deduction).to_integral_value(rounding=ROUND_CEILING))
    if installments > 600:
        raise ValueError("Calculated CDAS term exceeds the 600-installment safety limit")
    return deduction, installments


def _configuration_dict(row: OriginationIntegrationConfiguration) -> dict[str, Any]:
    return dict(row.configuration) if isinstance(row.configuration, dict) else {}


def get_monthly_automation_configuration(row: OriginationIntegrationConfiguration | None) -> dict[str, Any]:
    if row is None:
        return {
            "enabled": False,
            "item_code": "",
            "loan_policy": 0,
            "configured": False,
        }
    root = _configuration_dict(row)
    automation = root.get(AUTOMATION_KEY)
    automation = dict(automation) if isinstance(automation, dict) else {}
    item_code = str(automation.get("item_code") or "").strip()
    try:
        loan_policy = max(int(automation.get("loan_policy", 0)), 0)
    except (TypeError, ValueError):
        loan_policy = 0
    enabled = bool(automation.get("enabled", True))
    return {
        "enabled": enabled,
        "item_code": item_code,
        "loan_policy": loan_policy,
        "configured": bool(enabled and item_code and row.is_enabled),
    }


def update_monthly_automation_configuration(
    db: Session,
    *,
    row: OriginationIntegrationConfiguration,
    enabled: bool,
    item_code: str,
    loan_policy: int,
    configured_by_user_id: UUID,
) -> dict[str, Any]:
    cleaned_item_code = item_code.strip()
    if enabled and not cleaned_item_code:
        raise ValueError("CDAS automation item code is required when automatic deductions are enabled")
    if len(cleaned_item_code) > 100:
        raise ValueError("CDAS automation item code must not exceed 100 characters")
    if loan_policy < 0:
        raise ValueError("CDAS automation loan policy cannot be negative")
    root = _configuration_dict(row)
    root[AUTOMATION_KEY] = {
        "enabled": bool(enabled),
        "item_code": cleaned_item_code,
        "loan_policy": int(loan_policy),
        "window_start_day": WINDOW_START_DAY,
        "window_end_day": WINDOW_END_DAY,
        "hour": WINDOW_HOUR,
        "timezone": settings.APP_TIMEZONE,
        "authorization_basis": AUTOMATION_AUTHORIZATION_BASIS,
    }
    row.configuration = root
    row.configured_by_user_id = configured_by_user_id
    db.commit()
    db.refresh(row)
    return get_monthly_automation_configuration(row)


def _resolve_item_code(db: Session, *, company_id: UUID, configured_item_code: str) -> str:
    if configured_item_code.strip():
        return configured_item_code.strip()
    latest = (
        db.query(CdasOfficialMandateState)
        .filter(CdasOfficialMandateState.company_id == company_id)
        .order_by(CdasOfficialMandateState.last_synced_at.desc().nullslast())
        .first()
    )
    return str(latest.item_code or "").strip() if latest else ""


def _daily_marker(db: Session, *, company_id: UUID, borrower_id: UUID, run_date: date) -> CdasBookingOpportunity:
    reference = f"AUTO:{borrower_id}:{run_date.isoformat()}"
    existing = (
        db.query(CdasBookingOpportunity)
        .filter(
            CdasBookingOpportunity.company_id == company_id,
            CdasBookingOpportunity.client_reference == reference,
        )
        .order_by(CdasBookingOpportunity.id.desc())
        .first()
    )
    if existing is not None:
        return existing
    marker = CdasBookingOpportunity(
        company_id=company_id,
        client_reference=reference,
        status="monitoring",
        pipeline_stage="identified",
        analysis_snapshot={
            "source": AUTOMATION_SOURCE,
            "borrower_id": str(borrower_id),
            "last_check_date": run_date.isoformat(),
            "last_check_status": "started",
        },
    )
    db.add(marker)
    db.commit()
    db.refresh(marker)
    return marker


def _finish_marker(db: Session, marker: CdasBookingOpportunity, snapshot: dict[str, Any]) -> None:
    marker.analysis_snapshot = snapshot
    marker.status = "booked" if snapshot.get("activated", 0) else "monitoring"
    marker.pipeline_stage = "booked" if snapshot.get("activated", 0) else "identified"
    if snapshot.get("activated", 0):
        marker.booked_at = _utcnow()
    db.commit()


async def _register_automatic_deduction(
    db: Session,
    *,
    client: CdasClient,
    company_id: UUID,
    loan: ClientCompanyLoan,
    profile: CDASPayrollProfile,
    item_code: str,
    loan_policy: int,
    affordability: Decimal,
    effective_month: str,
) -> dict[str, Any]:
    if loan.status not in _ELIGIBLE_LOAN_STATUSES:
        raise CdasLifecycleError(409, "Only an active or defaulted loan can enter automatic CDAS collection")
    if loan.repayment_type != RepaymentType.MONTHLY:
        raise CdasLifecycleError(422, "Automatic CDAS collection requires a monthly loan")
    existing = get_official_mandate_for_loan(db, company_id=company_id, loan_id=loan.id)
    if existing is not None:
        state, mandate = existing
        return serialize_official_mandate(state, mandate)

    deduction, installments = calculate_automatic_terms(outstanding=loan.balance, affordability=affordability)
    employee_no = str(profile.employee_number or "").strip()
    if not employee_no:
        raise CdasLifecycleError(422, "Stored CDAS employee number is required for automatic collection")

    employee_details = await client.employee_details(employee_no)
    _validate_employee_identity(loan, employee_no, employee_details)

    application: DirectLoanApplication | None = None
    if loan.direct_application_id:
        application = (
            db.query(DirectLoanApplication)
            .filter(
                DirectLoanApplication.id == loan.direct_application_id,
                DirectLoanApplication.company_id == company_id,
                DirectLoanApplication.borrower_id == loan.borrower_id,
            )
            .one_or_none()
        )

    environment = _configuration_environment(db, company_id)
    start_date = _effective_month_start(effective_month)
    reference_no = str(loan.loan_reference).strip()
    balance = _money(loan.balance)

    try:
        profile.verified = True
        profile.verified_at = _utcnow()
        profile.verified_by_user_id = None
        profile.verification_reference = "CDAS_API_V1_5_AUTO"
        profile.verification_notes = (
            "Identity matched against CDAS during automatic collection. Stored CDAS employee number is the company-configured agreement basis."
        )

        duplicate_reference = (
            db.query(CdasOfficialMandateState)
            .filter(
                CdasOfficialMandateState.company_id == company_id,
                CdasOfficialMandateState.environment == environment,
                CdasOfficialMandateState.reference_no == reference_no,
            )
            .first()
        )
        if duplicate_reference is not None:
            raise CdasLifecycleError(409, "This loan reference is already linked to a CDAS mandate")

        mandate = CDASDeductionMandate(
            company_id=company_id,
            branch_id=loan.branch_id or profile.branch_id,
            borrower_id=loan.borrower_id,
            loan_id=loan.id,
            payroll_profile_id=profile.id,
            mandate_number=f"CDAS-{loan.loan_reference}"[:80],
            employee_number=employee_no,
            monthly_deduction=deduction,
            start_date=start_date,
            expected_installments=installments,
            total_expected=balance,
            status="registration_submission_pending",
            borrower_consent=True,
            external_reference=reference_no,
            submitted_at=_utcnow(),
            created_by_user_id=None,
        )
        db.add(mandate)
        db.flush()
        state = CdasOfficialMandateState(
            company_id=company_id,
            mandate_id=mandate.id,
            application_id=application.id if application else loan.direct_application_id,
            environment=environment,
            item_code=item_code,
            reference_no=reference_no,
            loan_policy=loan_policy,
            principal_amount=balance,
            effective_month=effective_month,
            lifecycle_status="registration_submission_pending",
            last_request_type=1,
            requires_reconciliation=True,
            last_error="Automatic registration submitted to CDAS; provider result has not yet been confirmed",
        )
        db.add(state)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CdasLifecycleError(409, "Automatic CDAS registration is already linked or in progress") from exc

    db.refresh(state)
    db.refresh(mandate)
    provider_payload = {
        "RequestType": 1,
        "DeductionID": 0,
        "EmployeeNo": employee_no,
        "LoanPolicy": loan_policy,
        "ItemCode": item_code,
        "DeductionAmount": float(deduction),
        "TotalInstallment": installments,
        "PrincipalAmount": float(balance),
        "EffectiveMonth": effective_month,
        "ReferenceNo": reference_no,
    }
    audit_payload = {
        **provider_payload,
        "Automation": True,
        "AuthorizationBasis": AUTOMATION_AUTHORIZATION_BASIS,
        "AffordabilityAtDecision": float(_money(affordability)),
        "OutstandingBalanceAtDecision": float(balance),
    }
    try:
        response = await client.add_update_deduction(provider_payload)
    except CdasError as exc:
        _mark_uncertain_failure(state, exc)
        if not state.requires_reconciliation:
            state.lifecycle_status = "registration_failed"
            mandate.status = "registration_failed"
        _record_event(
            db,
            state=state,
            actor_user_id=None,
            event_type="automatic_registration",
            request_type=1,
            request_snapshot=audit_payload,
            provider_status_code=exc.status_code,
            success=False,
            message=exc.message,
        )
        db.commit()
        raise

    complete = _apply_provider_response(
        state,
        mandate,
        response,
        requested_lifecycle="registered",
        require_status=True,
        require_deduction_id=True,
    )
    _record_event(
        db,
        state=state,
        actor_user_id=None,
        event_type="automatic_registration",
        request_type=1,
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
        raise CdasLifecycleError(502, state.last_error or "CDAS returned an incomplete automatic registration response")
    return serialize_official_mandate(state, mandate)


async def _advance_to_active(
    db: Session,
    *,
    client: CdasClient,
    company_id: UUID,
    state_id: UUID,
) -> dict[str, Any]:
    expected = ((3, "reviewed"), (4, "approved"), (5, "active"))
    result: dict[str, Any] = {}
    for request_type, expected_status in expected:
        state, mandate = get_official_mandate(db, company_id=company_id, state_id=state_id)
        if state.requires_reconciliation:
            raise CdasLifecycleError(409, "Automatic CDAS processing stopped because reconciliation is required")
        if state.lifecycle_status == "active":
            return serialize_official_mandate(state, mandate)
        result = await perform_linked_action(
            db,
            client=client,
            company_id=company_id,
            actor_user_id=None,  # system actor; never impersonate a staff member
            state_id=state_id,
            request_type=request_type,
        )
        if str(result.get("lifecycle_status") or "") not in {expected_status, "active"}:
            raise CdasLifecycleError(
                502,
                f"CDAS automatic request type {request_type} did not reach the expected {expected_status} state",
            )
    return result


async def process_company_monthly_automation(
    db: Session,
    *,
    company_id: UUID,
    run_date: date,
) -> dict[str, int]:
    config_row = (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == company_id,
            OriginationIntegrationConfiguration.provider == CDAS_PROVIDER,
        )
        .one_or_none()
    )
    config = get_monthly_automation_configuration(config_row)
    summary = {
        "borrowers": 0,
        "checked": 0,
        "positive_affordability": 0,
        "registered": 0,
        "reviewed": 0,
        "approved": 0,
        "activated": 0,
        "no_capacity": 0,
        "skipped": 0,
        "failed": 0,
        "provider_writes": 0,
    }
    if config_row is None or not config_row.is_enabled or not config["enabled"]:
        return summary

    item_code = _resolve_item_code(db, company_id=company_id, configured_item_code=str(config["item_code"]))
    if not item_code:
        summary["failed"] += 1
        return summary

    profiles = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == company_id,
            CDASPayrollProfile.employee_number.isnot(None),
            CDASPayrollProfile.employee_number != "",
        )
        .all()
    )
    summary["borrowers"] = len(profiles)
    client = get_company_cdas_client(db, company_id)
    effective_month = next_effective_month(run_date)

    for profile in profiles:
        marker_reference = f"AUTO:{profile.borrower_id}:{run_date.isoformat()}"
        already_checked = (
            db.query(CdasBookingOpportunity.id)
            .filter(
                CdasBookingOpportunity.company_id == company_id,
                CdasBookingOpportunity.client_reference == marker_reference,
            )
            .first()
        )
        if already_checked is not None:
            summary["skipped"] += 1
            continue

        marker = _daily_marker(db, company_id=company_id, borrower_id=profile.borrower_id, run_date=run_date)
        snapshot: dict[str, Any] = {
            "source": AUTOMATION_SOURCE,
            "authorization_basis": AUTOMATION_AUTHORIZATION_BASIS,
            "borrower_id": str(profile.borrower_id),
            "employee_no": str(profile.employee_number),
            "last_check_date": run_date.isoformat(),
            "last_check_status": "success",
            "activated": 0,
            "provider_writes": 0,
            "loans": [],
        }
        try:
            affordability = max(_money(await client.affordability(str(profile.employee_number).strip())), Decimal("0.00"))
            summary["checked"] += 1
            snapshot["available_affordability"] = float(affordability)
            if affordability <= 0:
                summary["no_capacity"] += 1
                snapshot["recommended_action"] = "MONITOR_NO_CAPACITY"
                _finish_marker(db, marker, snapshot)
                continue

            summary["positive_affordability"] += 1
            remaining = affordability
            loans = (
                db.query(ClientCompanyLoan)
                .filter(
                    ClientCompanyLoan.company_id == company_id,
                    ClientCompanyLoan.borrower_id == profile.borrower_id,
                    ClientCompanyLoan.status.in_(tuple(_ELIGIBLE_LOAN_STATUSES)),
                    ClientCompanyLoan.balance > 0,
                )
                .order_by(ClientCompanyLoan.is_overdue.desc(), ClientCompanyLoan.id.asc())
                .all()
            )
            for loan in loans:
                existing = get_official_mandate_for_loan(db, company_id=company_id, loan_id=loan.id)
                if existing is not None:
                    summary["skipped"] += 1
                    snapshot["loans"].append({"loan_id": str(loan.id), "status": "existing_mandate"})
                    continue
                if remaining <= 0:
                    break
                allocation, installments = calculate_automatic_terms(outstanding=loan.balance, affordability=remaining)
                try:
                    registered = await _register_automatic_deduction(
                        db,
                        client=client,
                        company_id=company_id,
                        loan=loan,
                        profile=profile,
                        item_code=item_code,
                        loan_policy=int(config["loan_policy"]),
                        affordability=allocation,
                        effective_month=effective_month,
                    )
                    summary["registered"] += 1
                    summary["provider_writes"] += 1
                    snapshot["provider_writes"] += 1
                    state_id = UUID(str(registered["id"]))
                    active = await _advance_to_active(
                        db,
                        client=client,
                        company_id=company_id,
                        state_id=state_id,
                    )
                    summary["reviewed"] += 1
                    summary["approved"] += 1
                    summary["activated"] += 1
                    summary["provider_writes"] += 3
                    snapshot["provider_writes"] += 3
                    snapshot["activated"] += 1
                    snapshot["loans"].append(
                        {
                            "loan_id": str(loan.id),
                            "loan_reference": loan.loan_reference,
                            "status": str(active.get("lifecycle_status") or "active"),
                            "deduction_amount": float(allocation),
                            "installments": installments,
                            "outstanding": float(_money(loan.balance)),
                        }
                    )
                    remaining = max(remaining - allocation, Decimal("0.00"))
                except (CdasLifecycleError, CdasError, ValueError) as exc:
                    summary["failed"] += 1
                    snapshot["last_check_status"] = "degraded"
                    snapshot["loans"].append(
                        {
                            "loan_id": str(loan.id),
                            "loan_reference": loan.loan_reference,
                            "status": "failed",
                            "error": getattr(exc, "message", None) or str(exc),
                        }
                    )
                    # Never continue the same borrower's write chain after an
                    # ambiguous or failed provider mutation.
                    break
            snapshot["recommended_action"] = "AUTOMATIC_PROCESSING_COMPLETED"
            snapshot["remaining_affordability"] = float(remaining)
        except CdasError as exc:
            summary["failed"] += 1
            snapshot["last_check_status"] = "failed"
            snapshot["error"] = exc.message
        except Exception as exc:
            summary["failed"] += 1
            snapshot["last_check_status"] = "failed"
            snapshot["error"] = str(exc)
        _finish_marker(db, marker, snapshot)

    return summary


async def run_monthly_cdas_automation(
    db: Session,
    *,
    now: datetime | None = None,
    enforce_window: bool = True,
) -> dict[str, Any]:
    current = now or local_now()
    local_current = current.astimezone(ZoneInfo(settings.APP_TIMEZONE)) if current.tzinfo else current.replace(tzinfo=ZoneInfo(settings.APP_TIMEZONE))
    if enforce_window and not is_monthly_automation_window(local_current):
        return {
            "ran": False,
            "reason": "outside_monthly_window",
            "local_time": local_current.isoformat(),
            "window": {"start_day": WINDOW_START_DAY, "end_day": WINDOW_END_DAY, "hour": WINDOW_HOUR},
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
            companies[str(row.company_id)] = await process_company_monthly_automation(
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
        "window": {"start_day": WINDOW_START_DAY, "end_day": WINDOW_END_DAY, "hour": WINDOW_HOUR},
        "companies": companies,
    }
