from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    get_tenant_context,
    require_tenant_roles,
)
from database.config.config import settings
from database.models.cdas_booking import CdasBookingOpportunity
from database.session import get_db
from services.cdas_config_service import configuration_summary, get_configuration
from services.cdas_lifecycle_automation import (
    SETTLEMENT_REASON_CONSOLIDATION,
    SETTLEMENT_REASON_PAID_BY_EMPLOYEE,
)
from services.cdas_monthly_automation import (
    AUTOMATION_AUTHORIZATION_BASIS,
    AUTOMATION_SOURCE,
    WINDOW_END_DAY,
    WINDOW_HOUR,
    WINDOW_START_DAY,
    get_monthly_automation_configuration,
    update_monthly_automation_configuration,
)
from services.cdas_sub1000_auto_modification import AUTO_MODIFY_TARGET


router = APIRouter(prefix="/cdas/monthly-automation", tags=["CDAS Monthly Automation"])


class MonthlyAutomationConfigurationRequest(BaseModel):
    enabled: bool = True
    item_code: str = Field(min_length=1, max_length=100)
    loan_policy: int = Field(default=0, ge=0)


def _require_manager(context: TenantContext) -> None:
    if context.is_platform_admin or not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="A company-scoped management membership is required")
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)


def _configuration_payload(db: Session, context: TenantContext) -> dict[str, Any]:
    assert context.company_id is not None
    row = get_configuration(db, context.company_id)
    automation = get_monthly_automation_configuration(row)
    return {
        **automation,
        "timezone": settings.APP_TIMEZONE,
        "window_start_day": WINDOW_START_DAY,
        "window_end_day": WINDOW_END_DAY,
        "scheduled_time": f"{WINDOW_HOUR:02d}:00",
        "authorization_basis": AUTOMATION_AUTHORIZATION_BASIS,
        "auto_modify_below": float(AUTO_MODIFY_TARGET),
        "auto_modify_target": float(AUTO_MODIFY_TARGET),
        "automatic_status_reconciliation": True,
        "automatic_zero_balance_settlement": True,
        "automatic_settlement_reasons": {
            "paid_by_employee": SETTLEMENT_REASON_PAID_BY_EMPLOYEE,
            "consolidation": SETTLEMENT_REASON_CONSOLIDATION,
        },
        "cdas_integration": configuration_summary(row),
    }


@router.get("/configuration")
def get_automation_configuration(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_manager(context)
    return _configuration_payload(db, context)


@router.put("/configuration")
def put_automation_configuration(
    payload: MonthlyAutomationConfigurationRequest,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_manager(context)
    assert context.company_id is not None
    row = get_configuration(db, context.company_id)
    if row is None:
        raise HTTPException(status_code=409, detail="Configure the company CDAS integration before enabling automatic deductions")
    try:
        update_monthly_automation_configuration(
            db,
            row=row,
            enabled=payload.enabled,
            item_code=payload.item_code,
            loan_policy=payload.loan_policy,
            configured_by_user_id=context.user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _configuration_payload(db, context)


@router.get("/status")
def get_automation_status(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _require_manager(context)
    assert context.company_id is not None
    rows = (
        db.query(CdasBookingOpportunity)
        .filter(CdasBookingOpportunity.company_id == context.company_id)
        .order_by(CdasBookingOpportunity.id.desc())
        .limit(500)
        .all()
    )
    snapshots = [
        dict(row.analysis_snapshot or {})
        for row in rows
        if dict(row.analysis_snapshot or {}).get("source") == AUTOMATION_SOURCE
    ]
    latest = snapshots[0] if snapshots else None
    totals = {
        "runs": len(snapshots),
        "activated": sum(int(item.get("activated") or 0) for item in snapshots),
        "modified": sum(int(item.get("modified") or 0) for item in snapshots),
        "reconciled": sum(int(item.get("reconciled") or 0) for item in snapshots),
        "settled": sum(int(item.get("settled") or 0) for item in snapshots),
        "paid_settlements": sum(
            1
            for item in snapshots
            if int(item.get("settled") or 0) and int(item.get("settlement_reason") or 0) == SETTLEMENT_REASON_PAID_BY_EMPLOYEE
        ),
        "consolidation_settlements": sum(
            1
            for item in snapshots
            if int(item.get("settled") or 0) and int(item.get("settlement_reason") or 0) == SETTLEMENT_REASON_CONSOLIDATION
        ),
        "provider_reads": sum(int(item.get("provider_reads") or 0) for item in snapshots),
        "provider_writes": sum(int(item.get("provider_writes") or 0) for item in snapshots),
        "provider_missing": sum(
            1
            for item in snapshots
            if item.get("recommended_action") == "RECONCILIATION_REQUIRED_PROVIDER_RECORD_NOT_FOUND"
        ),
        "failed": sum(1 for item in snapshots if item.get("last_check_status") in {"failed", "degraded"}),
    }
    return {
        **_configuration_payload(db, context),
        "latest": latest,
        "totals": totals,
        "legacy_daily_0345_enabled": False,
    }
