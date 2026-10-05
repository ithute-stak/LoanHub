from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    LENDING_ROLES,
    TenantContext,
    assert_branch_scope,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.audit_log import AuditLog
from database.models.cdas_official import (
    CdasOfficialMandateEvent,
    CdasOfficialMandateState,
    CdasProviderOperation,
)
from database.models.client_loan_company import ClientCompanyLoan
from database.models.enums import LoanStatus, UserRole
from database.models.lending_operations import CDASDeductionMandate, CDASPayrollProfile
from database.models.professional_lending import DirectLoanApplication
from database.session import get_db
from integrations.cdas import CdasClient, CdasError
from integrations.cdas_contracts import (
    CdasLifecyclePayload,
    CdasModifyActivePayload,
    CdasSettlementPayload,
    cdas_reference_data,
)
from services.cdas_config_service import (
    configuration_summary,
    get_company_cdas_client,
    get_configuration,
    get_company_item_code,
    update_selected_environment,
)
from services.cdas_operation_ledger import (
    CdasDuplicateOperationError,
    CdasTrackedProviderError,
    execute_provider_operation,
    operation_summary,
    reconcile_provider_operation,
)
from services.cdas_request_budget import get_cdas_request_budget_status
from services.platform_cdas_service import (
    assert_live_credit_available,
    get_subscription as get_cdas_subscription,
    list_invoices as list_cdas_invoices,
    list_transactions as list_cdas_payg_transactions,
    record_successful_operation,
    request_subscription as request_cdas_subscription,
    require_approved_subscription as require_cdas_subscription,
    subscription_payload as cdas_subscription_payload,
)

router = APIRouter(prefix="/cdas", tags=["CDAS"])


class CdasConfigurationUpdateRequest(BaseModel):
    environment: Literal["test", "live"] = "test"
    enabled: bool = False
    base_url: str = Field(min_length=8, max_length=500)
    username: str = Field(min_length=1, max_length=200)
    item_code: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, max_length=500)
    clear_password: bool = False
    timeout_seconds: float = Field(default=20.0, ge=1, le=120)


class CdasEnvironmentSwitchRequest(BaseModel):
    environment: Literal["test", "live"]


class CdasEmployeeLookupRequest(BaseModel):
    employee_no: str = Field(min_length=1, max_length=100)


class CdasOwnDeductionLookupRequest(CdasEmployeeLookupRequest):
    deduction_status: int = Field(ge=1, le=10)


class CdasDeductionLifecycleRequest(CdasLifecyclePayload):
    confirmed: bool = False


class CdasModifyActiveDeductionRequest(CdasModifyActivePayload):
    confirmed: bool = False


class CdasSettleDeductionRequest(CdasSettlementPayload):
    confirmed: bool = False


class CdasLoanRegistrationConfirmRequest(BaseModel):
    confirmed: bool = False
    borrower_consent: bool = False


class CdasLoanLifecycleConfirmRequest(BaseModel):
    request_type: Literal[3, 4, 6, 10]
    confirmed: bool = False


class CdasLinkedModifyRequest(BaseModel):
    total_installment: int = Field(gt=0)
    deduction_amount: Decimal = Field(gt=Decimal("0"), max_digits=15, decimal_places=2)
    principal_amount: Decimal = Field(gt=Decimal("0"), max_digits=15, decimal_places=2)
    effective_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    confirmed: bool = False


class CdasLinkedSettlementRequest(BaseModel):
    effective_date: str = Field(min_length=10, max_length=50)
    settlement_reason: Literal[1, 2, 3, 4]
    confirmed: bool = False


class CdasDocumentRequest(BaseModel):
    year: int = Field(ge=1, le=9999)
    month: int = Field(ge=1, le=12)
    document_type: int = Field(ge=1, le=2)


def _require_company_manager(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)


def _require_lending_user(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped membership is required")
    require_tenant_roles(context, LENDING_ROLES)


def _require_confirmed(confirmed: bool) -> None:
    if not confirmed:
        raise HTTPException(
            status_code=409,
            detail="Explicit confirmation is required for this CDAS state-changing action",
        )


def _cdas_http_error(exc: CdasError, *, operation: CdasProviderOperation | None = None) -> HTTPException:
    status = exc.status_code if 400 <= exc.status_code <= 599 else 502
    detail: dict[str, Any] = {
        "provider": "CDAS",
        "code": exc.status_code,
        "message": exc.message,
    }
    if operation is not None:
        detail["operation"] = operation_summary(operation)
    return HTTPException(status_code=status, detail=detail)


def _duplicate_operation_error(exc: CdasDuplicateOperationError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "provider": "CDAS",
            "code": "CDAS_DUPLICATE_UNRESOLVED_OPERATION",
            "message": "An identical CDAS mutation is still unresolved. Reconcile it before submitting again.",
            "operation": operation_summary(exc.operation),
        },
    )


def _company_cdas_environment(db: Session, company_id: UUID) -> str:
    row = get_configuration(db, company_id)
    return str(row.environment or "test").strip().lower() if row else "test"


def _prepare_cdas_business_operation(
    db: Session,
    *,
    company_id: UUID,
    operation_type: str,
) -> str:
    environment = _company_cdas_environment(db, company_id)
    subscription = require_cdas_subscription(db, company_id=company_id)
    assert_live_credit_available(
        db,
        subscription=subscription,
        environment=environment,
        operation_type=operation_type,
    )
    return environment


def _record_cdas_business_operation(
    db: Session,
    *,
    context: TenantContext,
    environment: str,
    operation_type: str,
    source_reference: str | None = None,
) -> None:
    assert context.company_id is not None
    record_successful_operation(
        db,
        company_id=context.company_id,
        environment=environment,
        operation_type=operation_type,
        actor_user_id=context.user.id,
        billing_key=f"cdas-read:{uuid4().hex}",
        source_reference=source_reference,
        metadata={"request_origin": "tenant_user"},
    )


def _record_cdas_mutation_audit(
    db: Session,
    context: TenantContext,
    *,
    action: str,
    request_data: dict[str, Any],
    status: str,
    provider_data: dict[str, Any],
) -> None:
    """Best-effort audit record; audit persistence must not repeat a provider mutation."""

    try:
        db.add(
            AuditLog(
                user_id=context.user.id,
                company_id=context.company_id,
                branch_id=context.branch_id,
                action=action,
                table_name="cdas",
                entity_type="external_payroll_deduction",
                description="User-initiated CDAS deduction operation",
                actor_role=getattr(context.role, "value", str(context.role)),
                severity="info" if status == "success" else "warning",
                status=status,
                event_data={
                    "request": request_data,
                    "provider": provider_data,
                },
            )
        )
        db.commit()
    except Exception:
        db.rollback()


async def _execute_tracked_mutation(
    *,
    db: Session,
    context: TenantContext,
    client: CdasClient,
    operation_type: str,
    audit_action: str,
    provider_request: dict[str, Any],
    ledger_request: dict[str, Any],
    provider_call: Callable[[], Awaitable[dict[str, Any]]],
) -> dict[str, Any]:
    assert context.company_id is not None
    environment = _company_cdas_environment(db, context.company_id)
    subscription = require_cdas_subscription(db, company_id=context.company_id)
    billing_operation = (
        "registration"
        if int(provider_request.get("RequestType") or 0) == 1
        else "settlement"
        if "settle" in operation_type
        else "modification"
        if "modify" in operation_type
        else "lifecycle"
    )
    assert_live_credit_available(
        db,
        subscription=subscription,
        environment=environment,
        operation_type=billing_operation,
    )
    try:
        result, operation = await execute_provider_operation(
            db,
            company_id=context.company_id,
            branch_id=context.branch_id,
            actor_user_id=context.user.id,
            environment=environment,
            operation_type=operation_type,
            request_snapshot=ledger_request,
            provider_call=provider_call,
        )
    except CdasDuplicateOperationError as exc:
        raise _duplicate_operation_error(exc) from exc
    except CdasTrackedProviderError as exc:
        _record_cdas_mutation_audit(
            db,
            context,
            action=audit_action,
            request_data=ledger_request,
            status="failed",
            provider_data={
                "code": exc.provider_error.status_code,
                "message": exc.provider_error.message,
                "operation": operation_summary(exc.operation),
            },
        )
        raise _cdas_http_error(exc.provider_error, operation=exc.operation) from exc

    record_successful_operation(
        db,
        company_id=context.company_id,
        environment=environment,
        operation_type=billing_operation,
        actor_user_id=context.user.id,
        billing_key=f"cdas-mutation:{operation.id}",
        source_reference=str(operation.id),
        metadata={"provider_operation_type": operation_type},
    )

    reconciled = False
    try:
        reconciled, operation = await reconcile_provider_operation(
            db,
            operation=operation,
            client=client,
        )
    except CdasError:
        # The provider already acknowledged the mutation. A failed read-back must
        # never turn that into a retryable write failure; the ledger remains in a
        # reconciliation-required state for a later explicit read-only check.
        db.refresh(operation)

    summary = operation_summary(operation)
    _record_cdas_mutation_audit(
        db,
        context,
        action=audit_action,
        request_data=ledger_request,
        status="success" if reconciled else "warning",
        provider_data={
            "response": result,
            "operation": summary,
            "reconciled": reconciled,
        },
    )
    return {
        "ok": True,
        "deduction": result,
        "reconciled": reconciled,
        "operation": summary,
    }


@router.get("/configuration")
def get_cdas_configuration(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    return configuration_summary(
        get_configuration(db, context.company_id),
        db=db,
        company_id=context.company_id,
    )


@router.post("/subscription")
def subscribe_to_cdas(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    row = request_cdas_subscription(
        db,
        company_id=context.company_id,
        requested_by_user_id=context.user.id,
    )
    return cdas_subscription_payload(row, db=db)


@router.put("/environment")
def switch_cdas_environment(
    payload: CdasEnvironmentSwitchRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    if context.role != UserRole.COMPANY_OWNER:
        raise HTTPException(status_code=403, detail="Only the Loan Company Owner can switch CDAS between Test and Live.")
    assert context.company_id is not None
    try:
        row = update_selected_environment(
            db,
            company_id=context.company_id,
            configured_by_user_id=context.user.id,
            environment=payload.environment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return configuration_summary(row, db=db, company_id=context.company_id)


@router.put("/configuration")
def reject_company_cdas_credentials(
    payload: CdasConfigurationUpdateRequest,
    context: TenantContext = Depends(get_tenant_context),
):
    _require_company_manager(context)
    raise HTTPException(
        status_code=403,
        detail=(
            "CDAS credentials, Item Code and provider endpoints are controlled by the LoanHub Platform Owner. "
            "The Loan Company Owner may only switch the approved company between Test and Live."
        ),
    )


@router.post("/configuration/test")
async def reject_company_cdas_test(
    context: TenantContext = Depends(get_tenant_context),
):
    _require_company_manager(context)
    raise HTTPException(
        status_code=403,
        detail="CDAS credential testing is controlled by the LoanHub Platform Owner.",
    )


@router.get("/reference-data")
def get_cdas_reference_data(
    context: TenantContext = Depends(get_tenant_context),
):
    """Return the official CDAS v1.5 codes and limits without contacting CDAS."""
    _require_lending_user(context)
    return cdas_reference_data()


@router.get("/request-budget")
def get_cdas_request_budget(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return LoanHub's local CDAS quota counter without contacting CDAS."""
    _require_lending_user(context)
    assert context.company_id is not None
    row = get_configuration(db, context.company_id)
    environment = str(row.environment or "test").strip().lower() if row else "test"
    return get_cdas_request_budget_status(db, company_id=context.company_id, environment=environment)


def _loan_registration_context(
    db: Session,
    *,
    company_id: UUID,
    loan_id: UUID,
) -> tuple[ClientCompanyLoan, CDASPayrollProfile | None, dict[str, Any] | None, list[str], str]:
    loan = (
        db.query(ClientCompanyLoan)
        .filter(
            ClientCompanyLoan.id == loan_id,
            ClientCompanyLoan.company_id == company_id,
        )
        .first()
    )
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found")

    reasons: list[str] = []
    if not loan.cdas_collection_enabled:
        reasons.append("CDAS collection is not enabled for this loan")
    if loan.status not in {LoanStatus.APPROVED, LoanStatus.ACTIVE}:
        reasons.append("The loan must be approved or active before CDAS registration")

    profile = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == company_id,
            CDASPayrollProfile.borrower_id == loan.borrower_id,
        )
        .first()
    )
    if not profile or not str(profile.employee_number or "").strip():
        reasons.append("A CDAS payroll profile with an employee number is required")
    elif not profile.verified:
        reasons.append("The borrower CDAS payroll profile has not been verified")

    try:
        item_code = get_company_item_code(db, company_id)
    except Exception:
        item_code = ""
    if not item_code:
        reasons.append("Configure the company's CDAS Item Code before registration")

    plan = dict(loan.cdas_collection_plan or {})
    effective_month = str(plan.get("effective_month") or "").strip()
    if not effective_month and loan.first_payment_due:
        effective_month = loan.first_payment_due.strftime("%Y-%m")
    if not effective_month:
        reasons.append("The loan does not have a CDAS effective month")

    provider_payload = None
    if not reasons and profile:
        provider_payload = CdasLifecyclePayload(
            request_type=1,
            deduction_id=0,
            employee_no=profile.employee_number,
            loan_policy=1,
            item_code=item_code,
            deduction_amount=loan.installment_amount or 0,
            total_installment=int(loan.repayment_period or 0),
            principal_amount=loan.principal_amount or 0,
            effective_month=effective_month,
            reference_no=loan.loan_reference,
        ).provider_payload()

    return loan, profile, provider_payload, reasons, effective_month


def _first_provider_int(payload: Any, *keys: str) -> int | None:
    if not isinstance(payload, dict):
        return None
    for key in keys:
        value = payload.get(key)
        if value not in (None, "", 0, "0"):
            try:
                return int(value)
            except (TypeError, ValueError):
                return None
    return None


@router.get("/loans/{loan_id}/registration-draft")
def get_cdas_loan_registration_draft(
    loan_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Build a local CDAS Registration payload without contacting CDAS."""
    _require_company_manager(context)
    assert context.company_id is not None

    loan, _, provider_payload, reasons, _ = _loan_registration_context(
        db,
        company_id=context.company_id,
        loan_id=loan_id,
    )
    registration = None
    if provider_payload:
        registration = {
            "request_type": int(provider_payload["RequestType"]),
            "deduction_id": int(provider_payload["DeductionID"]),
            "employee_no": provider_payload["EmployeeNo"],
            "loan_policy": int(provider_payload["LoanPolicy"]),
            "item_code": provider_payload["ItemCode"],
            "deduction_amount": str(provider_payload["DeductionAmount"]),
            "total_installment": int(provider_payload["TotalInstallment"]),
            "principal_amount": str(provider_payload["PrincipalAmount"]),
            "effective_month": provider_payload["EffectiveMonth"],
            "reference_no": provider_payload["ReferenceNo"],
        }

    return {
        "loan_id": str(loan.id),
        "loan_reference": loan.loan_reference,
        "ready": not reasons,
        "reasons": reasons,
        "registration": registration,
        "provider_request_sent": False,
    }


@router.post("/loans/{loan_id}/register")
async def register_cdas_deduction_for_loan(
    loan_id: UUID,
    payload: CdasLoanRegistrationConfirmRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Register a confirmed LoanHub loan with CDAS and persist the provider link."""
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    if not payload.borrower_consent:
        raise HTTPException(
            status_code=409,
            detail="Confirm the borrower's payroll-deduction consent before CDAS registration",
        )
    assert context.company_id is not None

    loan, profile, provider_request, reasons, effective_month = _loan_registration_context(
        db,
        company_id=context.company_id,
        loan_id=loan_id,
    )
    if reasons or not profile or not provider_request:
        raise HTTPException(status_code=409, detail=" ".join(reasons) or "Loan is not ready for CDAS registration")

    existing_mandate = (
        db.query(CDASDeductionMandate)
        .filter(
            CDASDeductionMandate.company_id == context.company_id,
            CDASDeductionMandate.loan_id == loan.id,
        )
        .first()
    )
    mandate = existing_mandate or CDASDeductionMandate(
        company_id=context.company_id,
        branch_id=loan.branch_id,
        borrower_id=loan.borrower_id,
        loan_id=loan.id,
        payroll_profile_id=profile.id,
        mandate_number=f"CDAS-{loan.loan_reference}"[:80],
        employee_number=profile.employee_number,
        monthly_deduction=loan.installment_amount or 0,
        start_date=loan.first_payment_due,
        end_date=None,
        expected_installments=int(loan.repayment_period or 0),
        deductions_received=0,
        total_expected=loan.total_repayable or 0,
        total_received=0,
        status="draft",
        borrower_consent=True,
        created_by_user_id=context.user.id,
    )
    if existing_mandate is None:
        db.add(mandate)
        db.flush()
    else:
        mandate.payroll_profile_id = profile.id
        mandate.employee_number = profile.employee_number
        mandate.monthly_deduction = loan.installment_amount or 0
        mandate.start_date = loan.first_payment_due
        mandate.expected_installments = int(loan.repayment_period or 0)
        mandate.total_expected = loan.total_repayable or 0
        mandate.borrower_consent = True

    environment = _company_cdas_environment(db, context.company_id)
    state = (
        db.query(CdasOfficialMandateState)
        .filter(CdasOfficialMandateState.mandate_id == mandate.id)
        .first()
    )
    if state is None:
        state = CdasOfficialMandateState(
            company_id=context.company_id,
            mandate_id=mandate.id,
            application_id=loan.direct_application_id,
            environment=environment,
            deduction_id=None,
            item_code=str(provider_request["ItemCode"]),
            reference_no=str(provider_request["ReferenceNo"]),
            loan_policy=int(provider_request["LoanPolicy"]),
            principal_amount=loan.principal_amount or 0,
            effective_month=effective_month,
            cdas_status=None,
            lifecycle_status="registration_pending",
            requires_reconciliation=False,
            last_provider_response={},
        )
        db.add(state)
    else:
        if state.deduction_id:
            raise HTTPException(
                status_code=409,
                detail="This loan is already linked to a CDAS DeductionID; use lifecycle management instead of registering it again",
            )
        state.environment = environment
        state.item_code = str(provider_request["ItemCode"])
        state.reference_no = str(provider_request["ReferenceNo"])
        state.principal_amount = loan.principal_amount or 0
        state.effective_month = effective_month
    mandate.status = "submitted"
    mandate.submitted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    db.refresh(mandate)
    db.refresh(state)

    client = get_company_cdas_client(db, context.company_id)
    ledger_request = CdasLifecyclePayload(
        request_type=1,
        deduction_id=0,
        employee_no=str(provider_request["EmployeeNo"]),
        loan_policy=1,
        item_code=str(provider_request["ItemCode"]),
        deduction_amount=provider_request["DeductionAmount"],
        total_installment=int(provider_request["TotalInstallment"]),
        principal_amount=provider_request["PrincipalAmount"],
        effective_month=str(provider_request["EffectiveMonth"]),
        reference_no=str(provider_request["ReferenceNo"]),
    ).ledger_payload()

    try:
        mutation = await _execute_tracked_mutation(
            db=db,
            context=context,
            client=client,
            operation_type="deduction.lifecycle.1",
            audit_action="cdas.loan.registration",
            provider_request=provider_request,
            ledger_request=ledger_request,
            provider_call=lambda: client.add_update_deduction(provider_request),
        )
    except HTTPException as exc:
        state.lifecycle_status = "registration_failed"
        state.last_error = str(exc.detail)
        state.requires_reconciliation = bool(
            isinstance(exc.detail, dict)
            and isinstance(exc.detail.get("operation"), dict)
            and exc.detail["operation"].get("requires_reconciliation")
        )
        state.last_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        raise

    provider_response = dict(mutation.get("deduction") or {})
    operation = dict(mutation.get("operation") or {})
    operation_response = operation.get("response_snapshot")
    deduction_id = _first_provider_int(provider_response, "DeductionID", "deductionId", "deduction_id")
    if deduction_id is None and isinstance(operation_response, dict):
        deduction_id = _first_provider_int(operation_response, "DeductionID", "deductionId", "deduction_id")
        if deduction_id is None:
            deduction_id = _first_provider_int(
                operation_response.get("reconciliation"),
                "DeductionID",
                "deductionId",
                "deduction_id",
            )

    provider_status = _first_provider_int(provider_response, "DeductionStatus", "deductionStatus", "deduction_status")
    reconciled = bool(mutation.get("reconciled"))

    state.deduction_id = deduction_id
    state.cdas_status = provider_status or (1 if reconciled else None)
    state.lifecycle_status = "registered" if reconciled else "registration_pending"
    state.last_request_type = 1
    state.requires_reconciliation = not reconciled
    state.last_provider_response = provider_response
    state.last_error = None
    state.last_synced_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if reconciled:
        state.registered_at = state.last_synced_at
        mandate.status = "registered"
    mandate.external_reference = str(deduction_id) if deduction_id is not None else mandate.external_reference

    event = CdasOfficialMandateEvent(
        company_id=context.company_id,
        state_id=state.id,
        actor_user_id=context.user.id,
        event_type="registration",
        request_type=1,
        request_snapshot=ledger_request,
        response_snapshot=provider_response,
        provider_status_code=operation.get("provider_status_code"),
        success=True,
        message="CDAS registration confirmed" if reconciled else "CDAS registration submitted; reconciliation is still required",
        occurred_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(event)
    db.commit()
    db.refresh(state)

    return {
        **mutation,
        "mandate_id": str(mandate.id),
        "official_state_id": str(state.id),
        "deduction_id": state.deduction_id,
        "lifecycle_status": state.lifecycle_status,
    }


@router.get("/loans/{loan_id}/state")
def get_cdas_loan_state(
    loan_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_lending_user(context)
    assert context.company_id is not None

    mandate = (
        db.query(CDASDeductionMandate)
        .filter(
            CDASDeductionMandate.company_id == context.company_id,
            CDASDeductionMandate.loan_id == loan_id,
        )
        .first()
    )
    if not mandate:
        raise HTTPException(status_code=404, detail="This loan has no CDAS mandate")

    state = (
        db.query(CdasOfficialMandateState)
        .filter(
            CdasOfficialMandateState.company_id == context.company_id,
            CdasOfficialMandateState.mandate_id == mandate.id,
        )
        .first()
    )
    if not state:
        raise HTTPException(status_code=404, detail="This loan has no official CDAS provider state")

    return {
        "loan_id": str(loan_id),
        "mandate_id": str(mandate.id),
        "mandate_status": mandate.status,
        "employee_no": mandate.employee_number,
        "monthly_deduction": str(mandate.monthly_deduction),
        "expected_installments": mandate.expected_installments,
        "deduction_id": state.deduction_id,
        "item_code": state.item_code,
        "reference_no": state.reference_no,
        "loan_policy": state.loan_policy,
        "principal_amount": str(state.principal_amount),
        "effective_month": state.effective_month,
        "cdas_status": state.cdas_status,
        "lifecycle_status": state.lifecycle_status,
        "requires_reconciliation": bool(state.requires_reconciliation),
        "last_request_type": state.last_request_type,
        "last_synced_at": state.last_synced_at,
    }


@router.post("/loans/{loan_id}/lifecycle")
async def change_linked_cdas_loan_lifecycle(
    loan_id: UUID,
    payload: CdasLoanLifecycleConfirmRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Advance an already-linked CDAS deduction without retyping provider identifiers."""
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    assert context.company_id is not None

    mandate = (
        db.query(CDASDeductionMandate)
        .filter(
            CDASDeductionMandate.company_id == context.company_id,
            CDASDeductionMandate.loan_id == loan_id,
        )
        .first()
    )
    if not mandate:
        raise HTTPException(status_code=404, detail="This loan has no CDAS mandate")
    state = (
        db.query(CdasOfficialMandateState)
        .filter(
            CdasOfficialMandateState.company_id == context.company_id,
            CdasOfficialMandateState.mandate_id == mandate.id,
        )
        .first()
    )
    if not state or not state.deduction_id:
        raise HTTPException(
            status_code=409,
            detail="This loan is not linked to a confirmed CDAS DeductionID",
        )
    if state.requires_reconciliation:
        raise HTTPException(
            status_code=409,
            detail="Reconcile the previous CDAS operation before submitting another lifecycle change",
        )

    lifecycle = CdasLifecyclePayload(
        request_type=payload.request_type,
        deduction_id=int(state.deduction_id),
        employee_no=mandate.employee_number,
        loan_policy=int(state.loan_policy),
        item_code=state.item_code,
        deduction_amount=mandate.monthly_deduction,
        total_installment=int(mandate.expected_installments),
        principal_amount=state.principal_amount,
        effective_month=state.effective_month,
        reference_no=state.reference_no,
    )
    provider_request = lifecycle.provider_payload()
    ledger_request = lifecycle.ledger_payload()
    client = get_company_cdas_client(db, context.company_id)

    mutation = await _execute_tracked_mutation(
        db=db,
        context=context,
        client=client,
        operation_type=f"deduction.lifecycle.{payload.request_type}",
        audit_action="cdas.loan.lifecycle",
        provider_request=provider_request,
        ledger_request=ledger_request,
        provider_call=lambda: client.add_update_deduction(provider_request),
    )

    reconciled = bool(mutation.get("reconciled"))
    provider_response = dict(mutation.get("deduction") or {})
    status_by_request = {3: ("reviewed", 3), 4: ("approved", 4), 6: ("cancelled", 6), 10: ("changed", 10)}
    lifecycle_status, cdas_status = status_by_request[payload.request_type]
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    state.last_request_type = payload.request_type
    state.last_provider_response = provider_response
    state.last_error = None
    state.last_synced_at = now
    state.requires_reconciliation = not reconciled
    if reconciled:
        state.lifecycle_status = lifecycle_status
        state.cdas_status = cdas_status
        if payload.request_type == 3:
            state.reviewed_at = now
            mandate.status = "reviewed"
        elif payload.request_type == 4:
            state.approved_at = now
            mandate.status = "approved"
        elif payload.request_type == 6:
            state.cancelled_at = now
            mandate.status = "cancelled"
    else:
        state.lifecycle_status = f"{lifecycle_status}_pending"

    db.add(
        CdasOfficialMandateEvent(
            company_id=context.company_id,
            state_id=state.id,
            actor_user_id=context.user.id,
            event_type=f"lifecycle_{payload.request_type}",
            request_type=payload.request_type,
            request_snapshot=ledger_request,
            response_snapshot=provider_response,
            provider_status_code=(mutation.get("operation") or {}).get("provider_status_code"),
            success=True,
            message=(
                f"CDAS lifecycle request {payload.request_type} confirmed"
                if reconciled
                else f"CDAS lifecycle request {payload.request_type} submitted; reconciliation is still required"
            ),
            occurred_at=now,
        )
    )
    db.commit()
    db.refresh(state)

    return {
        **mutation,
        "mandate_id": str(mandate.id),
        "deduction_id": state.deduction_id,
        "lifecycle_status": state.lifecycle_status,
        "cdas_status": state.cdas_status,
    }


@router.post("/loans/{loan_id}/modify-active")
async def modify_linked_cdas_active_deduction(
    loan_id: UUID,
    payload: CdasLinkedModifyRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    assert context.company_id is not None

    mandate = (
        db.query(CDASDeductionMandate)
        .filter(
            CDASDeductionMandate.company_id == context.company_id,
            CDASDeductionMandate.loan_id == loan_id,
        )
        .first()
    )
    if not mandate:
        raise HTTPException(status_code=404, detail="This loan has no CDAS mandate")
    state = (
        db.query(CdasOfficialMandateState)
        .filter(
            CdasOfficialMandateState.company_id == context.company_id,
            CdasOfficialMandateState.mandate_id == mandate.id,
        )
        .first()
    )
    if not state or not state.deduction_id:
        raise HTTPException(status_code=409, detail="This loan is not linked to a confirmed CDAS DeductionID")
    if state.requires_reconciliation:
        raise HTTPException(status_code=409, detail="Reconcile the previous CDAS operation before modifying this deduction")

    modify = CdasModifyActivePayload(
        employee_no=mandate.employee_number,
        item_code=state.item_code,
        total_installment=payload.total_installment,
        deduction_amount=payload.deduction_amount,
        principal_amount=payload.principal_amount,
        deduction_id=int(state.deduction_id),
        effective_date=payload.effective_date,
    )
    provider_request = modify.provider_payload()
    ledger_request = modify.ledger_payload()
    client = get_company_cdas_client(db, context.company_id)

    mutation = await _execute_tracked_mutation(
        db=db,
        context=context,
        client=client,
        operation_type="deduction.modify_active",
        audit_action="cdas.loan.modify_active",
        provider_request=provider_request,
        ledger_request=ledger_request,
        provider_call=lambda: client.modify_active_deduction(provider_request),
    )

    reconciled = bool(mutation.get("reconciled"))
    provider_response = dict(mutation.get("deduction") or {})
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    state.last_request_type = 10
    state.last_provider_response = provider_response
    state.last_error = None
    state.last_synced_at = now
    state.requires_reconciliation = not reconciled
    state.lifecycle_status = "changed" if reconciled else "change_pending"
    if reconciled:
        state.cdas_status = 10
        mandate.monthly_deduction = payload.deduction_amount
        mandate.expected_installments = payload.total_installment
        mandate.total_expected = payload.principal_amount
        mandate.status = "changed"

    db.add(
        CdasOfficialMandateEvent(
            company_id=context.company_id,
            state_id=state.id,
            actor_user_id=context.user.id,
            event_type="modify_active",
            request_type=10,
            request_snapshot=ledger_request,
            response_snapshot=provider_response,
            provider_status_code=(mutation.get("operation") or {}).get("provider_status_code"),
            success=True,
            message="Active CDAS deduction modification confirmed" if reconciled else "Active CDAS deduction modification submitted; reconciliation is still required",
            occurred_at=now,
        )
    )
    db.commit()
    db.refresh(state)

    return {
        **mutation,
        "mandate_id": str(mandate.id),
        "deduction_id": state.deduction_id,
        "lifecycle_status": state.lifecycle_status,
        "cdas_status": state.cdas_status,
    }


@router.post("/loans/{loan_id}/settle")
async def settle_linked_cdas_deduction(
    loan_id: UUID,
    payload: CdasLinkedSettlementRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    assert context.company_id is not None

    mandate = (
        db.query(CDASDeductionMandate)
        .filter(
            CDASDeductionMandate.company_id == context.company_id,
            CDASDeductionMandate.loan_id == loan_id,
        )
        .first()
    )
    if not mandate:
        raise HTTPException(status_code=404, detail="This loan has no CDAS mandate")
    state = (
        db.query(CdasOfficialMandateState)
        .filter(
            CdasOfficialMandateState.company_id == context.company_id,
            CdasOfficialMandateState.mandate_id == mandate.id,
        )
        .first()
    )
    if not state or not state.deduction_id:
        raise HTTPException(status_code=409, detail="This loan is not linked to a confirmed CDAS DeductionID")
    if state.requires_reconciliation:
        raise HTTPException(status_code=409, detail="Reconcile the previous CDAS operation before settling this deduction")

    settlement = CdasSettlementPayload(
        item_code=state.item_code,
        deduction_id=int(state.deduction_id),
        effective_date=payload.effective_date,
        employee_no=mandate.employee_number,
        settlement_reason=payload.settlement_reason,
    )
    provider_request = settlement.provider_payload()
    ledger_request = settlement.ledger_payload()
    client = get_company_cdas_client(db, context.company_id)

    mutation = await _execute_tracked_mutation(
        db=db,
        context=context,
        client=client,
        operation_type="deduction.settle",
        audit_action="cdas.loan.settlement",
        provider_request=provider_request,
        ledger_request=ledger_request,
        provider_call=lambda: client.settle_deduction(provider_request),
    )

    reconciled = bool(mutation.get("reconciled"))
    provider_response = dict(mutation.get("deduction") or {})
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    state.last_request_type = 7
    state.last_provider_response = provider_response
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
            company_id=context.company_id,
            state_id=state.id,
            actor_user_id=context.user.id,
            event_type="settlement",
            request_type=7,
            request_snapshot=ledger_request,
            response_snapshot=provider_response,
            provider_status_code=(mutation.get("operation") or {}).get("provider_status_code"),
            success=True,
            message="CDAS settlement confirmed" if reconciled else "CDAS settlement submitted; reconciliation is still required",
            occurred_at=now,
        )
    )
    db.commit()
    db.refresh(state)

    return {
        **mutation,
        "mandate_id": str(mandate.id),
        "deduction_id": state.deduction_id,
        "lifecycle_status": state.lifecycle_status,
        "cdas_status": state.cdas_status,
    }


@router.get("/operations")
def list_cdas_operations(
    state: str | None = Query(default=None, max_length=40),
    limit: int = Query(default=50, ge=1, le=200),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Return the company's local CDAS mutation ledger without contacting CDAS."""
    _require_company_manager(context)
    assert context.company_id is not None
    query = db.query(CdasProviderOperation).filter(CdasProviderOperation.company_id == context.company_id)
    if state:
        query = query.filter(CdasProviderOperation.state == state.strip().lower())
    rows = query.order_by(CdasProviderOperation.created_at.desc()).limit(limit).all()
    return {"items": [operation_summary(row) for row in rows], "count": len(rows)}


@router.get("/operations/{operation_id}")
def get_cdas_operation(
    operation_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    row = db.query(CdasProviderOperation).filter(
        CdasProviderOperation.id == operation_id,
        CdasProviderOperation.company_id == context.company_id,
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="CDAS operation not found")
    return operation_summary(row)


@router.post("/operations/{operation_id}/reconcile")
async def reconcile_cdas_operation(
    operation_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Read CDAS to reconcile one mutation; this endpoint never replays a write."""
    _require_company_manager(context)
    assert context.company_id is not None
    operation = db.query(CdasProviderOperation).filter(
        CdasProviderOperation.id == operation_id,
        CdasProviderOperation.company_id == context.company_id,
    ).one_or_none()
    if operation is None:
        raise HTTPException(status_code=404, detail="CDAS operation not found")

    current_environment = _company_cdas_environment(db, context.company_id)
    if operation.environment != current_environment:
        raise HTTPException(
            status_code=409,
            detail="This CDAS operation belongs to a different provider environment",
        )

    try:
        client = get_company_cdas_client(db, context.company_id)
        matched, operation = await reconcile_provider_operation(db, operation=operation, client=client)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CdasError as exc:
        db.refresh(operation)
        raise _cdas_http_error(exc, operation=operation) from exc

    return {"ok": True, "reconciled": matched, "operation": operation_summary(operation)}


@router.post("/employees/verify")
async def verify_cdas_employee(
    payload: CdasEmployeeLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_lending_user(context)
    assert context.company_id is not None
    environment = _prepare_cdas_business_operation(db, company_id=context.company_id, operation_type="employee_verification")
    try:
        client = get_company_cdas_client(db, context.company_id)
        employee = await client.get_employee_details(payload.employee_no)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    _record_cdas_business_operation(
        db,
        context=context,
        environment=environment,
        operation_type="employee_verification",
        source_reference=payload.employee_no.strip(),
    )
    return {"ok": True, "employee": employee}


@router.post("/applications/{application_id}/verify-employee")
async def verify_cdas_employee_for_application(
    application_id: UUID,
    payload: CdasEmployeeLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Verify one application's borrower against CDAS and store the local payroll link."""
    _require_lending_user(context)
    assert context.company_id is not None

    application = (
        db.query(DirectLoanApplication)
        .filter(
            DirectLoanApplication.id == application_id,
            DirectLoanApplication.company_id == context.company_id,
        )
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Loan application not found")
    assert_branch_scope(context, application.branch_id)

    environment = _prepare_cdas_business_operation(db, company_id=context.company_id, operation_type="employee_verification")
    try:
        client = get_company_cdas_client(db, context.company_id)
        employee = await client.get_employee_details(payload.employee_no)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc

    requested_employee_no = payload.employee_no.strip()
    returned_employee_no = str(employee.get("EmployeeNo") or "").strip()
    if returned_employee_no.casefold() != requested_employee_no.casefold():
        raise HTTPException(
            status_code=502,
            detail="CDAS returned a different employee number than the one requested",
        )

    profile = (
        db.query(CDASPayrollProfile)
        .filter(
            CDASPayrollProfile.company_id == context.company_id,
            CDASPayrollProfile.borrower_id == application.borrower_id,
        )
        .first()
    )
    if not profile:
        profile = CDASPayrollProfile(
            company_id=context.company_id,
            borrower_id=application.borrower_id,
            branch_id=application.branch_id,
            employee_number=returned_employee_no,
            ministry_department=employee.get("Department"),
            employment_status="active",
            verified=True,
            verified_at=datetime.now(timezone.utc),
            verified_by_user_id=context.user.id,
            verification_reference="CDAS employee details",
            verification_notes="Verified using CDAS /api/employee/getDetails (Third Party API v1.5).",
        )
        db.add(profile)
    else:
        profile.branch_id = application.branch_id
        profile.employee_number = returned_employee_no
        profile.ministry_department = employee.get("Department")
        profile.verified = True
        profile.verified_at = datetime.now(timezone.utc)
        profile.verified_by_user_id = context.user.id
        profile.verification_reference = "CDAS employee details"
        profile.verification_notes = "Verified using CDAS /api/employee/getDetails (Third Party API v1.5)."

    db.commit()
    db.refresh(profile)
    _record_cdas_business_operation(
        db,
        context=context,
        environment=environment,
        operation_type="employee_verification",
        source_reference=str(application.id),
    )
    return {
        "ok": True,
        "application_id": str(application.id),
        "borrower_id": str(application.borrower_id),
        "employee": employee,
        "payroll_profile": {
            "id": str(profile.id),
            "employee_number": profile.employee_number,
            "verified": bool(profile.verified),
            "verified_at": profile.verified_at,
            "department": profile.ministry_department,
        },
    }


@router.post("/employees/affordability")
async def check_cdas_affordability(
    payload: CdasEmployeeLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_lending_user(context)
    assert context.company_id is not None
    environment = _prepare_cdas_business_operation(db, company_id=context.company_id, operation_type="affordability")
    try:
        client = get_company_cdas_client(db, context.company_id)
        affordability = await client.check_affordability(payload.employee_no)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    _record_cdas_business_operation(db, context=context, environment=environment, operation_type="affordability", source_reference=payload.employee_no.strip())
    return {"ok": True, "affordability": affordability}


@router.post("/deductions/all")
async def view_all_cdas_deductions(
    payload: CdasEmployeeLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_lending_user(context)
    assert context.company_id is not None
    environment = _prepare_cdas_business_operation(db, company_id=context.company_id, operation_type="deduction_lookup")
    try:
        client = get_company_cdas_client(db, context.company_id)
        deductions = await client.view_all_deductions(payload.employee_no)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    _record_cdas_business_operation(db, context=context, environment=environment, operation_type="deduction_lookup", source_reference=payload.employee_no.strip())
    return {"ok": True, "deductions": deductions}


@router.post("/deductions/own")
async def view_own_cdas_deductions(
    payload: CdasOwnDeductionLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_lending_user(context)
    assert context.company_id is not None
    environment = _prepare_cdas_business_operation(db, company_id=context.company_id, operation_type="deduction_lookup")
    try:
        client = get_company_cdas_client(db, context.company_id)
        deductions = await client.view_own_deductions(payload.employee_no, payload.deduction_status)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    _record_cdas_business_operation(db, context=context, environment=environment, operation_type="deduction_lookup", source_reference=payload.employee_no.strip())
    return {"ok": True, "deductions": deductions}


@router.post("/deductions/active-approved")
async def get_active_approved_cdas_deduction(
    payload: CdasEmployeeLookupRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_lending_user(context)
    assert context.company_id is not None
    environment = _prepare_cdas_business_operation(db, company_id=context.company_id, operation_type="deduction_lookup")
    try:
        client = get_company_cdas_client(db, context.company_id)
        deduction = await client.get_active_and_approved_deduction(payload.employee_no)
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    _record_cdas_business_operation(db, context=context, environment=environment, operation_type="deduction_lookup", source_reference=payload.employee_no.strip())
    return {"ok": True, "deduction": deduction}


@router.post("/deductions/lifecycle")
async def change_cdas_deduction_lifecycle(
    payload: CdasDeductionLifecycleRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    assert context.company_id is not None
    client = get_company_cdas_client(db, context.company_id)
    provider_request = payload.provider_payload()
    ledger_request = payload.ledger_payload()
    return await _execute_tracked_mutation(
        db=db,
        context=context,
        client=client,
        operation_type=f"deduction.lifecycle.{payload.request_type}",
        audit_action="cdas.deduction.lifecycle",
        provider_request=provider_request,
        ledger_request=ledger_request,
        provider_call=lambda: client.add_update_deduction(provider_request),
    )


@router.post("/deductions/modify-active")
async def modify_active_cdas_deduction(
    payload: CdasModifyActiveDeductionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    assert context.company_id is not None
    client = get_company_cdas_client(db, context.company_id)
    provider_request = payload.provider_payload()
    ledger_request = payload.ledger_payload()
    return await _execute_tracked_mutation(
        db=db,
        context=context,
        client=client,
        operation_type="deduction.modify_active",
        audit_action="cdas.deduction.modify_active",
        provider_request=provider_request,
        ledger_request=ledger_request,
        provider_call=lambda: client.modify_active_deduction(provider_request),
    )


@router.post("/deductions/settle")
async def settle_cdas_deduction(
    payload: CdasSettleDeductionRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    _require_confirmed(payload.confirmed)
    assert context.company_id is not None
    client = get_company_cdas_client(db, context.company_id)
    provider_request = payload.provider_payload()
    ledger_request = payload.ledger_payload()
    return await _execute_tracked_mutation(
        db=db,
        context=context,
        client=client,
        operation_type="deduction.settle",
        audit_action="cdas.deduction.settle",
        provider_request=provider_request,
        ledger_request=ledger_request,
        provider_call=lambda: client.settle_deduction(provider_request),
    )


@router.post("/documents")
async def get_cdas_document(
    payload: CdasDocumentRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_company_manager(context)
    assert context.company_id is not None
    environment = _prepare_cdas_business_operation(db, company_id=context.company_id, operation_type="document")
    try:
        client = get_company_cdas_client(db, context.company_id)
        document = await client.get_document(
            year=payload.year,
            month=payload.month,
            document_type=payload.document_type,
        )
    except CdasError as exc:
        raise _cdas_http_error(exc) from exc
    _record_cdas_business_operation(
        db,
        context=context,
        environment=environment,
        operation_type="document",
        source_reference=f"{payload.year:04d}-{payload.month:02d}:{payload.document_type}",
    )
    return {"ok": True, "document": document}


@router.get("/transactions")
def get_company_cdas_transactions(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    limit: int = 200,
):
    _require_company_manager(context)
    assert context.company_id is not None
    return list_cdas_payg_transactions(db, company_id=context.company_id, limit=limit)



@router.get("/invoices")
def get_company_cdas_invoices(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
):
    _require_company_manager(context)
    assert context.company_id is not None
    return list_cdas_invoices(db, company_id=context.company_id, limit=limit)
