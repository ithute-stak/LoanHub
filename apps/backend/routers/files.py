from datetime import datetime, timedelta, timezone
from io import BytesIO
import hashlib
import secrets
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, LENDING_ROLES, TenantContext, get_user_context
from database.models.borrower import Borrower
from database.models.company_client import CompanyBorrowerAccount
from database.models.chat import ChatMessage, ChatMessageAttachment, ChatParticipant
from database.models.file_management import ManagedFile
from database.models.file_sharing import CompanySocialShareSettings, ExternalFileShare
from database.schemas.file_management import ManagedFileListRead, ManagedFileRead
from database.schemas.file_sharing import ExternalFileShareCreate, ExternalFileShareRead
from database.session import get_db
from services.file_service import can_access_file, read_file_bytes, save_upload


router = APIRouter(prefix='/files', tags=['File Management'])


BORROWER_EVIDENCE_CATEGORIES = {
    "borrower_identity",
    "borrower_proof_of_address",
    "borrower_payslip",
    "borrower_bank_statement",
    "borrower_employment",
    "borrower_existing_debt",
    "borrower_business",
    "borrower_other",
}


def _external_share_read(row: ExternalFileShare, share_url: str | None = None) -> ExternalFileShareRead:
    return ExternalFileShareRead(
        id=row.id,
        file_id=row.file_id,
        company_id=row.company_id,
        created_by_user_id=row.created_by_user_id,
        label=row.label,
        share_url=share_url,
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        access_count=row.access_count or 0,
        allow_download=row.allow_download,
        created_at=row.created_at,
    )


def _external_settings(db: Session, company_id) -> CompanySocialShareSettings | None:
    if not company_id:
        return None
    return (
        db.query(CompanySocialShareSettings)
        .filter(CompanySocialShareSettings.company_id == company_id)
        .first()
    )


@router.get('', response_model=ManagedFileListRead)
def list_files(
    search: str | None = None,
    category: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    query = db.query(ManagedFile).filter(ManagedFile.is_deleted.is_(False))
    if not context.is_platform_admin:
        shared_chat_file_ids = (
            db.query(ChatMessageAttachment.file_id)
            .join(ChatMessage, ChatMessage.id == ChatMessageAttachment.message_id)
            .join(ChatParticipant, ChatParticipant.conversation_id == ChatMessage.conversation_id)
            .filter(
                ChatParticipant.user_id == context.user.id,
                ChatParticipant.is_active.is_(True),
            )
        )
        conditions = [
            ManagedFile.owner_user_id == context.user.id,
            ManagedFile.id.in_(shared_chat_file_ids),
            # Candidate shared assessment files are narrowed by can_access_file
            # below using borrower ownership, consent and lender relationship.
            ManagedFile.linked_entity_type == "borrower_evaluation",
        ]
        if context.company_id:
            conditions.append(ManagedFile.company_id == context.company_id)
        query = query.filter(or_(*conditions))
    if category:
        query = query.filter(ManagedFile.category == category)
    if search:
        token = f'%{search.strip()}%'
        query = query.filter(or_(
            ManagedFile.original_name.ilike(token),
            ManagedFile.reference.ilike(token),
            ManagedFile.description.ilike(token),
        ))

    candidates = query.order_by(ManagedFile.created_at.desc()).limit(2500).all()
    visible = [item for item in candidates if can_access_file(db, context, item)]
    return ManagedFileListRead(
        items=visible[skip: skip + limit],
        total=len(visible),
    )


@router.post('/upload', response_model=ManagedFileRead, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    category: str = Form('general'),
    visibility: str = Form('private'),
    description: str | None = Form(None),
    linked_entity_type: str | None = Form(None),
    linked_entity_id: str | None = Form(None),
    is_confidential: bool = Form(False),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    if visibility not in {'private', 'company', 'branch', 'conversation', 'platform'}:
        raise HTTPException(status_code=400, detail='Invalid file visibility')
    if visibility == 'platform' and not context.is_platform_admin:
        raise HTTPException(status_code=403, detail='Platform file visibility requires platform-owner access')
    if visibility == 'conversation':
        raise HTTPException(status_code=400, detail='Conversation files must be uploaded from the chat module')

    if linked_entity_type == "borrower_evaluation":
        try:
            borrower_id = UUID(linked_entity_id or "")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid borrower profile reference") from exc
        borrower = db.query(Borrower).filter(Borrower.id == borrower_id).first()
        borrower_owned = bool(
            borrower and borrower.user_id == context.user.id
        )
        company_concerned = bool(
            borrower
            and context.company_id
            and context.staff
            and context.staff.role in LENDING_ROLES
            and db.query(CompanyBorrowerAccount.id)
            .filter(
                CompanyBorrowerAccount.company_id == context.company_id,
                CompanyBorrowerAccount.borrower_id == borrower_id,
            )
            .first()
        )
        if not borrower_owned and not company_concerned:
            raise HTTPException(
                status_code=403,
                detail="Borrower evidence requires the borrower or a concerned lending company",
            )
        if category not in BORROWER_EVIDENCE_CATEGORIES:
            raise HTTPException(status_code=400, detail="Invalid borrower evidence category")
        visibility = "private"
        is_confidential = True

    record = await save_upload(
        db,
        file,
        context,
        category=category,
        visibility=visibility,
        description=description,
        linked_entity_type=linked_entity_type,
        linked_entity_id=linked_entity_id,
        is_confidential=is_confidential,
    )
    db.commit()
    db.refresh(record)
    return record


@router.post('/{file_id}/external-shares', response_model=ExternalFileShareRead, status_code=status.HTTP_201_CREATED)
def create_external_file_share(
    file_id: UUID,
    payload: ExternalFileShareCreate,
    request: Request,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    record = db.query(ManagedFile).filter(
        ManagedFile.id == file_id,
        ManagedFile.is_deleted.is_(False),
    ).first()
    if not record or not can_access_file(db, context, record):
        raise HTTPException(status_code=404, detail='File not found')
    if record.company_id and not context.is_platform_admin and context.company_id != record.company_id:
        raise HTTPException(status_code=403, detail='Only users in the owning company can create an external link')
    if not record.company_id and not context.is_platform_admin and record.owner_user_id != context.user.id:
        raise HTTPException(status_code=403, detail='You cannot create an external link for this file')
    if record.is_confidential:
        raise HTTPException(status_code=409, detail='Confidential files cannot be shared externally')
    if record.scan_status == 'quarantined':
        raise HTTPException(status_code=409, detail='Quarantined files cannot be shared')

    settings = _external_settings(db, record.company_id)
    if record.company_id and (not settings or not settings.external_sharing_enabled):
        raise HTTPException(
            status_code=403,
            detail='External sharing is disabled in company settings',
        )

    hours = payload.expires_in_hours or (settings.default_expiry_hours if settings else 24)
    hours = max(1, min(int(hours), 168))
    raw_token = secrets.token_urlsafe(36)
    token_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
    row = ExternalFileShare(
        file_id=record.id,
        company_id=record.company_id,
        created_by_user_id=context.user.id,
        token_hash=token_hash,
        label=payload.label,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=hours),
        allow_download=payload.allow_download,
        access_count=0,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    share_url = str(request.url_for('download_public_file_share', token=raw_token))
    return _external_share_read(row, share_url)


@router.get('/{file_id}/external-shares', response_model=list[ExternalFileShareRead])
def list_external_file_shares(
    file_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    record = db.query(ManagedFile).filter(
        ManagedFile.id == file_id,
        ManagedFile.is_deleted.is_(False),
    ).first()
    if not record or not can_access_file(db, context, record):
        raise HTTPException(status_code=404, detail='File not found')
    if record.company_id and not context.is_platform_admin and context.company_id != record.company_id:
        raise HTTPException(status_code=403, detail='External link history is available only to the owning company')
    rows = (
        db.query(ExternalFileShare)
        .filter(ExternalFileShare.file_id == file_id)
        .order_by(ExternalFileShare.created_at.desc())
        .all()
    )
    return [_external_share_read(row) for row in rows]


@router.delete('/{file_id}/external-shares/{share_id}', status_code=status.HTTP_204_NO_CONTENT)
def revoke_external_file_share(
    file_id: UUID,
    share_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    record = db.query(ManagedFile).filter(
        ManagedFile.id == file_id,
        ManagedFile.is_deleted.is_(False),
    ).first()
    if not record or not can_access_file(db, context, record):
        raise HTTPException(status_code=404, detail='File not found')
    if record.company_id and not context.is_platform_admin and context.company_id != record.company_id:
        raise HTTPException(status_code=403, detail='Only the owning company can revoke an external link')
    row = db.query(ExternalFileShare).filter(
        ExternalFileShare.id == share_id,
        ExternalFileShare.file_id == file_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail='Share link not found')
    if not context.is_platform_admin and row.created_by_user_id != context.user.id:
        is_company_manager = bool(
            context.staff
            and context.staff.role in COMPANY_MANAGEMENT_ROLES
            and context.company_id == record.company_id
        )
        if not is_company_manager:
            raise HTTPException(status_code=403, detail='Only the creator or company management can revoke this link')
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/{file_id}', response_model=ManagedFileRead)
def get_file(
    file_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    record = db.query(ManagedFile).filter(
        ManagedFile.id == file_id,
        ManagedFile.is_deleted.is_(False),
    ).first()
    if not record or not can_access_file(db, context, record):
        raise HTTPException(status_code=404, detail='File not found')
    return record


@router.get('/{file_id}/download')
def download_file(
    file_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    record = db.query(ManagedFile).filter(
        ManagedFile.id == file_id,
        ManagedFile.is_deleted.is_(False),
    ).first()
    if not record or not can_access_file(db, context, record):
        raise HTTPException(status_code=404, detail='File not found')

    content = read_file_bytes(record)
    encoded_name = quote(record.original_name, safe='')
    headers = {
        'Content-Disposition': (
            f"attachment; filename=\"download\"; filename*=UTF-8''{encoded_name}"
        ),
        'Content-Length': str(len(content)),
        'Cache-Control': 'private, no-store',
        'X-Content-Type-Options': 'nosniff',
        'X-File-Reference': record.reference,
    }
    return StreamingResponse(
        BytesIO(content),
        media_type=record.mime_type,
        headers=headers,
    )


@router.delete('/{file_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    record = db.query(ManagedFile).filter(
        ManagedFile.id == file_id,
        ManagedFile.is_deleted.is_(False),
    ).first()
    if not record or not can_access_file(db, context, record):
        raise HTTPException(status_code=404, detail='File not found')
    is_company_manager = bool(
        context.staff
        and context.staff.role in COMPANY_MANAGEMENT_ROLES
        and context.company_id == record.company_id
    )
    if (
        not context.is_platform_admin
        and record.owner_user_id != context.user.id
        and not is_company_manager
    ):
        raise HTTPException(
            status_code=403,
            detail='Only the uploader or company management can remove this file',
        )
    record.is_deleted = True
    record.deleted_at = datetime.utcnow()
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
