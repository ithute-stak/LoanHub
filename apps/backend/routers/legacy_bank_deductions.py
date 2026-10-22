from __future__ import annotations

import re
import csv
from io import StringIO
from zipfile import ZipFile, ZIP_DEFLATED
from datetime import datetime, timezone
from io import BytesIO
from fastapi.responses import StreamingResponse
from decimal import Decimal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from core.access_control import FINANCE_ROLES, COMPANY_MANAGEMENT_ROLES, TenantContext, get_tenant_context, require_tenant_roles
from database.models.employer_group import EmployerGroup
from database.models.legacy_bank_deduction import LegacyBankDeduction
from database.models.company_operating_system import CompanyOperatingRecord
from database.models.legacy_employer import LegacyEmployer
from sqlalchemy.dialects.postgresql import insert as pg_insert
from database.models.user import User
from database.models.person import Person
from database.session import get_db
from services.credential_service import encrypt_credential, decrypt_credential
from services.bank_submission_export import build_bank_submission_zip
from services.legacy_bank_routing import resolve_legacy_bank, BANK_RULES
from services.legacy_bank_import import parse_legacy_csv, parse_legacy_spreadsheet
from services.legacy_employer_names import canonical_employer_name, employer_key

router = APIRouter(prefix="/legacy-bank-deductions", tags=["Legacy Bank Deductions"])


class LegacyCreate(BaseModel):
    work_group_id: UUID
    client_name: str = Field(min_length=1, max_length=120)
    employer: str = Field(min_length=1, max_length=120)
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


def _canonical_employer(db: Session, company_id: UUID, name: str) -> str:
    """Use the same employer spelling for all case/space variants."""
    cleaned = canonical_employer_name(name)
    match = db.query(LegacyEmployer.name).filter(
        LegacyEmployer.company_id == company_id,
        LegacyEmployer.normalized_name == cleaned.casefold(),
    ).first()
    if match:
        return match[0]
    # Older records may predate the directory table.
    previous = db.query(LegacyBankDeduction.employer).filter(
        LegacyBankDeduction.company_id == company_id,
        LegacyBankDeduction.employer.is_not(None),
    ).all()
    for (existing,) in previous:
        if existing and employer_key(existing) == employer_key(cleaned):
            return cleaned
    return cleaned


def _record_employers(db: Session, company_id: UUID, names: set[str]) -> None:
    """Company-scoped and idempotent; conflict-safe for concurrent imports."""
    canonical = {}
    for raw in names:
        value = canonical_employer_name(raw)
        if value and len(value) <= 120:
            canonical.setdefault(employer_key(value), value)
    if canonical:
        rows = [{"company_id": company_id, "name": name, "normalized_name": normalized}
                for normalized, name in canonical.items()]
        db.execute(pg_insert(LegacyEmployer).values(rows).on_conflict_do_nothing(
            constraint="uq_legacy_employers_company_normalized"))


@router.get("/employers")
def list_employers(context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    directory = db.query(LegacyEmployer.name).filter(LegacyEmployer.company_id == context.company_id).all()
    previous = db.query(LegacyBankDeduction.employer).filter(
        LegacyBankDeduction.company_id == context.company_id,
        LegacyBankDeduction.employer.is_not(None)).distinct().all()
    existing_groups = db.query(EmployerGroup).filter(EmployerGroup.is_active.is_(True)).all()
    # Collapse case/whitespace variants, using directory names first as canonical.
    canonical = {}
    for (name,) in directory:
        cleaned = canonical_employer_name(name)
        if cleaned:
            canonical.setdefault(employer_key(cleaned), cleaned)
    for (name,) in previous:
        cleaned = " ".join((name or "").split())
        if cleaned:
            canonical.setdefault(cleaned.casefold(), cleaned)
    # EmployerGroup is a legacy source of employer suggestions; omit work-group labels.
    for group in existing_groups:
        if _group_kind(group) is None:
            cleaned = " ".join((group.name or "").split())
            if cleaned:
                canonical.setdefault(cleaned.casefold(), cleaned)
    return sorted(canonical.values(), key=str.casefold)


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
    creator_ids = set()
    for row, _ in rows:
        if row.created_by:
            try:
                creator_ids.add(UUID(str(row.created_by)))
            except ValueError:
                pass
    creators = db.query(User.id, User.email, User.phone, Person.first_name, Person.last_name).outerjoin(Person, Person.user_id == User.id).filter(User.id.in_(creator_ids)).all() if creator_ids else []
    creator_names = {str(user_id): (" ".join(filter(None, (first_name, last_name))).strip() or email or phone or "Unknown user") for user_id, email, phone, first_name, last_name in creators}
    return [{
        "id": str(row.id), "work_group_id": str(group.id), "work_group": group.name,
        "client_name": row.client_name, "employer": row.employer or "", "account_last4": row.account_last4,
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
        employer=_canonical_employer(db, context.company_id, payload.employer),
        account_number_encrypted=encrypt_credential(payload.account_number),
        account_last4=payload.account_number[-4:],
        branch_code=payload.branch_code.zfill(6) if payload.branch_code else (routing[1] if routing else ""), amount=payload.amount,
    )
    db.add(record)
    _record_employers(db, context.company_id, {record.employer})
    db.commit()
    db.refresh(record)
    return {"id": str(record.id), "saved": True}


@router.get("/export.zip")
def export_legacy_csv_zip(include_custom: bool = False, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
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
    custom_groups = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.company_id == context.company_id,
        CompanyOperatingRecord.module == _CUSTOM_MODULE,
        CompanyOperatingRecord.record_type == _CUSTOM_TYPE,
        CompanyOperatingRecord.is_archived.is_(False),
    ).order_by(CompanyOperatingRecord.id).all() if include_custom else []
    configured = []
    for saved in custom_groups:
        config = saved.data or {}
        bank_branch = config.get("branch_code")
        work_id = config.get("work_group_id")
        employers = {employer_key(name) for name in config.get("employers", []) if isinstance(name, str)}
        if not bank_branch or not work_id or not employers:
            raise HTTPException(422, "A saved custom bank group is incomplete; edit or remove it before exporting")
        configured.append((saved, bank_branch, str(work_id), employers))
    data = []
    record_refs = []
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
        matched = [
            saved for saved, bank_branch, work_id, employers in configured
            if str(group.id) == work_id
            and bank_branch == branch
            and routing is not None and routing[1] == bank_branch
            and employer_key(entry.employer or "") in employers
        ]
        if len(matched) > 1:
            raise HTTPException(422, "Overlapping custom groups include the same deduction. Edit the groups before export.")
        record = {
            "name": entry.client_name, "bank": bank,
            "account": number, "branch": branch,
            "group": work_group, "installment": entry.amount, "balance": entry.amount,
            "employer": entry.employer,
        }
        if matched:
            # Stable ID prevents collisions between equal or renamed group names.
            # One instruction can be routed to exactly one custom CSV.
            record["custom_filename"] = "CUSTOM-" + re.sub(r"[^A-Za-z0-9_-]+", "-", matched[0].title).strip("-")[:45] + "-" + str(matched[0].id).replace("-", "")[:12] + ".csv"
        data.append(record)
        record_refs.append(entry)
    # The legacy dataset must never be silently confused with current loan exports.
    payload, summary = build_bank_submission_zip(data, lender_name=context.company.name, employer_grouping=True, include_spreadsheets=True)
    if summary["excluded"]:
        # Derive rejection details once for both the correction report and
        # the all-rejected error. Never add rejected instructions to the ZIP.
        invalid_records = [
            {
                "id": str(record_refs[item["index"]].id),
                "client_name": record_refs[item["index"]].client_name,
                "account_last4": record_refs[item["index"]].account_last4,
                "reason": item["reason"],
            }
            for item in summary["rejected_indices"]
        ]
        if not summary["rows"]:
            raise HTTPException(422, detail={
                "message": "No valid bank instructions; correct rejected records",
                "excluded": summary["excluded"],
                "invalid_records": [
                    {**item, "reasons": [item["reason"]]}
                    for item in invalid_records[:100]
                ],
            })
        report = StringIO(newline="")
        writer = csv.writer(report)
        writer.writerow(["Client", "Account last four", "Issue", "Status"])
        for item in invalid_records:
            writer.writerow([item["client_name"], item["account_last4"],
                             item["reason"].replace("_", " "), "NOT EXPORTED"])
        revised = BytesIO()
        with ZipFile(BytesIO(payload), "r") as source, ZipFile(revised, "w", compression=ZIP_DEFLATED) as target_zip:
            for member in source.infolist():
                target_zip.writestr(member, source.read(member.filename))
            target_zip.writestr("REJECTED-RECORDS-CORRECT-BEFORE-SUBMISSION.csv",
                                report.getvalue().encode("utf-8-sig"))
        payload = revised.getvalue()
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
    employer: str = Field(min_length=1, max_length=120)
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
    record.employer = _canonical_employer(db, context.company_id, payload.employer)
    _record_employers(db, context.company_id, {payload.employer})
    routing = resolve_legacy_bank(decrypt_credential(record.account_number_encrypted))
    record.branch_code = payload.branch_code.zfill(6) if payload.branch_code else (routing[1] if routing else "")
    record.amount = payload.amount
    db.commit()
    return {"id": str(record.id), "saved": True}


class BulkDeleteConfirm(BaseModel):
    confirmation: str
    expected_count: int = Field(ge=1)


@router.get("/bulk-delete/preview")
def preview_bulk_delete(context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    count = db.query(LegacyBankDeduction).filter(
        LegacyBankDeduction.company_id == context.company_id,
        LegacyBankDeduction.deleted_at.is_(None),
    ).count()
    return {"count": count, "company_id": str(context.company_id), "recoverable": True}


@router.post("/bulk-delete")
def bulk_delete_legacy(payload: BulkDeleteConfirm, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    """Soft-delete this company's historical deduction register only; never touch live loans."""
    _authorized(context)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    if payload.confirmation != "DELETE LEGACY RECORDS":
        raise HTTPException(422, "Type DELETE LEGACY RECORDS to confirm")
    rows = db.query(LegacyBankDeduction).filter(
        LegacyBankDeduction.company_id == context.company_id,
        LegacyBankDeduction.deleted_at.is_(None),
    ).with_for_update().all()
    if len(rows) != payload.expected_count:
        raise HTTPException(409, "The register changed. Refresh the preview and confirm again.")
    now = datetime.now(timezone.utc)
    for record in rows:
        record.deleted_at = now
        record.deleted_by_user_id = context.user.id
    db.commit()
    return {"deleted": len(rows), "recoverable": True}


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
    extension = (file.filename or "").lower()
    if not extension.endswith((".csv", ".xlsx")):
        raise HTTPException(422, "Select a CSV or XLSX file")
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
        parser = parse_legacy_spreadsheet if extension.endswith(".xlsx") else parse_legacy_csv
        valid, issues = parser(content, known_groups=known, selected_group=selected.name if selected else None)
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
         row.client_name.strip().casefold(), (row.employer or "").strip().casefold(), str(row.amount.quantize(Decimal("0.01"))))
        for row in existing
    }
    new_rows = []
    for row in valid:
        signature = (str(row["group_id"]), row["account"], row["name"].casefold(), row["employer"].casefold(), str(row["amount"].quantize(Decimal("0.01"))))
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
    canonical_import_employers = set()
    for row in new_rows:
        canonical_employer = _canonical_employer(db, context.company_id, row["employer"])
        canonical_import_employers.add(canonical_employer)
        db.add(LegacyBankDeduction(
            company_id=context.company_id, work_group_id=UUID(row["group_id"]),
            created_by=str(context.user.id), client_name=row["name"],
            employer=canonical_employer,
            account_number_encrypted=encrypt_credential(row["account"]),
            account_last4=row["account"][-4:],
            branch_code=row["branch"] or ((resolve_legacy_bank(row["account"]) or ("", ""))[1]), amount=row["amount"],
        ))
    _record_employers(db, context.company_id, canonical_import_employers)
    db.commit()
    return {**summary, "saved": len(new_rows), "preview": False}


@router.get("/combined-export.zip")
def export_combined_bank_zip(context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    """Export historical deductions and outstanding system loans in one validated ZIP."""
    from database.models.borrower import Borrower
    from database.models.client_loan_company import ClientCompanyLoan
    from database.models.enums import LoanStatus
    from database.models.origination import BorrowerBankAccount

    _authorized(context)
    legacy_rows = (
        db.query(LegacyBankDeduction, EmployerGroup)
        .join(EmployerGroup, LegacyBankDeduction.work_group_id == EmployerGroup.id)
        .filter(LegacyBankDeduction.company_id == context.company_id,
                LegacyBankDeduction.deleted_at.is_(None))
        .order_by(LegacyBankDeduction.created_at, LegacyBankDeduction.id).all()
    )
    records = []
    legacy_keys = set()
    for entry, group in legacy_rows:
        account = decrypt_credential(entry.account_number_encrypted)
        routing = resolve_legacy_bank(account)
        kind = _group_kind(group)
        records.append({
            "name": entry.client_name, "bank": routing[0] if routing else "",
            "account": account, "branch": entry.branch_code or (routing[1] if routing else ""),
            "employer": entry.employer, "group": kind or "", "installment": entry.amount, "balance": entry.amount,
        })
        legacy_keys.add((account, kind))

    loans = (
        db.query(ClientCompanyLoan, Person, BorrowerBankAccount, Borrower)
        .join(Borrower, Borrower.id == ClientCompanyLoan.borrower_id)
        .join(Person, Person.user_id == Borrower.user_id)
        .join(BorrowerBankAccount,
              (BorrowerBankAccount.borrower_id == Borrower.id)
              & (BorrowerBankAccount.company_id == context.company_id))
        .filter(ClientCompanyLoan.company_id == context.company_id,
                ClientCompanyLoan.balance > 0,
                ClientCompanyLoan.status.in_((LoanStatus.active, LoanStatus.defaulted)))
        .all()
    )
    chosen = {}
    for loan, person, bank, borrower in loans:
        if context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES and loan.branch_id != context.branch_id:
            continue
        previous = chosen.get(loan.id)
        if previous is None or (
            bool(bank.salary_account), bool(bank.verified_at)
        ) > (
            bool(previous[2].salary_account), bool(previous[2].verified_at)
        ):
            chosen[loan.id] = (loan, person, bank, borrower)
    overlap = []
    for loan, person, bank, borrower in chosen.values():
        account = decrypt_credential(bank.account_number_encrypted)
        group = str(loan.folio_group_code or "").upper().replace("/", "").replace("-", "").replace(" ", "")
        kind = "S/E" if group in {"SE", "SELFEMPLOYED"} else "FORCE" if group in {"FORCE", "LDF"} else "CIVIL" if group in {"CIVIL", "CIV"} else ""
        if (account, kind) in legacy_keys:
            overlap.append({"loan_id": str(loan.id), "account_last4": account[-4:], "work_group": kind})
            continue
        records.append({
            "name": " ".join(filter(None, (person.first_name, person.last_name))),
            "bank": bank.bank_name, "account": account, "branch": bank.branch_code,
            "employer": borrower.employer_name,
            "group": loan.folio_group_code, "installment": loan.installment_amount,
            "balance": loan.balance,
        })
    if overlap:
        raise HTTPException(422, detail={
            "message": "Combined export blocked: existing loans overlap legacy mandates. Reconcile before exporting.",
            "overlap_count": len(overlap), "overlaps": overlap[:25],
        })
    payload, summary = build_bank_submission_zip(records, lender_name=context.company.name, employer_grouping=True)
    if summary["excluded"]:
        raise HTTPException(422, detail={
            "message": "Combined bank export blocked: correct incomplete bank instructions first",
            "excluded": summary["excluded"], "exportable_rows": summary["rows"],
        })
    if not summary["rows"]:
        raise HTTPException(422, "No eligible legacy deductions or outstanding loans to export")
    return StreamingResponse(BytesIO(payload), media_type="application/zip", headers={
        "Content-Disposition": 'attachment; filename="loanhub-combined-bank-submissions.zip"',
        "Cache-Control": "no-store, private", "X-Content-Type-Options": "nosniff",
        "X-Exported-Rows": str(summary["rows"]),
    })


# Custom bank submissions store selection metadata only, never change source deductions.
_CUSTOM_MODULE = "legacy_bank_deductions"
_CUSTOM_TYPE = "custom_bank_group"


class CustomBankGroupInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    branch_code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")
    work_group_id: UUID
    employers: list[str] = Field(min_length=1, max_length=250)

    @field_validator("employers")
    @classmethod
    def validate_employers(cls, names: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(" ".join(n.split()) for n in names))
        if any(not n or len(n) > 120 for n in cleaned):
            raise ValueError("Every employer must have a valid name")
        return cleaned


def _custom_record(db: Session, company_id: UUID, record_id: UUID) -> CompanyOperatingRecord:
    record = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.id == record_id,
        CompanyOperatingRecord.company_id == company_id,
        CompanyOperatingRecord.module == _CUSTOM_MODULE,
        CompanyOperatingRecord.record_type == _CUSTOM_TYPE,
        CompanyOperatingRecord.is_archived.is_(False),
    ).first()
    if record is None:
        raise HTTPException(404, "Custom bank group not found")
    return record


def _custom_view(record: CompanyOperatingRecord) -> dict:
    data = record.data or {}
    return {
        "id": str(record.id), "name": record.title,
        "branch_code": data.get("branch_code", ""),
        "work_group_id": data.get("work_group_id", ""),
        "employers": data.get("employers", []),
    }


def _validate_custom_group(db: Session, company_id: UUID, payload: CustomBankGroupInput) -> None:
    if payload.branch_code not in {branch for _, branch, _ in BANK_RULES}:
        raise HTTPException(422, "Select a bank branch supported by configured LoanHub bank rules")
    group = db.query(EmployerGroup).filter(
        EmployerGroup.id == payload.work_group_id, EmployerGroup.is_active.is_(True)).first()
    if group is None or _group_kind(group) is None:
        raise HTTPException(422, "Select a valid CIVIL, FORCE or S/E work group")
    available = db.query(LegacyBankDeduction).filter(
        LegacyBankDeduction.company_id == company_id,
        LegacyBankDeduction.work_group_id == payload.work_group_id,
        LegacyBankDeduction.deleted_at.is_(None),
    ).all()
    valid = set()
    for entry in available:
        routing = resolve_legacy_bank(decrypt_credential(entry.account_number_encrypted))
        if routing and routing[1] == payload.branch_code and (entry.branch_code or routing[1]) == payload.branch_code:
            valid.add(employer_key(entry.employer or ""))
    if not all(employer_key(name) in valid for name in payload.employers):
        raise HTTPException(422, "Some selected employers have no active deductions in the selected bank and work group")


@router.get("/custom-groups")
def list_custom_groups(context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    records = db.query(CompanyOperatingRecord).filter(
        CompanyOperatingRecord.company_id == context.company_id,
        CompanyOperatingRecord.module == _CUSTOM_MODULE,
        CompanyOperatingRecord.record_type == _CUSTOM_TYPE,
        CompanyOperatingRecord.is_archived.is_(False),
    ).order_by(CompanyOperatingRecord.title).all()
    return [_custom_view(item) for item in records]


@router.post("/custom-groups", status_code=201)
def create_custom_group(payload: CustomBankGroupInput, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    _validate_custom_group(db, context.company_id, payload)
    record = CompanyOperatingRecord(
        company_id=context.company_id,
        module=_CUSTOM_MODULE, record_type=_CUSTOM_TYPE,
        reference="legacy-custom-" + uuid4().hex,
        title=payload.name.strip(), status="active",
        created_by_user_id=context.user.id,
        data={"branch_code": payload.branch_code, "work_group_id": str(payload.work_group_id), "employers": payload.employers},
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return _custom_view(record)


@router.put("/custom-groups/{record_id}")
def update_custom_group(record_id: UUID, payload: CustomBankGroupInput, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    record = _custom_record(db, context.company_id, record_id)
    _validate_custom_group(db, context.company_id, payload)
    record.title = payload.name.strip()
    record.data = {"branch_code": payload.branch_code, "work_group_id": str(payload.work_group_id), "employers": payload.employers}
    db.commit()
    return _custom_view(record)


@router.delete("/custom-groups/{record_id}", status_code=204)
def archive_custom_group(record_id: UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    record = _custom_record(db, context.company_id, record_id)
    record.is_archived = True
    db.commit()


@router.get("/custom-groups/{record_id}/export.zip")
def export_custom_group(record_id: UUID, context: TenantContext = Depends(get_tenant_context), db: Session = Depends(get_db)):
    _authorized(context)
    record = _custom_record(db, context.company_id, record_id)
    config = record.data or {}
    branch_code = config.get("branch_code")
    work_group_id = config.get("work_group_id")
    employers = {employer_key(name) for name in config.get("employers", [])}
    if not branch_code or not work_group_id or not employers:
        raise HTTPException(422, "Custom group is incomplete")
    group = db.query(EmployerGroup).filter(EmployerGroup.id == work_group_id).first()
    if not group or _group_kind(group) is None:
        raise HTTPException(422, "Custom group has an invalid work group")
    rows = db.query(LegacyBankDeduction).filter(
        LegacyBankDeduction.company_id == context.company_id,
        LegacyBankDeduction.work_group_id == group.id,
        LegacyBankDeduction.deleted_at.is_(None),
    ).order_by(LegacyBankDeduction.created_at, LegacyBankDeduction.id).all()
    data = []
    for entry in rows:
        if employer_key(entry.employer or "") not in employers:
            continue
        number = decrypt_credential(entry.account_number_encrypted)
        routing = resolve_legacy_bank(number)
        if not routing or routing[1] != branch_code or (entry.branch_code or routing[1]) != branch_code:
            continue
        data.append({
            "name": entry.client_name, "bank": routing[0],
            "account": number, "branch": branch_code,
            "group": _group_kind(group), "installment": entry.amount,
            "balance": entry.amount, "employer": entry.employer,
        })
    if not data:
        raise HTTPException(422, "No active matching deductions remain in this custom group")
    payload, summary = build_bank_submission_zip(data, lender_name=context.company.name, employer_grouping=True, include_spreadsheets=True)
    if summary["excluded"]:
        raise HTTPException(422, detail={
            "message": "Custom group export blocked: correct invalid bank deductions first",
            "exportable_rows": summary["rows"], "excluded": summary["excluded"],
        })
    if not summary["rows"]:
        raise HTTPException(422, "No valid records available for custom bank export")
    return StreamingResponse(BytesIO(payload), media_type="application/zip", headers={
        "Content-Disposition": 'attachment; filename="legacy-custom-bank-group.zip"',
        "Cache-Control": "no-store, private",
        "X-Content-Type-Options": "nosniff",
        "X-Exported-Rows": str(summary["rows"]),
    })
