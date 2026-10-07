from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.cdas_official import CdasOfficialMandateEvent, CdasOfficialMandateState
from database.models.client_loan_company import ClientCompanyLoan
from database.models.lending_operations import CDASDeductionMandate, CDASPayrollProfile
from integrations.cdas import CdasError
from integrations.cdas_contracts import CdasModifyActivePayload, CdasSettlementPayload
from services.cdas_autopilot import affordability_window_open, decide_cdas_autopilot
from services.cdas_config_service import get_company_cdas_client, get_configuration, selected_environment
from services.cdas_operation_ledger import (
    CdasDuplicateOperationError,
    CdasTrackedProviderError,
    execute_provider_operation,
    reconcile_provider_operation,
)
from services.platform_cdas_service import (
    assert_live_credit_available,
    record_successful_operation,
    require_approved_subscription,
)


ACTIVE_MANDATE_STATUSES = {"active", "approved", "changed", "registered"}
ACTIVE_PROVIDER_STATUSES = {4, 5, 10}


def _now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _money(value) -> Decimal:
    return Decimal(str(value or 0)).quantize(Decimal("0.01"))


def _actor_from_plan(plan: dict, mandate: CDASDeductionMandate) -> UUID | None:
    raw = plan.get("selected_by_user_id")
    if raw:
        try:
            return UUID(str(raw))
        except (TypeError, ValueError):
            pass
    return mandate.created_by_user_id


def _eligible_link(
    db: Session,
    loan: ClientCompanyLoan,
) -> tuple[CDASDeductionMandate, CdasOfficialMandateState, CDASPayrollProfile] | None:
    mandate = (
        db.query(CDASDeductionMandate)
        .filter(
            CDASDeductionMandate.company_id == loan.company_id,
            CDASDeductionMandate.loan_id == loan.id,
            CDASDeductionMandate.status.in_(ACTIVE_MANDATE_STATUSES),
        )
        .first()
    )
    if not mandate or not mandate.borrower_consent:
        return None

    state = (
        db.query(CdasOfficialMandateState)
        .filter(
            CdasOfficialMandateState.company_id == loan.company_id,
            CdasOfficialMandateState.mandate_id == mandate.id,
        )
        .first()
    )
    if (
        not state
        or not state.deduction_id
        or state.requires_reconciliation
        or (state.cdas_status is not None and int(state.cdas_status) not in ACTIVE_PROVIDER_STATUSES)
    ):
        return None

    profile = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.id == mandate.payroll_profile_id,
            CDASPayrollProfile.company_id == loan.company_id,
            CDASPayrollProfile.verified.is_(True),
            CDASPayrollProfile.employee_number.isnot(None),
            CDASPayrollProfile.employee_number != "",
        )
        .first()
    )
    if not profile:
        return None
    return mandate, state, profile


async def _tracked_modify(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    mandate: CDASDeductionMandate,
    state: CdasOfficialMandateState,
    total_installment: int,
    deduction_amount: Decimal,
    principal_amount: Decimal,
    actor_user_id: UUID | None,
    reason: str,
) -> bool:
    configuration = get_configuration(db, loan.company_id)
    environment = selected_environment(configuration)
    subscription = require_approved_subscription(db, company_id=loan.company_id)
    assert_live_credit_available(
        db,
        subscription=subscription,
        environment=environment,
        operation_type="modification",
    )

    payload = CdasModifyActivePayload(
        employee_no=mandate.employee_number,
        item_code=state.item_code,
        total_installment=max(1, int(total_installment)),
        deduction_amount=_money(deduction_amount),
        principal_amount=max(_money(principal_amount), Decimal("0.01")),
        deduction_id=int(state.deduction_id),
        effective_date=date.today().isoformat(),
    )
    provider_request = payload.provider_payload()
    ledger_request = payload.ledger_payload()
    client = get_company_cdas_client(db, loan.company_id)

    try:
        result, operation = await execute_provider_operation(
            db,
            company_id=loan.company_id,
            branch_id=loan.branch_id,
            actor_user_id=actor_user_id,
            environment=environment,
            operation_type="deduction.modify_active.autopilot",
            request_snapshot=ledger_request,
            provider_call=lambda: client.modify_active_deduction(provider_request),
        )
    except (CdasDuplicateOperationError, CdasTrackedProviderError):
        return False

    record_successful_operation(
        db,
        company_id=loan.company_id,
        environment=environment,
        operation_type="modification",
        actor_user_id=actor_user_id,
        billing_key=f"cdas-mutation:{operation.id}",
        source_reference=str(operation.id),
        metadata={"provider_operation_type": "deduction.modify_active.autopilot", "reason": reason},
    )

    reconciled = False
    try:
        reconciled, operation = await reconcile_provider_operation(db, operation=operation, client=client)
    except CdasError:
        db.refresh(operation)

    now = _now_naive()
    state.last_request_type = 10
    state.last_provider_response = dict(result or {})
    state.last_error = None
    state.last_synced_at = now
    state.requires_reconciliation = not reconciled
    state.lifecycle_status = "changed" if reconciled else "change_pending"
    if reconciled:
        state.cdas_status = 10
        mandate.monthly_deduction = _money(deduction_amount)
        mandate.expected_installments = max(1, int(total_installment))
        mandate.total_expected = _money(principal_amount)
        mandate.status = "changed"

    db.add(
        CdasOfficialMandateEvent(
            company_id=loan.company_id,
            state_id=state.id,
            actor_user_id=actor_user_id,
            event_type="autopilot_modify_active",
            request_type=10,
            request_snapshot=ledger_request,
            response_snapshot=dict(result or {}),
            provider_status_code=operation.provider_status_code,
            success=True,
            message=(
                f"CDAS Autopilot confirmed {reason}"
                if reconciled
                else f"CDAS Autopilot submitted {reason}; reconciliation remains required"
            ),
            occurred_at=now,
        )
    )
    db.commit()
    return reconciled


async def _tracked_settle(
    db: Session,
    *,
    loan: ClientCompanyLoan,
    mandate: CDASDeductionMandate,
    state: CdasOfficialMandateState,
    actor_user_id: UUID | None,
) -> bool:
    configuration = get_configuration(db, loan.company_id)
    environment = selected_environment(configuration)
    subscription = require_approved_subscription(db, company_id=loan.company_id)
    assert_live_credit_available(
        db,
        subscription=subscription,
        environment=environment,
        operation_type="settlement",
    )

    payload = CdasSettlementPayload(
        item_code=state.item_code,
        deduction_id=int(state.deduction_id),
        effective_date=date.today().isoformat(),
        employee_no=mandate.employee_number,
        settlement_reason=2,
    )
    provider_request = payload.provider_payload()
    ledger_request = payload.ledger_payload()
    client = get_company_cdas_client(db, loan.company_id)

    try:
        result, operation = await execute_provider_operation(
            db,
            company_id=loan.company_id,
            branch_id=loan.branch_id,
            actor_user_id=actor_user_id,
            environment=environment,
            operation_type="deduction.settle.autopilot",
            request_snapshot=ledger_request,
            provider_call=lambda: client.settle_deduction(provider_request),
        )
    except (CdasDuplicateOperationError, CdasTrackedProviderError):
        return False

    record_successful_operation(
        db,
        company_id=loan.company_id,
        environment=environment,
        operation_type="settlement",
        actor_user_id=actor_user_id,
        billing_key=f"cdas-mutation:{operation.id}",
        source_reference=str(operation.id),
        metadata={"provider_operation_type": "deduction.settle.autopilot", "reason": "loan_balance_settled"},
    )

    reconciled = False
    try:
        reconciled, operation = await reconcile_provider_operation(db, operation=operation, client=client)
    except CdasError:
        db.refresh(operation)

    now = _now_naive()
    state.last_request_type = 7
    state.last_provider_response = dict(result or {})
    state.last_error = None
    state.last_synced_at = now
    state.requires_reconciliation = not reconciled
    state.lifecycle_status = "settled" if reconciled else "settlement_pending"
    if reconciled:
        state.cdas_status = 7
        state.settled_at = now
        mandate.status = "settled"
        mandate.completed_at = now

    db.add(
        CdasOfficialMandateEvent(
            company_id=loan.company_id,
            state_id=state.id,
            actor_user_id=actor_user_id,
            event_type="autopilot_settlement",
            request_type=7,
            request_snapshot=ledger_request,
            response_snapshot=dict(result or {}),
            provider_status_code=operation.provider_status_code,
            success=True,
            message=(
                "CDAS Autopilot settlement confirmed"
                if reconciled
                else "CDAS Autopilot settlement submitted; reconciliation remains required"
            ),
            occurred_at=now,
        )
    )
    db.commit()
    return reconciled


async def process_pending_payment_reoptimizations(db: Session, *, limit: int = 100) -> dict[str, int]:
    processed = settled = shortened = skipped = 0
    loans = (
        db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.cdas_collection_enabled.is_(True))
        .order_by(ClientCompanyLoan.created_at.asc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    for loan in loans:
        plan = dict(loan.cdas_collection_plan or {})
        pending = plan.get("autopilot_pending")
        if not isinstance(pending, dict):
            continue

        link = _eligible_link(db, loan)
        if not link:
            skipped += 1
            continue
        mandate, state, _profile = link
        actor_user_id = _actor_from_plan(plan, mandate)
        decision = decide_cdas_autopilot(
            outstanding_balance=_money(loan.balance),
            current_deduction=_money(mandate.monthly_deduction),
            evaluation_date=date.today(),
            dynamic_top_up_consent=bool(plan.get("dynamic_top_up_consent")),
            payment_triggered=True,
        )
        processed += 1

        confirmed = False
        if decision.action == "settle":
            confirmed = await _tracked_settle(
                db,
                loan=loan,
                mandate=mandate,
                state=state,
                actor_user_id=actor_user_id,
            )
            settled += int(confirmed)
        elif decision.action == "shorten_term":
            confirmed = await _tracked_modify(
                db,
                loan=loan,
                mandate=mandate,
                state=state,
                total_installment=decision.proposed_remaining_installments,
                deduction_amount=decision.proposed_deduction,
                principal_amount=decision.effective_balance,
                actor_user_id=actor_user_id,
                reason="cash-payment term reduction",
            )
            shortened += int(confirmed)

        if confirmed:
            plan.pop("autopilot_pending", None)
            plan["autopilot_last_result"] = {
                "action": decision.action,
                "confirmed_at": datetime.now(timezone.utc).isoformat(),
                "decision": decision.as_dict(),
            }
            loan.cdas_collection_plan = plan
            db.add(loan)
            db.commit()

    return {
        "processed": processed,
        "settled": settled,
        "shortened": shortened,
        "skipped": skipped,
    }


async def scan_affordability_opportunities(db: Session, *, limit: int = 250) -> dict[str, int]:
    today = date.today()
    if not affordability_window_open(today):
        return {"checked": 0, "provider_reads": 0, "reused_reads": 0, "opportunities": 0, "topups": 0, "skipped": 0}

    checked = provider_reads = reused_reads = opportunities = topups = skipped = 0
    affordability_cache: dict[tuple[str, str, str], Decimal] = {}
    loans = (
        db.query(ClientCompanyLoan)
        .filter(ClientCompanyLoan.cdas_collection_enabled.is_(True))
        .order_by(ClientCompanyLoan.created_at.asc())
        .limit(max(1, min(limit, 1000)))
        .all()
    )
    for loan in loans:
        link = _eligible_link(db, loan)
        if not link:
            skipped += 1
            continue
        mandate, state, profile = link
        plan = dict(loan.cdas_collection_plan or {})
        actor_user_id = _actor_from_plan(plan, mandate)
        configuration = get_configuration(db, loan.company_id)
        environment = selected_environment(configuration)
        cache_key = (
            str(loan.company_id),
            environment,
            str(profile.employee_number).strip().casefold(),
        )
        if cache_key in affordability_cache:
            live_affordability = affordability_cache[cache_key]
            reused_reads += 1
        else:
            client = get_company_cdas_client(db, loan.company_id)
            subscription = require_approved_subscription(db, company_id=loan.company_id)
            assert_live_credit_available(
                db,
                subscription=subscription,
                environment=environment,
                operation_type="affordability",
            )
            try:
                live_affordability = _money(await client.check_affordability(profile.employee_number))
            except CdasError:
                skipped += 1
                continue

            affordability_cache[cache_key] = live_affordability
            provider_reads += 1
            record_successful_operation(
                db,
                company_id=loan.company_id,
                environment=environment,
                operation_type="affordability",
                actor_user_id=actor_user_id,
                billing_key=(
                    f"cdas-autopilot-affordability:{loan.company_id}:"
                    f"{profile.employee_number}:{today.isoformat()}"
                ),
                source_reference=str(profile.id),
                metadata={
                    "request_origin": "cdas_autopilot_window",
                    "dedupe_scope": "company_employee_day",
                    "employee_number_present": True,
                },
            )

        decision = decide_cdas_autopilot(
            outstanding_balance=_money(loan.balance),
            current_deduction=_money(mandate.monthly_deduction),
            available_affordability=live_affordability,
            evaluation_date=today,
            dynamic_top_up_consent=bool(plan.get("dynamic_top_up_consent")),
            mandate_maximum=plan.get("dynamic_top_up_maximum"),
        )
        checked += 1
        if decision.action != "top_up":
            continue

        opportunities += 1
        plan["autopilot_topup_opportunity"] = {
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "decision": decision.as_dict(),
            "requires_customer_approval": not decision.execute_automatically,
        }
        loan.cdas_collection_plan = plan
        db.add(loan)
        db.commit()

        if decision.execute_automatically:
            confirmed = await _tracked_modify(
                db,
                loan=loan,
                mandate=mandate,
                state=state,
                total_installment=decision.proposed_remaining_installments,
                deduction_amount=decision.proposed_deduction,
                principal_amount=decision.effective_balance,
                actor_user_id=actor_user_id,
                reason="affordability top-up",
            )
            if confirmed:
                topups += 1
                plan = dict(loan.cdas_collection_plan or {})
                plan.pop("autopilot_topup_opportunity", None)
                plan["autopilot_last_result"] = {
                    "action": "top_up",
                    "confirmed_at": datetime.now(timezone.utc).isoformat(),
                    "decision": decision.as_dict(),
                }
                loan.cdas_collection_plan = plan
                db.add(loan)
                db.commit()

    return {
        "checked": checked,
        "provider_reads": provider_reads,
        "reused_reads": reused_reads,
        "opportunities": opportunities,
        "topups": topups,
        "skipped": skipped,
    }


async def run_cdas_autopilot_cycle(db: Session) -> dict[str, dict[str, int]]:
    payments = await process_pending_payment_reoptimizations(db)
    affordability = await scan_affordability_opportunities(db)
    return {"payments": payments, "affordability": affordability}
