from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import logging
import secrets
from io import BytesIO
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError, OperationalError, ProgrammingError
from sqlalchemy.orm import Session, joinedload

from core.access_control import TenantContext, get_user_context, is_platform_role
from database.models.company_staff import CompanyStaff
from database.models.enums import UserRole
from database.models.user import User
from database.models.workspace_document import (
    WorkspaceDocument,
    WorkspaceDocumentAsset,
    WorkspaceDocumentCollaborator,
    WorkspaceDocumentRevision,
    WorkspaceDocumentSignature,
)
from database.schemas.file_management import ManagedFileRead
from database.schemas.workspace_document import (
    WorkspaceDocumentAssetRead,
    WorkspaceDocumentCollaboratorCreate,
    WorkspaceDocumentCollaboratorRead,
    WorkspaceDocumentCreate,
    WorkspaceDocumentListRead,
    WorkspaceDocumentPublish,
    WorkspaceDocumentRead,
    WorkspaceDocumentSignatureCreate,
    WorkspaceDocumentSignatureRead,
    WorkspaceDocumentRevisionRead,
    WorkspaceDocumentUpdate,
)
from database.session import get_db
from database.config.config import settings
from routers.chat import allowed_directory_ids
from services.file_service import store_bytes
from services.document_branding_service import get_company_branding_logos
from services.client_document_template_service import (
    CLIENT_LETTER_TEMPLATE_KEYS,
    build_client_letter_context,
)
from services.workspace_document_service import (
    content_json_or_default,
    default_document_html,
    document_reference,
    export_docx,
    export_pdf,
    plain_text_from_html,
    sanitize_document_html,
    signature_field_count,
    signature_field_metadata,
    user_display_name,
)
from services.workspace_document_asset_service import (
    active_signatures,
    asset_image_bytes,
    canonical_document_hash,
    default_asset,
    extract_signature_image,
    image_sha256,
    normalize_logo_image,
    protect_asset_bytes,
    private_signature_asset_id,
    resolved_brand_asset,
    signature_asset_bytes_for_owner,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workspace-documents", tags=["Document Studio"])


def _base_query(db: Session):
    return db.query(WorkspaceDocument).options(
        joinedload(WorkspaceDocument.owner).joinedload(User.person),
        joinedload(WorkspaceDocument.company),
        joinedload(WorkspaceDocument.collaborators),
    )


def _collaboration(db: Session, document_id: UUID, user_id: UUID):
    return db.query(WorkspaceDocumentCollaborator).filter(
        WorkspaceDocumentCollaborator.document_id == document_id,
        WorkspaceDocumentCollaborator.user_id == user_id,
    ).first()


def _can_view(db: Session, context: TenantContext, document: WorkspaceDocument) -> bool:
    if document.owner_user_id == context.user.id:
        return True
    if _collaboration(db, document.id, context.user.id):
        return True
    if document.visibility == "company" and context.company_id and document.company_id == context.company_id:
        return True
    if document.visibility == "platform" and is_platform_role(context.user.role):
        return True
    return False


def _can_edit(db: Session, context: TenantContext, document: WorkspaceDocument) -> bool:
    if document.owner_user_id == context.user.id:
        return True
    collaborator = _collaboration(db, document.id, context.user.id)
    return bool(collaborator and collaborator.permission == "edit")


def _can_manage(context: TenantContext, document: WorkspaceDocument) -> bool:
    return bool(document.owner_user_id == context.user.id or context.is_platform_admin)


def _document_or_404(db: Session, context: TenantContext, document_id: UUID) -> WorkspaceDocument:
    document = _base_query(db).filter(
        WorkspaceDocument.id == document_id,
        WorkspaceDocument.is_deleted.is_(False),
    ).first()
    if not document or not _can_view(db, context, document):
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def _company_header(document: WorkspaceDocument) -> dict[str, str | None]:
    company = document.company
    if company is None:
        return {
            "name": settings.PRODUCT_NAME,
            "registration_number": None,
            "license_number": None,
            "phone": None,
            "email": None,
            "website": None,
            "address": None,
            "district": None,
        }
    return {
        "name": company.name,
        "registration_number": company.registration_number,
        "license_number": company.license_number,
        "phone": company.phone,
        "email": company.email,
        "website": company.website,
        "address": company.address,
        "district": company.district,
    }


def _read(db: Session, context: TenantContext, document: WorkspaceDocument) -> WorkspaceDocumentRead:
    brand_asset = resolved_brand_asset(db, document)
    applied_count = db.query(WorkspaceDocumentSignature.id).filter(
        WorkspaceDocumentSignature.document_id == document.id,
        WorkspaceDocumentSignature.revoked_at.is_(None),
    ).count()
    return WorkspaceDocumentRead(
        id=document.id,
        reference=document.reference,
        owner_user_id=document.owner_user_id,
        owner_display_name=user_display_name(document.owner),
        company_id=document.company_id,
        branch_id=document.branch_id,
        company_header=_company_header(document),
        title=document.title,
        template_key=document.template_key,
        content_json=document.content_json or {},
        content_html=document.content_html or "",
        plain_text=document.plain_text or "",
        visibility=document.visibility,
        status=document.status,
        version=document.version,
        page_size=document.page_size,
        orientation=document.orientation,
        margin_top_mm=document.margin_top_mm,
        margin_right_mm=document.margin_right_mm,
        margin_bottom_mm=document.margin_bottom_mm,
        margin_left_mm=document.margin_left_mm,
        style_key=document.style_key,
        default_font_family=document.default_font_family,
        default_font_size_pt=document.default_font_size_pt,
        default_line_height_percent=document.default_line_height_percent,
        include_brand_header=document.include_brand_header,
        include_footer=document.include_footer,
        is_confidential=document.is_confidential,
        brand_logo_asset_id=brand_asset.id if brand_asset else None,
        cover_page_enabled=bool(getattr(document, "cover_page_enabled", False)),
        cover_page=getattr(document, "cover_page", None) or {},
        address_blocks=getattr(document, "address_blocks", None) or [],
        can_edit=_can_edit(db, context, document),
        can_manage=_can_manage(context, document),
        collaborator_count=len(document.collaborators or []),
        signature_field_count=signature_field_count(document.content_html),
        applied_signature_count=applied_count,
        finalized_at=document.finalized_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )



def _asset_read(asset: WorkspaceDocumentAsset) -> WorkspaceDocumentAssetRead:
    return WorkspaceDocumentAssetRead(
        id=asset.id,
        kind=asset.kind,
        label=asset.label,
        original_filename=asset.original_filename,
        mime_type=asset.mime_type,
        width_px=asset.width_px,
        height_px=asset.height_px,
        is_default=asset.is_default,
        created_at=asset.created_at,
        updated_at=asset.updated_at,
    )


def _owned_asset_or_404(
    db: Session,
    context: TenantContext,
    asset_id: UUID,
    *,
    kind: str | None = None,
) -> WorkspaceDocumentAsset:
    query = db.query(WorkspaceDocumentAsset).filter(
        WorkspaceDocumentAsset.id == asset_id,
        WorkspaceDocumentAsset.owner_user_id == context.user.id,
        WorkspaceDocumentAsset.is_active.is_(True),
    )
    if kind:
        query = query.filter(WorkspaceDocumentAsset.kind == kind)
    asset = query.first()
    if not asset:
        raise HTTPException(status_code=404, detail="Document asset not found")
    return asset


def _request_digest(value: str | None) -> str | None:
    if not value:
        return None
    key = str(settings.SECRET_KEY).encode("utf-8")
    return hmac.new(key, value.encode("utf-8", errors="ignore"), hashlib.sha256).hexdigest()


def _signature_read(
    row: WorkspaceDocumentSignature,
    *,
    viewer_user_id: UUID,
) -> WorkspaceDocumentSignatureRead:
    return WorkspaceDocumentSignatureRead(
        id=row.id,
        field_id=row.field_id,
        field_type=row.field_type,
        signer_user_id=row.signer_user_id,
        signer_name=row.signer_name,
        method=row.method,
        # A stored-signature vault asset id is private. Document owners, company
        # admins, platform admins and collaborators receive the signature audit
        # metadata but never another user's reusable asset identifier.
        asset_id=private_signature_asset_id(row, viewer_user_id),
        signed_at=row.signed_at,
        document_version=row.document_version,
        document_hash=row.document_hash,
        verification_code=row.verification_code,
        revoked_at=row.revoked_at,
    )


def _validate_visibility(context: TenantContext, visibility: str) -> None:
    if visibility == "company" and not context.company_id:
        raise HTTPException(status_code=400, detail="Company visibility requires an active company")
    if visibility == "platform" and not is_platform_role(context.user.role):
        raise HTTPException(status_code=403, detail="Platform visibility requires a platform role")


def _revision(db: Session, document: WorkspaceDocument, user_id: UUID) -> None:
    exists = db.query(WorkspaceDocumentRevision.id).filter(
        WorkspaceDocumentRevision.document_id == document.id,
        WorkspaceDocumentRevision.version == document.version,
    ).first()
    if exists:
        return
    db.add(WorkspaceDocumentRevision(
        document_id=document.id,
        version=document.version,
        title=document.title,
        content_json=document.content_json,
        content_html=document.content_html,
        plain_text=document.plain_text,
        created_by_user_id=user_id,
    ))


def _invalidate_active_signatures(
    db: Session,
    document: WorkspaceDocument,
    *,
    user_id: UUID,
) -> int:
    """Revoke active signatures whenever the signed document is materially edited."""
    rows = db.query(WorkspaceDocumentSignature).filter(
        WorkspaceDocumentSignature.document_id == document.id,
        WorkspaceDocumentSignature.revoked_at.is_(None),
    ).all()
    if not rows:
        return 0
    now = datetime.now(timezone.utc)
    for row in rows:
        row.revoked_at = now
        row.revoked_by_user_id = user_id
    return len(rows)


def _is_workspace_schema_error(error: Exception) -> bool:
    """Return True when PostgreSQL reports a stale Document Studio schema.

    The public response stays generic, while the full database exception is
    retained in the application log for administrators.
    """
    source = getattr(error, "orig", error)
    message = str(source).lower()
    schema_tokens = (
        "workspace_documents",
        "workspace_document_revisions",
        "workspace_document_collaborators",
        "workspace_document_assets",
        "workspace_document_signatures",
        "undefinedcolumn",
        "undefinedtable",
        "does not exist",
    )
    return any(token in message for token in schema_tokens)


def _commit_created_document(
    db: Session,
    document: WorkspaceDocument,
    *,
    user_id: UUID,
) -> None:
    """Persist a document and its initial immutable revision atomically."""
    try:
        db.add(document)
        db.flush()
        _revision(db, document, user_id)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        logger.exception("Document Studio could not create a document because a database constraint failed")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The document could not be created because its owner, company, "
                "branch or reference is no longer valid. Refresh the page and retry."
            ),
        ) from error
    except (ProgrammingError, OperationalError) as error:
        db.rollback()
        logger.exception("Document Studio database operation failed during document creation")
        if _is_workspace_schema_error(error):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Document Studio database schema is not up to date. "
                    "Run 'alembic upgrade head' in the backend, then restart FastAPI."
                ),
            ) from error
        raise
    except Exception:
        db.rollback()
        logger.exception("Unexpected Document Studio failure during document creation")
        raise


@router.get("", response_model=WorkspaceDocumentListRead)
def list_workspace_documents(
    search: str | None = None,
    document_status: str | None = Query(default=None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=300),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    collaborator_ids = db.query(WorkspaceDocumentCollaborator.document_id).filter(
        WorkspaceDocumentCollaborator.user_id == context.user.id
    )
    visibility_conditions = [
        WorkspaceDocument.owner_user_id == context.user.id,
        WorkspaceDocument.id.in_(collaborator_ids),
    ]
    if context.company_id:
        visibility_conditions.append(
            (WorkspaceDocument.company_id == context.company_id)
            & (WorkspaceDocument.visibility == "company")
        )
    if is_platform_role(context.user.role):
        visibility_conditions.append(WorkspaceDocument.visibility == "platform")

    query = _base_query(db).filter(
        WorkspaceDocument.is_deleted.is_(False),
        or_(*visibility_conditions),
    )
    if document_status:
        query = query.filter(WorkspaceDocument.status == document_status)
    if search:
        token = f"%{search.strip()}%"
        query = query.filter(or_(
            WorkspaceDocument.title.ilike(token),
            WorkspaceDocument.reference.ilike(token),
            WorkspaceDocument.plain_text.ilike(token),
        ))
    rows = query.order_by(WorkspaceDocument.updated_at.desc()).all()
    return WorkspaceDocumentListRead(
        items=[_read(db, context, item) for item in rows[skip: skip + limit]],
        total=len(rows),
    )


@router.post("", response_model=WorkspaceDocumentRead, status_code=status.HTTP_201_CREATED)
def create_workspace_document(
    payload: WorkspaceDocumentCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    _validate_visibility(context, payload.visibility)
    is_client_letter = payload.template_key in CLIENT_LETTER_TEMPLATE_KEYS
    if payload.brand_logo_asset_id is not None and not is_client_letter:
        _owned_asset_or_404(db, context, payload.brand_logo_asset_id, kind="logo")

    client_letter_context = build_client_letter_context(
        db,
        context=context,
        template_key=payload.template_key,
        company_client_id=payload.company_client_id,
        loan_id=payload.loan_id,
        signer_name=payload.signer_name,
        signer_title=payload.signer_title,
        company_bank_accounts=payload.company_bank_accounts,
    )
    content_html = sanitize_document_html(
        payload.content_html
        if payload.content_html is not None
        else default_document_html(
            payload.template_key,
            user_display_name(context.user),
            client_letter_context.values if client_letter_context else None,
        )
    )
    document = WorkspaceDocument(
        owner_user_id=context.user.id,
        company_id=context.company_id,
        branch_id=context.branch_id,
        last_edited_by_user_id=context.user.id,
        reference=document_reference(),
        title=payload.title,
        template_key=payload.template_key,
        content_json=content_json_or_default(payload.content_json),
        content_html=content_html,
        plain_text=plain_text_from_html(content_html),
        visibility="company" if is_client_letter else payload.visibility,
        status="draft",
        version=1,
        style_key=payload.style_key,
        default_font_family=payload.default_font_family,
        default_font_size_pt=payload.default_font_size_pt,
        default_line_height_percent=payload.default_line_height_percent,
        include_brand_header=True if is_client_letter else payload.include_brand_header,
        include_footer=payload.include_footer,
        is_confidential=payload.is_confidential,
        brand_logo_asset_id=None if is_client_letter else payload.brand_logo_asset_id,
        cover_page_enabled=payload.cover_page_enabled,
        cover_page=payload.cover_page.model_dump(),
        address_blocks=[item.model_dump() for item in payload.address_blocks],
    )
    _commit_created_document(
        db,
        document,
        user_id=context.user.id,
    )
    document = _document_or_404(db, context, document.id)
    return _read(db, context, document)



@router.get("/assets", response_model=list[WorkspaceDocumentAssetRead])
def list_workspace_document_assets(
    kind: str | None = Query(default=None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    query = db.query(WorkspaceDocumentAsset).filter(
        WorkspaceDocumentAsset.owner_user_id == context.user.id,
        WorkspaceDocumentAsset.is_active.is_(True),
    )
    if kind:
        if kind not in {"logo", "signature"}:
            raise HTTPException(status_code=400, detail="Asset kind must be logo or signature")
        query = query.filter(WorkspaceDocumentAsset.kind == kind)
    rows = query.order_by(
        WorkspaceDocumentAsset.is_default.desc(),
        WorkspaceDocumentAsset.updated_at.desc(),
    ).all()
    return [_asset_read(row) for row in rows]


async def _store_workspace_asset(
    *,
    db: Session,
    context: TenantContext,
    file: UploadFile,
    kind: str,
    label: str,
    make_default: bool,
) -> WorkspaceDocumentAsset:
    raw = await file.read()
    if kind == "logo":
        processed, width, height, metadata = normalize_logo_image(raw)
    else:
        processed, width, height, metadata = extract_signature_image(raw)
    digest = image_sha256(processed)
    existing = db.query(WorkspaceDocumentAsset).filter(
        WorkspaceDocumentAsset.owner_user_id == context.user.id,
        WorkspaceDocumentAsset.kind == kind,
        WorkspaceDocumentAsset.sha256 == digest,
        WorkspaceDocumentAsset.is_active.is_(True),
    ).first()
    if make_default:
        db.query(WorkspaceDocumentAsset).filter(
            WorkspaceDocumentAsset.owner_user_id == context.user.id,
            WorkspaceDocumentAsset.kind == kind,
            WorkspaceDocumentAsset.is_default.is_(True),
        ).update({WorkspaceDocumentAsset.is_default: False}, synchronize_session=False)
    if existing:
        existing.label = label.strip() or existing.label
        existing.is_default = make_default or existing.is_default
        db.commit()
        db.refresh(existing)
        return existing
    stored_bytes, is_encrypted, encryption_nonce, encryption_version = protect_asset_bytes(
        processed,
        force_encrypt=(kind == "signature"),
    )
    metadata = {
        **metadata,
        "vault_access": "owner_only" if kind == "signature" else "owner_managed",
        "encrypted_at_rest": bool(is_encrypted),
    }
    asset = WorkspaceDocumentAsset(
        owner_user_id=context.user.id,
        company_id=context.company_id,
        kind=kind,
        label=label.strip() or ("My logo" if kind == "logo" else "My signature"),
        original_filename=file.filename,
        mime_type="image/png",
        image_data=stored_bytes,
        is_encrypted=is_encrypted,
        encryption_nonce=encryption_nonce,
        encryption_version=encryption_version,
        width_px=width,
        height_px=height,
        sha256=digest,
        is_default=make_default,
        is_active=True,
        processing_metadata=metadata,
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.post("/assets/logo", response_model=WorkspaceDocumentAssetRead, status_code=status.HTTP_201_CREATED)
async def upload_workspace_logo(
    file: UploadFile = File(...),
    label: str = Form(default="My logo"),
    make_default: bool = Form(default=True),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    asset = await _store_workspace_asset(
        db=db,
        context=context,
        file=file,
        kind="logo",
        label=label,
        make_default=make_default,
    )
    return _asset_read(asset)


@router.post("/assets/signature", response_model=WorkspaceDocumentAssetRead, status_code=status.HTTP_201_CREATED)
async def upload_workspace_signature(
    file: UploadFile = File(...),
    label: str = Form(default="My signature"),
    make_default: bool = Form(default=True),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    asset = await _store_workspace_asset(
        db=db,
        context=context,
        file=file,
        kind="signature",
        label=label,
        make_default=make_default,
    )
    return _asset_read(asset)


@router.get("/assets/{asset_id}/content")
def workspace_asset_content(
    asset_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    asset = _owned_asset_or_404(db, context, asset_id)
    return Response(
        content=asset_image_bytes(asset),
        media_type=asset.mime_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace_asset(
    asset_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    asset = _owned_asset_or_404(db, context, asset_id)
    asset.is_active = False
    asset.is_default = False
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{document_id}", response_model=WorkspaceDocumentRead)
def get_workspace_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    return _read(db, context, _document_or_404(db, context, document_id))



@router.get("/{document_id}/brand-logo/content")
def document_brand_logo_content(
    document_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)

    # A logo selected specifically for the document wins. Otherwise the
    # current document company logo is the default. The writer's default
    # logo remains the last fallback for non-company documents.
    if document.brand_logo_asset_id:
        asset = resolved_brand_asset(db, document)
        if asset:
            return Response(
                content=asset_image_bytes(asset),
                media_type=asset.mime_type,
                headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
            )

    company_logo = get_company_branding_logos(db, document.company).right_logo
    if company_logo:
        return Response(
            content=company_logo,
            media_type="image/png",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    asset = resolved_brand_asset(db, document)
    if asset:
        return Response(
            content=asset_image_bytes(asset),
            media_type=asset.mime_type,
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    raise HTTPException(status_code=404, detail="This document has no company or custom logo")


@router.get("/{document_id}/signature-assets/{asset_id}/content")
def document_signature_asset_content(
    document_id: UUID,
    asset_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    row = db.query(WorkspaceDocumentSignature).filter(
        WorkspaceDocumentSignature.document_id == document.id,
        WorkspaceDocumentSignature.asset_id == asset_id,
        WorkspaceDocumentSignature.signer_user_id == context.user.id,
        WorkspaceDocumentSignature.revoked_at.is_(None),
    ).first()
    if not row or not row.asset:
        # Do not reveal whether another user's private signature exists.
        raise HTTPException(status_code=404, detail="Signature image not found")
    content = signature_asset_bytes_for_owner(row, context.user.id)
    return Response(
        content=content,
        media_type=row.asset.mime_type,
        headers={
            "Cache-Control": "private, no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
            "X-Robots-Tag": "noindex, noarchive, nosnippet",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.get("/{document_id}/signatures", response_model=list[WorkspaceDocumentSignatureRead])
def list_workspace_document_signatures(
    document_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    rows = db.query(WorkspaceDocumentSignature).filter(
        WorkspaceDocumentSignature.document_id == document.id,
        WorkspaceDocumentSignature.revoked_at.is_(None),
    ).order_by(WorkspaceDocumentSignature.signed_at.asc()).all()
    return [_signature_read(row, viewer_user_id=context.user.id) for row in rows]


@router.post("/{document_id}/signatures", response_model=WorkspaceDocumentSignatureRead, status_code=status.HTTP_201_CREATED)
def apply_workspace_document_signature(
    document_id: UUID,
    payload: WorkspaceDocumentSignatureCreate,
    request: Request,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    explicitly_shared = _collaboration(db, document.id, context.user.id)
    if document.owner_user_id != context.user.id and not explicitly_shared and not context.is_platform_admin:
        raise HTTPException(
            status_code=403,
            detail="A signature can be applied only by the document owner or an explicitly invited collaborator",
        )
    if document.status == "archived":
        raise HTTPException(status_code=409, detail="Archived documents cannot be signed")

    fields = signature_field_metadata(document.content_html)
    field = fields.get(payload.field_id)
    if not field:
        raise HTTPException(status_code=404, detail="The signature field no longer exists in this document")
    if field["field_type"] not in {"signature", "initials"}:
        raise HTTPException(status_code=400, detail="Electronic signatures can be applied only to signature or initials fields")

    existing = db.query(WorkspaceDocumentSignature).filter(
        WorkspaceDocumentSignature.document_id == document.id,
        WorkspaceDocumentSignature.field_id == payload.field_id,
        WorkspaceDocumentSignature.revoked_at.is_(None),
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="This signature field is already signed")

    asset = None
    if payload.method == "stored_signature":
        if payload.asset_id is None:
            asset = default_asset(db, context.user.id, "signature")
            if asset is None:
                raise HTTPException(status_code=400, detail="Upload or select a stored signature first")
        else:
            asset = _owned_asset_or_404(db, context, payload.asset_id, kind="signature")

    document.version += 1
    document.last_edited_by_user_id = context.user.id
    signed_at = datetime.now(timezone.utc)
    document_hash = canonical_document_hash(document)
    verification_code = f"SIG-{secrets.token_hex(6).upper()}"
    row = WorkspaceDocumentSignature(
        document_id=document.id,
        field_id=payload.field_id,
        field_type=field["field_type"],
        signer_user_id=context.user.id,
        signer_name=user_display_name(context.user),
        method=payload.method,
        asset_id=asset.id if asset else None,
        consent_text=payload.consent_text,
        signed_at=signed_at,
        document_version=document.version,
        document_hash=document_hash,
        verification_code=verification_code,
        ip_hash=_request_digest(request.client.host if request.client else None),
        user_agent_hash=_request_digest(request.headers.get("user-agent")),
    )
    db.add(row)
    _revision(db, document, context.user.id)
    db.commit()
    db.refresh(row)
    return _signature_read(row, viewer_user_id=context.user.id)


@router.delete("/{document_id}/signatures/{field_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_workspace_document_signature(
    document_id: UUID,
    field_id: str,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    if not _can_manage(context, document):
        raise HTTPException(status_code=403, detail="Only the document owner can revoke a signature")
    if document.status == "archived":
        raise HTTPException(status_code=409, detail="Archived documents cannot be changed")
    row = db.query(WorkspaceDocumentSignature).filter(
        WorkspaceDocumentSignature.document_id == document.id,
        WorkspaceDocumentSignature.field_id == field_id,
        WorkspaceDocumentSignature.revoked_at.is_(None),
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Active signature not found")
    row.revoked_at = datetime.now(timezone.utc)
    row.revoked_by_user_id = context.user.id
    document.version += 1
    document.last_edited_by_user_id = context.user.id
    _revision(db, document, context.user.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{document_id}", response_model=WorkspaceDocumentRead)
def update_workspace_document(
    document_id: UUID,
    payload: WorkspaceDocumentUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    if not _can_edit(db, context, document):
        raise HTTPException(status_code=403, detail="You have view-only access to this document")
    if document.status == "archived":
        raise HTTPException(status_code=409, detail="Archived documents cannot be edited")
    if payload.expected_version is not None and payload.expected_version != document.version:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "This document was changed by another user. Reload before saving.",
                "current_version": document.version,
            },
        )
    sanitised_html = sanitize_document_html(payload.content_html) if payload.content_html is not None else None
    incoming_cover = payload.cover_page.model_dump() if payload.cover_page is not None else None
    incoming_addresses = [item.model_dump() for item in payload.address_blocks] if payload.address_blocks is not None else None
    material_edit = any((
        payload.title is not None and (payload.title.strip() or "Untitled document") != document.title,
        payload.content_json is not None and payload.content_json != (document.content_json or {}),
        sanitised_html is not None and sanitised_html != (document.content_html or ""),
        payload.page_size is not None and payload.page_size != document.page_size,
        payload.orientation is not None and payload.orientation != document.orientation,
        payload.margin_top_mm is not None and payload.margin_top_mm != document.margin_top_mm,
        payload.margin_right_mm is not None and payload.margin_right_mm != document.margin_right_mm,
        payload.margin_bottom_mm is not None and payload.margin_bottom_mm != document.margin_bottom_mm,
        payload.margin_left_mm is not None and payload.margin_left_mm != document.margin_left_mm,
        payload.style_key is not None and payload.style_key != document.style_key,
        payload.default_font_family is not None and payload.default_font_family != document.default_font_family,
        payload.default_font_size_pt is not None and payload.default_font_size_pt != document.default_font_size_pt,
        payload.default_line_height_percent is not None and payload.default_line_height_percent != document.default_line_height_percent,
        payload.include_brand_header is not None and payload.include_brand_header != document.include_brand_header,
        payload.include_footer is not None and payload.include_footer != document.include_footer,
        payload.is_confidential is not None and payload.is_confidential != document.is_confidential,
        payload.cover_page_enabled is not None and payload.cover_page_enabled != document.cover_page_enabled,
        incoming_cover is not None and incoming_cover != (document.cover_page or {}),
        incoming_addresses is not None and incoming_addresses != (document.address_blocks or []),
        payload.brand_logo_asset_id is not None and payload.brand_logo_asset_id != document.brand_logo_asset_id,
        payload.clear_brand_logo_asset and document.brand_logo_asset_id is not None,
    ))
    if material_edit:
        invalidated = _invalidate_active_signatures(db, document, user_id=context.user.id)
        if invalidated:
            logger.info(
                "Invalidated %s signature(s) after document edit document_id=%s user_id=%s",
                invalidated, document.id, context.user.id,
            )

    if payload.visibility is not None:
        if not _can_manage(context, document):
            raise HTTPException(status_code=403, detail="Only the owner can change document visibility")
        _validate_visibility(context, payload.visibility)
        document.visibility = payload.visibility
    if payload.title is not None:
        document.title = payload.title.strip() or "Untitled document"
    if payload.content_json is not None:
        document.content_json = payload.content_json
    if sanitised_html is not None:
        document.content_html = sanitised_html
        document.plain_text = plain_text_from_html(document.content_html)
    for name in (
        "page_size", "orientation", "margin_top_mm", "margin_right_mm",
        "margin_bottom_mm", "margin_left_mm", "style_key",
        "default_font_family", "default_font_size_pt",
        "default_line_height_percent", "include_brand_header",
        "include_footer", "is_confidential", "cover_page_enabled",
    ):
        value = getattr(payload, name)
        if value is not None:
            setattr(document, name, value)
    if incoming_cover is not None:
        document.cover_page = incoming_cover
    if incoming_addresses is not None:
        document.address_blocks = incoming_addresses
    if payload.clear_brand_logo_asset:
        if not _can_manage(context, document):
            raise HTTPException(status_code=403, detail="Only the owner can change the document logo")
        document.brand_logo_asset_id = None
    elif payload.brand_logo_asset_id is not None:
        if not _can_manage(context, document):
            raise HTTPException(status_code=403, detail="Only the owner can change the document logo")
        _owned_asset_or_404(db, context, payload.brand_logo_asset_id, kind="logo")
        document.brand_logo_asset_id = payload.brand_logo_asset_id
    if payload.status is not None:
        if payload.status in {"final", "archived"} and not _can_manage(context, document):
            raise HTTPException(status_code=403, detail="Only the owner can finalize or archive a document")
        document.status = payload.status
        if payload.status == "final" and document.finalized_at is None:
            document.finalized_at = datetime.now(timezone.utc)
    document.version += 1
    document.last_edited_by_user_id = context.user.id
    if payload.create_revision:
        _revision(db, document, context.user.id)
    db.commit()
    db.refresh(document)
    document = _document_or_404(db, context, document.id)
    return _read(db, context, document)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workspace_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    if not _can_manage(context, document):
        raise HTTPException(status_code=403, detail="Only the owner can remove this document")
    document.is_deleted = True
    document.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{document_id}/collaborators", response_model=list[WorkspaceDocumentCollaboratorRead])
def list_document_collaborators(
    document_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    if not _can_manage(context, document):
        raise HTTPException(status_code=403, detail="Only the owner can manage sharing")
    rows = db.query(WorkspaceDocumentCollaborator).options(
        joinedload(WorkspaceDocumentCollaborator.user).joinedload(User.person)
    ).filter(WorkspaceDocumentCollaborator.document_id == document.id).order_by(
        WorkspaceDocumentCollaborator.created_at.desc()
    ).all()
    return [WorkspaceDocumentCollaboratorRead(
        id=row.id,
        user_id=row.user_id,
        display_name=user_display_name(row.user),
        email=row.user.email,
        phone=row.user.phone,
        permission=row.permission,
        created_at=row.created_at,
    ) for row in rows]


@router.post("/{document_id}/collaborators", response_model=WorkspaceDocumentCollaboratorRead)
def add_document_collaborator(
    document_id: UUID,
    payload: WorkspaceDocumentCollaboratorCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    if not _can_manage(context, document):
        raise HTTPException(status_code=403, detail="Only the owner can manage sharing")
    if payload.user_id == context.user.id:
        raise HTTPException(status_code=400, detail="The owner already has full access")
    if payload.user_id not in allowed_directory_ids(db, context):
        raise HTTPException(status_code=403, detail="This user is outside your permitted sharing directory")
    user = db.query(User).options(joinedload(User.person)).filter(
        User.id == payload.user_id,
        User.is_active.is_(True),
    ).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    row = db.query(WorkspaceDocumentCollaborator).filter(
        WorkspaceDocumentCollaborator.document_id == document.id,
        WorkspaceDocumentCollaborator.user_id == payload.user_id,
    ).first()
    if row:
        row.permission = payload.permission
    else:
        row = WorkspaceDocumentCollaborator(
            document_id=document.id,
            user_id=payload.user_id,
            invited_by_user_id=context.user.id,
            permission=payload.permission,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return WorkspaceDocumentCollaboratorRead(
        id=row.id,
        user_id=row.user_id,
        display_name=user_display_name(user),
        email=user.email,
        phone=user.phone,
        permission=row.permission,
        created_at=row.created_at,
    )


@router.delete("/{document_id}/collaborators/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_document_collaborator(
    document_id: UUID,
    user_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    if not _can_manage(context, document):
        raise HTTPException(status_code=403, detail="Only the owner can manage sharing")
    row = db.query(WorkspaceDocumentCollaborator).filter(
        WorkspaceDocumentCollaborator.document_id == document.id,
        WorkspaceDocumentCollaborator.user_id == user_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    db.delete(row)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{document_id}/revisions", response_model=list[WorkspaceDocumentRevisionRead])
def list_document_revisions(
    document_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    rows = db.query(WorkspaceDocumentRevision).filter(
        WorkspaceDocumentRevision.document_id == document.id
    ).order_by(WorkspaceDocumentRevision.version.desc()).limit(100).all()
    return rows


def _export_payload(db: Session, document: WorkspaceDocument, format_name: str) -> tuple[bytes, str, str]:
    if format_name == "docx":
        return export_docx(db, document, document.company), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"
    if format_name == "pdf":
        return export_pdf(db, document, document.company), "application/pdf", "pdf"
    raise HTTPException(status_code=400, detail="Format must be pdf or docx")


@router.get("/{document_id}/export/{format_name}")
def download_workspace_document(
    document_id: UUID,
    format_name: str,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    content, mime_type, extension = _export_payload(db, document, format_name.lower())
    clean_name = "".join(character if character.isalnum() or character in " -_" else "_" for character in document.title).strip() or "letter"
    filename = f"{clean_name}.{extension}"
    encoded = quote(filename, safe="")
    return StreamingResponse(
        BytesIO(content),
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"document.{extension}\"; filename*=UTF-8''{encoded}",
            "Content-Length": str(len(content)),
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/{document_id}/publish", response_model=ManagedFileRead, status_code=status.HTTP_201_CREATED)
def publish_workspace_document(
    document_id: UUID,
    payload: WorkspaceDocumentPublish,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _document_or_404(db, context, document_id)
    content, mime_type, extension = _export_payload(db, document, payload.format)
    visibility = payload.visibility or ("company" if document.company_id else "private")
    _validate_visibility(context, visibility)
    clean_title = "".join(character if character.isalnum() or character in " -_" else "_" for character in document.title).strip() or "letter"
    name = payload.file_name or f"{clean_title}.{extension}"
    if not name.lower().endswith(f".{extension}"):
        name = f"{name}.{extension}"
    record = store_bytes(
        db,
        content=content,
        original_name=name,
        mime_type=mime_type,
        owner_user_id=context.user.id,
        company_id=document.company_id,
        branch_id=document.branch_id,
        category="letter_document",
        visibility=visibility,
        description=f"Published from {document.reference}, version {document.version}",
        linked_entity_type="workspace_document",
        linked_entity_id=str(document.id),
        is_confidential=document.is_confidential if payload.is_confidential is None else payload.is_confidential,
    )
    db.commit()
    db.refresh(record)
    return record
