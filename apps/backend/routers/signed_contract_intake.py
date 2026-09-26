from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    LENDING_ROLES,
    TenantContext,
    get_tenant_context,
    require_tenant_roles,
)
from database.models.company_client import CompanyBorrowerAccount
from database.models.file_management import ManagedFile
from database.session import get_db
from services.file_service import store_bytes
from services.signed_contract_intake import (
    CLIENT_FILE_LINK_TYPE,
    MAX_BATCH_FILES,
    SIGNED_CONTRACT_CATEGORY,
    SIGNED_CONTRACT_REVIEW_CATEGORY,
    checksum,
    extract_contract_text,
    filed_description,
    find_existing_intake_file,
    load_client_identities,
    match_signed_contract,
    read_contract_upload,
    review_description,
)


router = APIRouter(prefix="/signed-contracts", tags=["Signed Contract Intake"])


class SignedContractIntakeResult(BaseModel):
    file_id: UUID | None = None
    original_name: str
    status: Literal["filed", "review", "duplicate", "rejected"]
    client_account_id: UUID | None = None
    client_name: str | None = None
    evidence_types: list[str] = []
    extraction_method: str | None = None
    detail: str


class SignedContractReviewItem(BaseModel):
    file_id: UUID
    reference: str
    original_name: str
    size_bytes: int
    mime_type: str
    description: str | None = None
    uploaded_at: datetime


class SignedContractManualAssignment(BaseModel):
    client_account_id: UUID


class SignedContractAssignmentResult(BaseModel):
    file_id: UUID
    client_account_id: UUID
    client_name: str
    status: Literal["filed"] = "filed"


def _require_company_lending_context(context: TenantContext) -> None:
    require_tenant_roles(context, LENDING_ROLES)
    if not context.company_id:
        raise HTTPException(status_code=403, detail="A company context is required")


def _looks_like_scan(content: bytes) -> bool:
    head = content[:16]
    return bool(
        head.startswith(b"%PDF-")
        or head.startswith(b"\xff\xd8\xff")
        or head.startswith(b"\x89PNG\r\n\x1a\n")
        or (len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP")
    )


def _branch_filter(query, context: TenantContext):
    if (
        context.staff
        and context.staff.role not in COMPANY_MANAGEMENT_ROLES
        and context.branch_id is not None
    ):
        query = query.filter(ManagedFile.branch_id == context.branch_id)
    return query


@router.post("/intake", response_model=list[SignedContractIntakeResult])
async def intake_signed_contracts(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    _require_company_lending_context(context)
    if not files:
        raise HTTPException(status_code=400, detail="Choose at least one signed contract")
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Upload at most {MAX_BATCH_FILES} signed contracts at a time",
        )

    results: list[SignedContractIntakeResult] = []
    identities = load_client_identities(db, context)

    for upload in files:
        original_name = upload.filename or "signed-contract"
        try:
            content, original_name, declared_mime = await read_contract_upload(upload)
            if not _looks_like_scan(content):
                results.append(SignedContractIntakeResult(
                    original_name=original_name,
                    status="rejected",
                    detail="Signed contract intake accepts PDF, JPEG, PNG or WebP scans only",
                ))
                continue

            digest = checksum(content)
            existing = find_existing_intake_file(db, context.company_id, digest)
            if existing:
                account_id = None
                client_name = None
                if existing.linked_entity_type == CLIENT_FILE_LINK_TYPE and existing.linked_entity_id:
                    try:
                        account_id = UUID(existing.linked_entity_id)
                    except ValueError:
                        account_id = None
                    identity = identities.get(account_id)
                    client_name = identity.display_name if identity else None
                results.append(SignedContractIntakeResult(
                    file_id=existing.id,
                    original_name=original_name,
                    status="duplicate",
                    client_account_id=account_id,
                    client_name=client_name,
                    detail="This exact signed contract is already stored in LoanHub",
                ))
                continue

            # Store and malware-scan the original bytes before any PDF parsing or OCR.
            record = store_bytes(
                db,
                content=content,
                original_name=original_name,
                mime_type=declared_mime,
                owner_user_id=context.user.id,
                company_id=context.company_id,
                branch_id=context.branch_id,
                category=SIGNED_CONTRACT_REVIEW_CATEGORY,
                visibility="private",
                description="Signed Contracts · Reading contract for client identification",
                linked_entity_type="signed_contract_intake",
                linked_entity_id=None,
                is_confidential=True,
            )

            extracted_text, extraction_method = extract_contract_text(content, record.mime_type)
            try:
                match = match_signed_contract(db, context, extracted_text)
            except Exception:
                # The original scan is already safely managed. A matcher failure must
                # never cause an evidentiary document to be discarded or misfiled.
                match = None

            if match and match.status == "filed" and match.account_id:
                record.category = SIGNED_CONTRACT_CATEGORY
                record.linked_entity_type = CLIENT_FILE_LINK_TYPE
                record.linked_entity_id = str(match.account_id)
                record.branch_id = match.branch_id
                record.description = filed_description(extraction_method, match.evidence_types)
                db.commit()
                db.refresh(record)
                results.append(SignedContractIntakeResult(
                    file_id=record.id,
                    original_name=record.original_name,
                    status="filed",
                    client_account_id=match.account_id,
                    client_name=match.client_name,
                    evidence_types=match.evidence_types,
                    extraction_method=extraction_method,
                    detail="Filed under the client's Signed Contracts documents",
                ))
                continue

            reason = match.reason if match else "Automatic identification could not be completed"
            evidence = match.evidence_types if match else []
            record.category = SIGNED_CONTRACT_REVIEW_CATEGORY
            record.linked_entity_type = "signed_contract_intake"
            record.linked_entity_id = None
            record.description = review_description(reason, extraction_method)
            db.commit()
            db.refresh(record)
            results.append(SignedContractIntakeResult(
                file_id=record.id,
                original_name=record.original_name,
                status="review",
                evidence_types=evidence,
                extraction_method=extraction_method,
                detail=reason,
            ))
        except HTTPException as exc:
            db.rollback()
            results.append(SignedContractIntakeResult(
                original_name=original_name,
                status="rejected",
                detail=str(exc.detail),
            ))
        except Exception:
            db.rollback()
            results.append(SignedContractIntakeResult(
                original_name=original_name,
                status="rejected",
                detail="LoanHub could not safely process this file",
            ))

    return results


@router.get("/review", response_model=list[SignedContractReviewItem])
def list_signed_contract_review_queue(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    _require_company_lending_context(context)
    query = db.query(ManagedFile).filter(
        ManagedFile.company_id == context.company_id,
        ManagedFile.category == SIGNED_CONTRACT_REVIEW_CATEGORY,
        ManagedFile.is_deleted.is_(False),
    )
    query = _branch_filter(query, context)
    rows = query.order_by(ManagedFile.created_at.desc()).limit(500).all()
    return [
        SignedContractReviewItem(
            file_id=row.id,
            reference=row.reference,
            original_name=row.original_name,
            size_bytes=row.size_bytes,
            mime_type=row.mime_type,
            description=row.description,
            uploaded_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/review/{file_id}/assign", response_model=SignedContractAssignmentResult)
def assign_reviewed_signed_contract(
    file_id: UUID,
    payload: SignedContractManualAssignment,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_tenant_context),
):
    _require_company_lending_context(context)
    record_query = db.query(ManagedFile).filter(
        ManagedFile.id == file_id,
        ManagedFile.company_id == context.company_id,
        ManagedFile.category == SIGNED_CONTRACT_REVIEW_CATEGORY,
        ManagedFile.is_deleted.is_(False),
    )
    record_query = _branch_filter(record_query, context)
    record = record_query.first()
    if not record:
        raise HTTPException(status_code=404, detail="Signed contract review item not found")

    account_query = db.query(CompanyBorrowerAccount).filter(
        CompanyBorrowerAccount.id == payload.client_account_id,
        CompanyBorrowerAccount.company_id == context.company_id,
    )
    if (
        context.staff
        and context.staff.role not in COMPANY_MANAGEMENT_ROLES
        and context.branch_id is not None
    ):
        account_query = account_query.filter(CompanyBorrowerAccount.branch_id == context.branch_id)
    account = account_query.first()
    if not account:
        raise HTTPException(status_code=404, detail="Client account not found in your company scope")

    identity = load_client_identities(db, context).get(account.id)
    client_name = identity.display_name if identity else account.account_reference
    record.category = SIGNED_CONTRACT_CATEGORY
    record.linked_entity_type = CLIENT_FILE_LINK_TYPE
    record.linked_entity_id = str(account.id)
    record.branch_id = account.branch_id
    record.description = "Signed Contracts · Manually verified and filed from global intake"
    db.commit()
    db.refresh(record)

    return SignedContractAssignmentResult(
        file_id=record.id,
        client_account_id=account.id,
        client_name=client_name,
    )
