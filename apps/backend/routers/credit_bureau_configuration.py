from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.origination import OriginationIntegrationConfiguration
from database.models.platform_credit_bureau import PlatformCreditBureauConfiguration
from database.schemas.credit_bureau import ExperianCompanySettingsUpdate, ExperianCompanyUsageConfiguration
from database.session import get_db


router = APIRouter(prefix="/credit-bureau", tags=["Credit Bureau Configuration"])


def _platform_row(db: Session) -> PlatformCreditBureauConfiguration | None:
    return (
        db.query(PlatformCreditBureauConfiguration)
        .filter(PlatformCreditBureauConfiguration.provider == "experian")
        .first()
    )


def _company_row(db: Session, company_id) -> OriginationIntegrationConfiguration | None:
    return (
        db.query(OriginationIntegrationConfiguration)
        .filter(
            OriginationIntegrationConfiguration.company_id == company_id,
            OriginationIntegrationConfiguration.provider == "experian",
        )
        .first()
    )


def _company_configuration(row: OriginationIntegrationConfiguration | None) -> dict:
    defaults = ExperianCompanyUsageConfiguration().model_dump()
    if row and isinstance(row.configuration, dict):
        for key in defaults:
            if key in row.configuration:
                defaults[key] = row.configuration[key]
    return defaults


def _platform_ready_for_company_use(
    platform: PlatformCreditBureauConfiguration | None,
    configuration: dict,
) -> bool:
    """Evaluate platform readiness without exposing private provider mapping to tenants."""
    return bool(
        platform
        and platform.is_enabled
        and platform.encrypted_credentials
        and platform.last_test_status == "connected"
        and str(configuration.get("bureau_endpoint_path") or "").strip()
        and configuration.get("request_template")
        and configuration.get("response_mapping")
    )


def company_experian_preview(
    db: Session,
    *,
    company_id,
) -> dict:
    company = _company_row(db, company_id)
    platform = _platform_row(db)
    platform_configuration = dict(platform.configuration or {}) if platform else {}
    platform_ready = _platform_ready_for_company_use(platform, platform_configuration)
    return {
        "provider": "experian",
        "scope": "company",
        "is_enabled": bool(company.is_enabled) if company else False,
        "configuration": _company_configuration(company),
        "platform": {
            "configured": bool(platform),
            "is_enabled": bool(platform.is_enabled) if platform else False,
            "environment": platform.environment if platform else None,
            "has_credentials": bool(platform and platform.encrypted_credentials),
            "last_test_status": platform.last_test_status if platform else None,
            "last_tested_at": platform.last_tested_at if platform else None,
            "ready_for_company_use": platform_ready,
            "product": platform_configuration.get("product"),
            "region": platform_configuration.get("region"),
        },
    }


@router.put("/experian/configuration")
def update_experian_configuration(
    payload: ExperianCompanySettingsUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    """Save company usage policy only; Experian secrets are Platform Owner data."""
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)

    if payload.is_enabled:
        preview = company_experian_preview(db, company_id=context.company_id)
        if not preview["platform"]["ready_for_company_use"]:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Experian cannot be enabled for this company until the Platform Owner "
                    "has completed and enabled the central Experian connection."
                ),
            )

    row = _company_row(db, context.company_id)
    if not row:
        row = OriginationIntegrationConfiguration(
            company_id=context.company_id,
            provider="experian",
            environment="platform",
        )
        db.add(row)

    row.environment = "platform"
    row.is_enabled = payload.is_enabled
    row.configuration = payload.configuration.model_dump()
    row.configured_by_user_id = context.user.id
    # Defence in depth: tenant Experian credentials were retired by migration,
    # and any stale value is cleared again whenever company policy is saved.
    row.encrypted_credentials = None
    row.last_test_status = None
    row.last_tested_at = None

    db.commit()
    db.refresh(row)
    return company_experian_preview(db, company_id=context.company_id)
