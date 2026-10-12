from __future__ import annotations

import re
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.access_control import FINANCE_ROLES, COMPANY_MANAGEMENT_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.employer_group import EmployerGroup
from database.models.legacy_bank_deduction import LegacyBankDeduction
from database.session import get_db
from services.credential_service import encrypt_credential

router = APIRouter(prefix="/legacy-bank-deductions", tags=["Legacy Bank Deductions"])


class LegacyCreate(BaseModel):
    work_group_id: UUID
    client_name: str = Field(min_length=1, max_length=120)
    account_number: str = Field(min_length=6, max_length=20)
    branch_code: str = Field(min_length=1, max_length=6)
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=15)

    @field_validator("account_number", "branch_code")
    @classmethod
    def digits_only(cls, value: str) -> str:
        if not re.fullmatch(r"[0-9]+", value):
            raise ValueError("Only digits are allowed")
        return value


def _authorized(context: TenantContext) -> None:
    require_tenant_roles(context, FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES)
    if context.company_id is None:
        raise HTTPException(403, "A company must be selected")


@router.get("/work-groups")
def work_groups(context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    rows = db.query(EmployerGroup).filter(EmployerGroup.is_active.is_(True)).order_by(EmployerGroup.name).all()
    return [{"id": str(row.id), "code": row.code, "name": row.name} for row in rows]


@router.get("/")
def list_legacy(context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    rows = (
        db.query(LegacyBankDeduction, EmployerGroup)
        .join(EmployerGroup, LegacyBankDeduction.work_group_id == EmployerGroup.id)
        .filter(LegacyBankDeduction.company_id == context.company_id)
        .order_by(LegacyBankDeduction.created_at.desc())
        .limit(1000).all()
    )
    return [{
        "id": str(row.id), "work_group_id": str(group.id), "work_group": group.name,
        "client_name": row.client_name, "account_last4": row.account_last4,
        "masked_account": "****" + row.account_last4, "branch_code": row.branch_code,
        "amount": str(row.amount), "created_at": row.created_at.isoformat() if row.created_at else None,
    } for row, group in rows]


@router.post("/", status_code=201)
def create_legacy(payload: LegacyCreate, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    group = db.query(EmployerGroup).filter(
        EmployerGroup.id == payload.work_group_id, EmployerGroup.is_active.is_(True)
    ).first()
    if group is None:
        raise HTTPException(422, "Select an active work group")
    record = LegacyBankDeduction(
        company_id=context.company_id, work_group_id=group.id,
        client_name=payload.client_name.strip(),
        account_number_encrypted=encrypt_credential(payload.account_number),
        account_last4=payload.account_number[-4:],
        branch_code=payload.branch_code.zfill(6), amount=payload.amount,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": str(record.id), "saved": True}
