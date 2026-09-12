from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.access_control import require_platform_owner
from database.models.audit_log import AuditLog
from database.models.user import User
from database.schemas.lelefa_paygate import (
    LelefaPayGateConfigurationRead,
    LelefaPayGateConfigurationUpdate,
)
from database.session import get_db
from services.lelefa_paygate_config_service import (
    configuration_summary,
    get_configuration,
    synchronize_runtime_settings,
    update_configuration,
)


router = APIRouter(prefix="/lelefapaygate/admin", tags=["LelefaPayGate Admin"])


def _audit_view(summary: dict) -> dict:
    return {
        key: value
        for key, value in summary.items()
        if key not in {"api_key_hint", "updated_at"}
    }


@router.get("/configuration", response_model=LelefaPayGateConfigurationRead)
def read_configuration(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    try:
        return configuration_summary(get_configuration(db))
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="LelefaPayGate configuration storage is not ready. Run alembic upgrade head.",
        ) from error


@router.put("/configuration", response_model=LelefaPayGateConfigurationRead)
def save_configuration(
    payload: LelefaPayGateConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    try:
        existing = get_configuration(db)
        before = configuration_summary(existing)
        configuration = update_configuration(
            db,
            enabled=payload.enabled,
            base_url=payload.base_url,
            api_key=payload.api_key,
            webhook_secret=payload.webhook_secret,
            clear_api_key=payload.clear_api_key,
            clear_webhook_secret=payload.clear_webhook_secret,
            request_signing_enabled=payload.request_signing_enabled,
            timeout_seconds=payload.timeout_seconds,
            webhook_tolerance_seconds=payload.webhook_tolerance_seconds,
            collection_provider=payload.collection_provider,
            payout_provider=payload.payout_provider,
        )
        after = configuration_summary(configuration)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error)) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=503,
            detail="LelefaPayGate configuration storage is not ready. Run alembic upgrade head.",
        ) from error

    changed_fields = [
        field
        for field in (
            "enabled",
            "base_url",
            "api_key_configured",
            "webhook_secret_configured",
            "request_signing_enabled",
            "timeout_seconds",
            "webhook_tolerance_seconds",
            "collection_provider",
            "payout_provider",
        )
        if before.get(field) != after.get(field)
    ]
    if payload.api_key and "api_key_configured" not in changed_fields:
        changed_fields.append("api_key_rotated")
    if payload.webhook_secret and "webhook_secret_configured" not in changed_fields:
        changed_fields.append("webhook_secret_rotated")

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="lelefapaygate_configuration_updated",
            table_name="lelefapaygate_configurations",
            entity_type="lelefapaygate_configuration",
            record_id=configuration.id,
            description="The platform owner updated LoanHub's LelefaPayGate configuration.",
            actor_role=current_user.role.value,
            severity="warning" if payload.enabled != before.get("enabled") else "info",
            status="success",
            before_data=_audit_view(before),
            after_data=_audit_view(after),
            changed_fields=changed_fields,
            event_data={
                "source": "superadmin_lelefapaygate_configuration",
                "secrets_persisted_encrypted": True,
            },
        )
    )
    db.commit()
    db.refresh(configuration)
    synchronize_runtime_settings(db)
    return configuration_summary(configuration)
