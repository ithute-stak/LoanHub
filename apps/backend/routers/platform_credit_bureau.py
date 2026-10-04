from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
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
from database.models.platform_credit_bureau import PlatformCreditBureauConfiguration
from database.models.user import User
from database.schemas.credit_bureau import ExperianConfigurationUpdate
from database.session import get_db
from services.credential_service import encrypt_credential
from services.experian_service import (
    ExperianConfigurationError,
    ExperianRequestError,
    public_configuration,
    test_connection,
)


router = APIRouter(prefix="/platform-owner/credit-bureau", tags=["Platform Owner Credit Bureau"])
company_guard_router = APIRouter(prefix="/origination", tags=["Credit Origination Integrations"])


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


def _read(row: PlatformCreditBureauConfiguration | None) -> dict:
    configuration = public_configuration(row)
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
        "is_enabled": bool(row.is_enabled) if row else False,
        "has_credentials": bool(row and row.encrypted_credentials),
        "last_test_status": row.last_test_status if row else None,
        "last_tested_at": row.last_tested_at if row else None,
        "configuration": configuration,
        "readiness": {
            "credentials": bool(row and row.encrypted_credentials),
            "connection_tested": bool(row and row.last_test_status == "connected"),
            "normal_search_contract": contract_ready,
            "response_mapping": mapping_ready,
            "ready_for_company_use": bool(
                row
                and row.is_enabled
                and row.encrypted_credentials
                and row.last_test_status == "connected"
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
        environment_changed = _public_environment(row.environment) != payload.environment
        credentials_changed = payload.credentials is not None

        row.environment = payload.environment
        row.is_enabled = payload.is_enabled
        row.configuration = payload.configuration
        row.configured_by_user_id = current_user.id
        if payload.credentials is not None:
            row.encrypted_credentials = encrypt_credential(
                json.dumps(payload.credentials.model_dump(), separators=(",", ":"))
            )
        if environment_changed or credentials_changed:
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
        result = test_connection(row)
    except ExperianConfigurationError as error:
        row.last_test_status = "configuration_error"
        row.last_tested_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=409, detail=str(error)) from error
    except ExperianRequestError as error:
        row.last_test_status = error.code
        row.last_tested_at = datetime.now(timezone.utc)
        db.commit()
        raise HTTPException(status_code=502, detail=str(error)) from error

    row.last_test_status = "connected"
    row.last_tested_at = datetime.now(timezone.utc)
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
