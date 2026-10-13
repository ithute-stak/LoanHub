from __future__ import annotations

import re
from datetime import datetime, timezone
from io import BytesIO
from fastapi.responses import StreamingResponse
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.access_control import FINANCE_ROLES, COMPANY_MANAGEMENT_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.employer_group import EmployerGroup
from database.models.legacy_bank_deduction import LegacyBankDeduction
from database.models.user import User
from database.models.person import Person
from database.session import get_db
from services.credential_service import encrypt_credential, decrypt_credential
from services.bank_submission_export import build_bank_submission_zip
from services.legacy_bank_routing import resolve_legacy_bank
from services.legacy_bank_import import parse_legacy_csv

router = APIRouter(prefix="/legacy-bank-deductions", tags=["Legacy Bank Deductions"])


class LegacyCreate(BaseModel):
    work_group_id: UUID
    client_name: str = Field(min_length=1, max_length=120)
    account_number: str = Field(min_length=6, max_length=20)
    branch_code: str = Field(default="", max_length=6)
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=15)

    @field_validator("account_number", "branch_code")
    @classmethod
    def digits_only(cls, value: str) -> str:
        if value and not re.fullmatch(r"[0-9]+", value):
            raise ValueError("Only digits are allowed")
        return value


def _group_kind(group: EmployerGroup) -> str | None:
    code = str(group.code or "").upper().replace("/", "").replace("-", "").replace(" ", "")
    name = str(group.name or "").upper().replace("/", "").replace("-", "").replace(" ", "")
    for value in (code, name):
        if value in {"CIVIL", "CIV"}:
            return "CIVIL"
        if value in {"FORCE", "LDF"}:
            return "FORCE"
        if value in {"SE", "SELFEMPLOYED"}:
            return "S/E"
    return None


def _authorized(context: TenantContext) -> None:
    require_tenant_roles(context, FINANCE_ROLES | COMPANY_MANAGEMENT_ROLES)
    if context.company_id is None:
        raise HTTPException(403, "A company must be selected")


@router.get("/work-groups")
def work_groups(context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    rows = db.query(EmployerGroup).filter(EmployerGroup.is_active.is_(True)).order_by(EmployerGroup.name).all()
    rows = [g for g in rows if _group_kind(g) is not None]
    return [{"id": str(row.id), "code": row.code, "name": row.name} for row in rows]


@router.get("/")
def list_legacy(context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    rows = (
        db.query(LegacyBankDeduction, EmployerGroup)
        .join(EmployerGroup, LegacyBankDeduction.work_group_id == EmployerGroup.id)
        .filter(LegacyBankDeduction.company_id == context.company_id,
        LegacyBankDeduction.deleted_at.is_(None))
        .order_by(LegacyBankDeduction.created_at.desc())
        .limit(1000).all()
    )
    creator_ids = {row.created_by for row, _ in rows if row.created_by}
    creators = db.query(User.id, User.email, User.phone, Person.first_name, Person.last_name).outerjoin(Person, Person.user_id == User.id).filter(User.id.in_(creator_ids)).all() if creator_ids else []
    creator_names = {str(user_id): (" ".join(filter(None, (first_name, last_name))).strip() or email or phone or "Unknown user") for user_id, email, phone, first_name, last_name in creators}
    return [{
        "id": str(row.id), "work_group_id": str(group.id), "work_group": group.name,
        "client_name": row.client_name, "account_last4": row.account_last4,
        "masked_account": "****" + row.account_last4, "branch_code": row.branch_code or (resolve_legacy_bank(decrypt_credential(row.account_number_encrypted)) or ("", ""))[1],
        "amount": str(row.amount), "created_at": row.created_at.isoformat() if row.created_at else None,
        "created_by_name": creator_names.get(str(row.created_by), "Not recorded"),
    } for row, group in rows]


@router.post("/", status_code=201)
def create_legacy(payload: LegacyCreate, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    group = db.query(EmployerGroup).filter(
        EmployerGroup.id == payload.work_group_id, EmployerGroup.is_active.is_(True)
    ).first()
    if group is None or _group_kind(group) is None:
        raise HTTPException(422, "Select CIVIL, FORCE or S/E work group")
    routing = resolve_legacy_bank(payload.account_number)
    record = LegacyBankDeduction(
        company_id=context.company_id, work_group_id=group.id,
        created_by=str(context.user.id), client_name=payload.client_name.strip(),
        account_number_encrypted=encrypt_credential(payload.account_number),
        account_last4=payload.account_number[-4:],
        branch_code=payload.branch_code.zfill(6) if payload.branch_code else (routing[1] if routing else ""), amount=payload.amount,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {"id": str(record.id), "saved": True}


@router.get("/export.zip")
def export_legacy_csv_zip(context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    """Export explicitly captured historical rows, never current live loans."""
    _authorized(context)
    rows = (
        db.query(LegacyBankDeduction, EmployerGroup)
        .join(EmployerGroup, LegacyBankDeduction.work_group_id == EmployerGroup.id)
        .filter(LegacyBankDeduction.company_id == context.company_id,
                LegacyBankDeduction.deleted_at.is_(None))
        .order_by(LegacyBankDeduction.created_at.asc(), LegacyBankDeduction.id.asc())
        .all()
    )
    data = []
    for entry, group in rows:
        number = decrypt_credential(entry.account_number_encrypted)
        # The institution-specific prefixes are supplied by the lender.
        routing = resolve_legacy_bank(number)
        bank = routing[0] if routing else ""
        branch = entry.branch_code or (routing[1] if routing else "")
        normalized = str(group.code or "").upper().replace(" ", "").replace("-", "").replace("/", "")
        name = str(group.name or "").upper()
        if normalized in {"FORCE", "LDF"} or "FORCE" in name:
            work_group = "FORCE"
        elif normalized in {"CIVIL", "CIV"} or "CIVIL" in name:
            work_group = "CIVIL"
        elif normalized in {"SE", "SELFEMPLOYED"} or "S/E" in name or "SELF EMPLOYED" in name:
            work_group = "S/E"
        else:
            work_group = str(group.code)
        data.append({
            "name": entry.client_name, "bank": bank,
            "account": number, "branch": branch,
            "group": work_group, "installment": entry.amount, "balance": entry.amount,
        })
    # The legacy dataset must never be silently confused with current loan exports.
    payload, summary = build_bank_submission_zip(data, lender_name=context.company.name)
    if summary["excluded"]:
        raise HTTPException(422, detail={
            "message": "Export blocked: correct invalid or unsupported legacy records first",
            "exportable_rows": summary["rows"],
            "excluded": summary["excluded"],
        })
    if not summary["rows"]:
        raise HTTPException(422, detail="No valid legacy records available for bank export")
    return StreamingResponse(
        BytesIO(payload), media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="legacy-bank-submissions.zip"',
            "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff",
            "X-Exported-Rows": str(summary["rows"]),
            "X-Excluded-Rows": str(sum(summary["excluded"].values())),
        },
    )


class LegacyUpdate(BaseModel):
    work_group_id: UUID
    client_name: str = Field(min_length=1, max_length=120)
    branch_code: str = Field(default="", max_length=6)
    amount: Decimal = Field(gt=0, decimal_places=2, max_digits=15)

    @field_validator("branch_code")
    @classmethod
    def valid_branch(cls, value: str) -> str:
        if value and not re.fullmatch(r"[0-9]+", value):
            raise ValueError("Branch code must contain digits only")
        return value


@router.patch("/{record_id}")
def update_legacy(
    record_id: UUID, payload: LegacyUpdate,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _authorized(context)
    record = db.query(LegacyBankDeduction).filter(
        LegacyBankDeduction.id == record_id,
        LegacyBankDeduction.company_id == context.company_id,
        LegacyBankDeduction.deleted_at.is_(None),
    ).first()
    if record is None:
        raise HTTPException(404, "Legacy record not found")
    group = db.query(EmployerGroup).filter(
        EmployerGroup.id == payload.work_group_id,
        EmployerGroup.is_active.is_(True),
    ).first()
    if group is None or _group_kind(group) is None:
        raise HTTPException(422, "Select CIVIL, FORCE or S/E work group")
    record.work_group_id = group.id
    record.client_name = payload.client_name.strip()
    routing = resolve_legacy_bank(decrypt_credential(record.account_number_encrypted))
    record.branch_code = payload.branch_code.zfill(6) if payload.branch_code else (routing[1] if routing else "")
    record.amount = payload.amount
    db.commit()
    return {"id": str(record.id), "saved": True}


@router.delete("/{record_id}", status_code=204)
def delete_legacy(
    record_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _authorized(context)
    record = db.query(LegacyBankDeduction).filter(
        LegacyBankDeduction.id == record_id,
        LegacyBankDeduction.company_id == context.company_id,
        LegacyBankDeduction.deleted_at.is_(None),
    ).first()
    if record is None:
        raise HTTPException(404, "Legacy record not found")
    record.deleted_at = datetime.now(timezone.utc)
    record.deleted_by_user_id = context.user.id
    db.commit()


@router.get("/deleted")
def list_deleted_legacy(
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _authorized(context)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    rows = db.query(LegacyBankDeduction).filter(
        LegacyBankDeduction.company_id == context.company_id,
        LegacyBankDeduction.deleted_at.is_not(None),
    ).order_by(LegacyBankDeduction.deleted_at.desc()).limit(100).all()
    return [{
        "id": str(row.id), "client_name": row.client_name,
        "account_last4": row.account_last4,
        "amount": str(row.amount),
        "deleted_at": row.deleted_at.isoformat(),
    } for row in rows]


@router.post("/{record_id}/restore")
def restore_deleted_legacy(
    record_id: UUID,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    _authorized(context)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    record = db.query(LegacyBankDeduction).filter(
        LegacyBankDeduction.id == record_id,
        LegacyBankDeduction.company_id == context.company_id,
        LegacyBankDeduction.deleted_at.is_not(None),
    ).first()
    if record is None:
        raise HTTPException(404, "Deleted legacy record not found")
    record.deleted_at = None
    record.deleted_by_user_id = None
    db.commit()
    return {"id": str(record.id), "restored": True}


@router.post("/import-csv")
async def import_legacy_csv(
    file: UploadFile = File(...),
    preview: bool = True,
    work_group_id: UUID | None = None,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    """Preview validation before a single atomic import; never post financial journals."""
    _authorized(context)
    if file.filename and not file.filename.lower().endswith(".csv"):
        raise HTTPException(422, "Select a CSV file")
    content = await file.read(2_000_001)
    if len(content) > 2_000_000:
        raise HTTPException(413, "CSV exceeds 2 MB")
    groups = db.query(EmployerGroup).filter(EmployerGroup.is_active.is_(True)).all()
    selected = next((g for g in groups if g.id == work_group_id), None) if work_group_id else None
    if work_group_id and (selected is None or _group_kind(selected) is None):
        raise HTTPException(422, "Select CIVIL, FORCE or S/E work group")
    known = {}
    for group in groups:
        if _group_kind(group) is None:
            continue
        known[group.name.strip().casefold()] = str(group.id)
        known[group.code.strip().casefold()] = str(group.id)
    try:
        valid, issues = parse_legacy_csv(content, known_groups=known, selected_group=selected.name if selected else None)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error

    # Avoid importing the same bank instruction twice, including duplicates within
    # one file. Decryption occurs only inside this restricted backend endpoint.
    existing = db.query(LegacyBankDeduction).filter(
        LegacyBankDeduction.company_id == context.company_id,
        LegacyBankDeduction.deleted_at.is_(None),
    ).all()
    fingerprints = {
        (str(row.work_group_id), decrypt_credential(row.account_number_encrypted),
         row.client_name.strip().casefold(), str(row.amount.quantize(Decimal("0.01"))))
        for row in existing
    }
    new_rows = []
    for row in valid:
        signature = (str(row["group_id"]), row["account"], row["name"].casefold(), str(row["amount"].quantize(Decimal("0.01"))))
        if signature in fingerprints:
            issues.append({"row": row["row"], "reason": "Duplicate deduction"})
        else:
            fingerprints.add(signature)
            new_rows.append(row)
    summary = {"valid": len(new_rows), "rejected": len(issues), "issues": issues[:200],
               "issues_truncated": len(issues) > 200}
    if preview:
        return {**summary, "saved": 0, "preview": True}
    if issues:
        raise HTTPException(422, detail={
            **summary, "message": "Resolve all CSV issues before importing",
        })
    if not new_rows:
        raise HTTPException(422, "No new valid deductions to import")
    for row in new_rows:
        db.add(LegacyBankDeduction(
            company_id=context.company_id, work_group_id=UUID(row["group_id"]),
            created_by=str(context.user.id), client_name=row["name"],
            account_number_encrypted=encrypt_credential(row["account"]),
            account_last4=row["account"][-4:],
            branch_code=row["branch"] or ((resolve_legacy_bank(row["account"]) or ("", ""))[1]), amount=row["amount"],
        ))
    db.commit()
    return {**summary, "saved": len(new_rows), "preview": False}
