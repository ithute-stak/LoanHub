from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    get_user_context,
    require_platform_owner,
    require_tenant_roles,
)
from database.models.audit_log import AuditLog
from database.models.platform_credit_bureau import (
    PlatformCreditBureauConfiguration,
    PlatformCreditBureauSubscription,
    PlatformCreditBureauTransaction,
)
from database.models.company import LoanCompany
from database.models.user import User
from database.schemas.credit_bureau import (
    CreditBureauInvoiceCreate,
    CreditBureauTransactionWaiver,
    ExperianConfigurationUpdate,
    ExperianSubscriptionDecision,
)
from database.session import get_db
from services.credential_service import decrypt_credential, encrypt_credential
from services.experian_service import (
    ExperianConfigurationError,
    ExperianRequestError,
    canonical_environment,
    credential_profiles,
    environment_test_status,
    has_credentials_for_environment,
    public_configuration,
    test_connection,
)
from services.credit_bureau_payg_service import (
    create_invoice,
    invoice_payload,
    list_invoices,
    mark_invoice_paid,
    refund_transaction,
    review_subscription,
    subscription_payload,
    transaction_payload,
    usage_summary,
    waive_transaction,
)


router = APIRouter(prefix="/platform-owner/credit-bureau", tags=["Platform Owner Credit Bureau"])
company_guard_router = APIRouter(prefix="/origination", tags=["Credit Origination Integrations"])


class ProviderInvoiceSettlement(BaseModel):
    payment_method: str = Field(pattern="^(cash|bank|electronic)$")
    proof_reference: str | None = Field(default=None, max_length=180)
    notes: str | None = Field(default=None, max_length=1000)

class CreditBureauTransactionRefund(BaseModel):
    reason: str = Field(min_length=3, max_length=1000)
    payment_method: str = Field(pattern="^(cash|bank|electronic)$")
    proof_reference: str | None = Field(default=None, max_length=180)



@company_guard_router.put("/integrations/experian")
def reject_company_experian_provider_credentials(
    context: TenantContext = Depends(get_user_context),
):
    """Override the old dynamic company integration route for Experian.

    The static route is registered before `/origination/integrations/{provider}`
    so tenant callers cannot reintroduce provider credentials through the legacy
    generic integration API.
    """
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    raise HTTPException(
        status_code=403,
        detail=(
            "Experian provider credentials are controlled by the LoanHub Platform Owner. "
            "Configure company usage under Credit Origination → Experian credit bureau."
        ),
    )


def _public_environment(value: str | None) -> str:
    normalized = str(value or "sandbox").strip().lower()
    return "live" if normalized in {"live", "production"} else "sandbox"


def _get_row(db: Session) -> PlatformCreditBureauConfiguration | None:
    return (
        db.query(PlatformCreditBureauConfiguration)
        .filter(PlatformCreditBureauConfiguration.provider == "experian")
        .first()
    )


def _profile_states(row: PlatformCreditBureauConfiguration | None) -> dict:
    result = {
        "sandbox": {"has_credentials": False, "last_test_status": None, "last_tested_at": None},
        "live": {"has_credentials": False, "last_test_status": None, "last_tested_at": None},
    }
    if not row:
        return result
    profiles = credential_profiles(row)
    configuration = dict(row.configuration or {})
    states = configuration.get("environment_states")
    states = states if isinstance(states, dict) else {}
    for environment in ("sandbox", "live"):
        state = states.get(environment)
        state = state if isinstance(state, dict) else {}
        result[environment] = {
            "has_credentials": environment in profiles,
            "last_test_status": state.get("last_test_status") or environment_test_status(row, environment),
            "last_tested_at": state.get("last_tested_at"),
        }
    return result


def _read(row: PlatformCreditBureauConfiguration | None) -> dict:
    configuration = public_configuration(row)
    profile_states = _profile_states(row)
    contract_ready = (
        configuration.get("product") == "normal_search_v2"
        and bool(str(configuration.get("origin") or "").strip())
        and bool(str(configuration.get("dll_version") or "").strip())
    )
    mapping_ready = isinstance(configuration.get("response_mapping"), dict)
    return {
        "provider": "experian",
        "scope": "platform",
        "environment": _public_environment(row.environment if row else "sandbox"),
        "environment_profiles": profile_states,
        "is_enabled": bool(row.is_enabled) if row else False,
        "has_credentials": bool(row and any(value["has_credentials"] for value in profile_states.values())),
        "last_test_status": row.last_test_status if row else None,
        "last_tested_at": row.last_tested_at if row else None,
        "configuration": configuration,
        "readiness": {
            "credentials": bool(row and any(value["has_credentials"] for value in profile_states.values())),
            "connection_tested": bool(row and row.last_test_status == "connected"),
            "normal_search_contract": contract_ready,
            "response_mapping": mapping_ready,
            "ready_for_company_use": bool(
                row
                and row.is_enabled
                and any(
                    value["has_credentials"] and value["last_test_status"] == "connected"
                    for value in profile_states.values()
                )
                and contract_ready
                and mapping_ready
            ),
        },
    }


@router.get("/experian/configuration")
def get_platform_experian_configuration(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    try:
        return _read(_get_row(db))
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Platform Experian configuration storage is not ready. Run alembic upgrade head.",
        ) from error


@router.put("/experian/configuration")
def update_platform_experian_configuration(
    payload: ExperianConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    try:
        row = _get_row(db)
        if not row:
            row = PlatformCreditBureauConfiguration(provider="experian")
            db.add(row)
            db.flush()

        before = _read(row)
        credentials_changed = payload.credentials is not None
        selected_environment = canonical_environment(payload.environment)

        previous_configuration = dict(row.configuration or {})
        environment_states = previous_configuration.get("environment_states")
        environment_states = dict(environment_states) if isinstance(environment_states, dict) else {}

        row.environment = selected_environment
        row.is_enabled = payload.is_enabled
        row.configuration = {**payload.configuration, "environment_states": environment_states}
        row.configured_by_user_id = current_user.id
        if payload.credentials is not None:
            profiles = credential_profiles(row)
            profiles[selected_environment] = payload.credentials.model_dump()
            row.encrypted_credentials = encrypt_credential(
                json.dumps(profiles, separators=(",", ":"))
            )
            environment_states[selected_environment] = {
                "last_test_status": None,
                "last_tested_at": None,
            }
            row.configuration = {**dict(row.configuration or {}), "environment_states": environment_states}
            row.last_test_status = None
            row.last_tested_at = None

        db.flush()
        after = _read(row)
        db.add(
            AuditLog(
                user_id=current_user.id,
                action="platform_experian_configuration_updated",
                table_name="platform_credit_bureau_configurations",
                entity_type="platform_credit_bureau_configuration",
                record_id=row.id,
                description="The platform owner updated LoanHub's central Experian credit-bureau configuration.",
                actor_role=current_user.role.value,
                severity="warning" if before.get("is_enabled") != after.get("is_enabled") else "info",
                status="success",
                before_data={
                    "environment": before.get("environment"),
                    "is_enabled": before.get("is_enabled"),
                    "has_credentials": before.get("has_credentials"),
                    "configuration": before.get("configuration"),
                },
                after_data={
                    "environment": after.get("environment"),
                    "is_enabled": after.get("is_enabled"),
                    "has_credentials": after.get("has_credentials"),
                    "configuration": after.get("configuration"),
                },
                changed_fields=[
                    field
                    for field in ("environment", "is_enabled", "has_credentials", "configuration")
                    if before.get(field) != after.get(field)
                ] + (["credentials_rotated"] if credentials_changed else []),
                event_data={
                    "source": "superadmin_experian_configuration",
                    "secrets_persisted_encrypted": True,
                    "company_credentials_used": False,
                },
            )
        )
        db.commit()
        db.refresh(row)
        return _read(row)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Platform Experian configuration storage is not ready. Run alembic upgrade head.",
        ) from error


@router.post("/experian/test-connection")
def test_platform_experian_connection(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    try:
        row = _get_row(db)
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="Platform Experian configuration storage is not ready. Run alembic upgrade head.",
        ) from error
    if not row:
        raise HTTPException(status_code=409, detail="Configure Experian in Platform Owner → API & integrations first")

    try:
        selected_environment = canonical_environment(row.environment)
        result = test_connection(row, environment=selected_environment)
    except ExperianConfigurationError as error:
        tested_at = datetime.now(timezone.utc)
        row.last_test_status = "configuration_error"
        row.last_tested_at = tested_at
        configuration = dict(row.configuration or {})
        states = configuration.get("environment_states")
        states = dict(states) if isinstance(states, dict) else {}
        states[canonical_environment(row.environment)] = {"last_test_status": "configuration_error", "last_tested_at": tested_at.isoformat()}
        row.configuration = {**configuration, "environment_states": states}
        db.commit()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ExperianRequestError as error:
        tested_at = datetime.now(timezone.utc)
        row.last_test_status = error.code
        row.last_tested_at = tested_at
        configuration = dict(row.configuration or {})
        states = configuration.get("environment_states")
        states = dict(states) if isinstance(states, dict) else {}
        states[canonical_environment(row.environment)] = {"last_test_status": error.code, "last_tested_at": tested_at.isoformat()}
        row.configuration = {**configuration, "environment_states": states}
        db.commit()
        raise HTTPException(status_code=502, detail=str(error)) from error

    tested_at = datetime.now(timezone.utc)
    row.last_test_status = "connected"
    row.last_tested_at = tested_at
    configuration = dict(row.configuration or {})
    states = configuration.get("environment_states")
    states = dict(states) if isinstance(states, dict) else {}
    states[selected_environment] = {
        "last_test_status": "connected",
        "last_tested_at": tested_at.isoformat(),
    }
    row.configuration = {**configuration, "environment_states": states}
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="platform_experian_connection_tested",
            table_name="platform_credit_bureau_configurations",
            entity_type="platform_credit_bureau_configuration",
            record_id=row.id,
            description="The platform owner successfully tested the central Experian Lesotho connection.",
            actor_role=current_user.role.value,
            severity="info",
            status="success",
            after_data={"environment": row.environment, "status": "connected", "host": result.get("host")},
            changed_fields=["last_test_status", "last_tested_at"],
            event_data={"source": "superadmin_experian_connection_test", "protocol": "lesotho_normal_search_rest_v0.5"},
        )
    )
    db.commit()
    return result


@router.get("/experian/subscriptions")
def list_experian_subscriptions(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    rows = (
        db.query(PlatformCreditBureauSubscription, LoanCompany)
        .join(LoanCompany, LoanCompany.id == PlatformCreditBureauSubscription.company_id)
        .filter(PlatformCreditBureauSubscription.provider == "experian")
        .order_by(PlatformCreditBureauSubscription.requested_at.desc())
        .all()
    )
    result = []
    for subscription, company in rows:
        item = subscription_payload(subscription, db=db)
        item["company"] = {
            "id": str(company.id),
            "name": company.name,
            "registration_number": company.registration_number,
            "license_number": company.license_number,
        }
        result.append(item)
    return result


@router.post("/experian/subscriptions/{company_id}/decision")
def decide_experian_subscription(
    company_id: UUID,
    payload: ExperianSubscriptionDecision,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    platform = _get_row(db)
    if payload.decision == "approved":
        if not platform or not platform.is_enabled:
            raise HTTPException(status_code=409, detail="Enable the platform Experian service before approving companies")
        price = payload.price_per_transaction
        if price is None:
            price = float(dict(platform.configuration or {}).get("default_price_per_transaction") or 0)
        if price <= 0:
            raise HTTPException(
                status_code=409,
                detail="Set a positive PAYG price per successful Credit Bureau transaction before approval",
            )
    else:
        price = payload.price_per_transaction

    row = review_subscription(
        db,
        company_id=company_id,
        reviewer_user_id=current_user.id,
        decision=payload.decision,
        price_per_transaction=Decimal(str(price)) if price is not None else None,
        currency=payload.currency,
        reason=payload.reason,
        notes=payload.notes,
        credit_limit=Decimal(str(payload.credit_limit)) if payload.credit_limit is not None else None,
        warning_threshold=Decimal(str(payload.warning_threshold)) if payload.warning_threshold is not None else None,
        auto_suspend_on_limit=payload.auto_suspend_on_limit,
        billing_due_days=payload.billing_due_days,
    )
    return subscription_payload(row)


@router.get("/experian/transactions")
def list_experian_payg_transactions(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
    limit: int = 200,
):
    rows = (
        db.query(PlatformCreditBureauTransaction)
        .filter(PlatformCreditBureauTransaction.provider == "experian")
        .order_by(PlatformCreditBureauTransaction.accrued_at.desc())
        .limit(max(1, min(limit, 1000)))
        .all()
    )
    return [transaction_payload(row) for row in rows]


@router.get("/experian/usage/{company_id}")
def get_experian_company_usage(
    company_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    return usage_summary(db, company_id=company_id)


@router.post("/experian/transactions/{transaction_id}/waive")
def waive_experian_transaction(
    transaction_id: UUID,
    payload: CreditBureauTransactionWaiver,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    return transaction_payload(
        waive_transaction(db, transaction_id=transaction_id, reason=payload.reason)
    )


@router.post("/experian/transactions/{transaction_id}/refund")
def refund_experian_transaction(
    transaction_id: UUID,
    payload: CreditBureauTransactionRefund,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    return transaction_payload(
        refund_transaction(
            db,
            transaction_id=transaction_id,
            reason=payload.reason,
            payment_method=payload.payment_method,
            proof_reference=payload.proof_reference,
        )
    )


@router.post("/experian/invoices/{company_id}")
def issue_experian_invoice(
    company_id: UUID,
    payload: CreditBureauInvoiceCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    return invoice_payload(
        create_invoice(
            db,
            company_id=company_id,
            period_start=payload.period_start,
            period_end=payload.period_end,
        )
    )


@router.get("/experian/invoices")
def list_experian_invoices(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
    limit: int = 200,
):
    return list_invoices(db, limit=limit)


@router.post("/experian/invoices/{invoice_id}/paid")
def mark_experian_invoice_paid(
    invoice_id: UUID,
    payload: ProviderInvoiceSettlement,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    return invoice_payload(mark_invoice_paid(
        db,
        invoice_id=invoice_id,
        payment_method=payload.payment_method,
        proof_reference=payload.proof_reference,
        notes=payload.notes,
    ))
