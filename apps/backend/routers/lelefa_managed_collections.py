from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, object_session

import routers.lelefa_managed_collections_base as _base
from core.access_control import (
    COLLECTIONS_ROLES,
    COMPANY_MANAGEMENT_ROLES,
    TenantContext,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.origination import LoanContract, OriginationIntegrationConfiguration
from database.session import get_db
from routers.lelefa_managed_collections_base import *  # noqa: F401,F403
from services.lelefa_managed_collections import (
    INTEGRATION_TYPE,
    PROVIDER,
    calculate_collection_charge,
    normalize_collection_charge_policy,
    normalize_rules,
)


router = _base.router
_original_case_snapshot = _base._case_snapshot
_original_settings_payload = _base._settings_payload


class CollectionChargePolicyUpdate(BaseModel):
    enabled: bool = False
    charge_type: Literal["percentage", "fixed"] = "percentage"
    rate_percent: Decimal = Field(default=Decimal("10"), ge=0, le=100)
    fixed_amount: Decimal = Field(default=Decimal("0"), ge=0)
    basis: Literal["amount_referred", "overdue_amount"] = "amount_referred"
    minimum_days_past_due: int = Field(default=120, ge=1, le=3650)
    cap_amount: Decimal | None = Field(default=None, ge=0)
    clause_version: str = Field(default="COLLECT-001", min_length=1, max_length=80)


class LelefaSettingsUpdate(BaseModel):
    enabled: bool
    rules: _base.LelefaRulesUpdate = Field(default_factory=_base.LelefaRulesUpdate)
    collection_charge: CollectionChargePolicyUpdate = Field(
        default_factory=CollectionChargePolicyUpdate
    )


def _settings_payload(
    row: OriginationIntegrationConfiguration | None,
) -> dict[str, Any]:
    payload = _original_settings_payload(row)
    payload["collection_charge"] = normalize_collection_charge_policy(
        row.configuration if row else None
    )
    payload["collection_charge"]["legal_control"] = (
        "The borrower charge is assessed only from the immutable terms of a fully "
        "signed loan contract. Changing this setting does not alter existing contracts."
    )
    return payload


def _signed_contract_for_loan(
    db: Session,
    loan_id: UUID,
) -> LoanContract | None:
    return (
        db.query(LoanContract)
        .filter(LoanContract.loan_id == loan_id)
        .one_or_none()
    )


def _case_snapshot(
    case: Any,
    loan: Any,
    rules: dict[str, Any],
) -> dict[str, Any]:
    snapshot = _original_case_snapshot(case, loan, rules)
    db = object_session(loan) or object_session(case)
    contract = _signed_contract_for_loan(db, loan.id) if db is not None else None

    contract_signed = bool(
        contract
        and contract.status == "signed"
        and contract.borrower_signed_at
        and contract.company_signed_at
    )
    frozen_policy = (
        (contract.terms_snapshot or {}).get("collection_charge")
        if contract and isinstance(contract.terms_snapshot, dict)
        else None
    )
    assessment = calculate_collection_charge(
        frozen_policy,
        amount_referred=case.outstanding_balance or 0,
        overdue_amount=case.overdue_amount or 0,
        days_past_due=int(case.days_past_due or 0),
        contract_signed=contract_signed,
    )
    assessment["contract_number"] = contract.contract_number if contract else None
    assessment["contract_hash"] = contract.contract_hash if contract else None
    assessment["contract_status"] = contract.status if contract else "missing"
    assessment["borrower_signed_at"] = (
        contract.borrower_signed_at.isoformat()
        if contract and contract.borrower_signed_at
        else None
    )
    assessment["company_signed_at"] = (
        contract.company_signed_at.isoformat()
        if contract and contract.company_signed_at
        else None
    )
    assessment["source"] = "signed_contract_snapshot"

    charge_amount = Decimal(str(assessment["charge_amount"]))
    outstanding = Decimal(str(snapshot.get("outstanding_balance") or 0))
    assessment["debt_total_including_collection_charge"] = f"{outstanding + charge_amount:.2f}"
    snapshot["collection_charge"] = assessment
    return snapshot


def _remove_original_settings_routes() -> None:
    retained = []
    for route in router.routes:
        path = str(getattr(route, "path", ""))
        methods = set(getattr(route, "methods", set()) or set())
        if path == "/lelefa-collections/settings" and methods.intersection({"GET", "PUT"}):
            continue
        retained.append(route)
    router.routes[:] = retained


_remove_original_settings_routes()
_base._settings_payload = _settings_payload
_base._case_snapshot = _case_snapshot


@router.get("/settings")
def get_lelefa_collection_settings(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COLLECTIONS_ROLES)
    if not context.company_id:
        raise HTTPException(status_code=403, detail="An active company context is required")
    return _settings_payload(_base._configuration(db, context.company_id))


@router.put("/settings")
def update_lelefa_collection_settings(
    payload: LelefaSettingsUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if not context.company_id:
        raise HTTPException(status_code=403, detail="An active company context is required")

    row = _base._configuration(db, context.company_id)
    if row is None:
        row = OriginationIntegrationConfiguration(
            company_id=context.company_id,
            provider=PROVIDER,
            environment="production",
            configured_by_user_id=context.user.id,
        )
        db.add(row)

    current = dict(row.configuration or {})
    current.update({
        "integration_type": INTEGRATION_TYPE,
        "selection_mode": "rule_assisted_manual_approval",
        "rules": normalize_rules(payload.rules.model_dump()),
        "collection_charge": normalize_collection_charge_policy(
            {"collection_charge": payload.collection_charge.model_dump(mode="json")}
        ),
    })
    row.configuration = current
    row.is_enabled = payload.enabled
    row.configured_by_user_id = context.user.id
    db.commit()
    db.refresh(row)
    return _settings_payload(row)
