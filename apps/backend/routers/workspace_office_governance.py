from __future__ import annotations

from io import BytesIO
from typing import Literal
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from core.access_control import TenantContext, get_user_context, is_platform_role
from database.models.company_staff import CompanyStaff
from database.models.enums import UserRole
from database.models.user import User
from database.models.workspace_document import (
    WorkspaceDocument,
    WorkspaceDocumentCollaborator,
    WorkspaceDocumentRevision,
    WorkspaceDocumentSignature,
)
from database.models.workspace_document_folder import WorkspaceDocumentFolder, WorkspaceDocumentFolderItem
from database.schemas.workspace_document import (
    WorkspaceDocumentListRead,
    WorkspaceDocumentRead,
    WorkspaceDocumentRevisionRead,
    WorkspaceDocumentSignatureRead,
)
from database.session import get_db
from routers.workspace_documents import _base_query, _export_payload, _read, _signature_read
from services.document_branding_service import get_company_branding_logos
from services.workspace_document_asset_service import asset_image_bytes, resolved_brand_asset
from services.workspace_document_service import user_display_name


document_router = APIRouter(prefix="/workspace-documents", tags=["Office Workspace Governance"])
office_router = APIRouter(prefix="/workspace-office", tags=["Office Workspace Governance"])

WorkspaceKind = Literal["document", "spreadsheet", "all"]


class OfficeAccessRead(BaseModel):
    is_company_owner: bool
    company_id: UUID | None = None
    role: str


class OfficeFolderRead(BaseModel):
    id: UUID
    name: str
    parent_id: UUID | None = None
    owner_user_id: UUID
    owner_display_name: str
    can_manage: bool
    is_personal: bool
    document_count: int = 0
    child_count: int = 0


class PersonalFolderRead(BaseModel):
    folder_id: UUID | None = None
    name: str | None = None
    moved_count: int = 0


class SharingDirectoryUserRead(BaseModel):
    user_id: UUID
    display_name: str
    email: str | None = None
    phone: str | None = None
    role: str


def _is_company_owner(context: TenantContext) -> bool:
    return bool(
        context.company_id
        and context.staff
        and context.role == UserRole.COMPANY_OWNER
    )


def _kind_filter(query, kind: WorkspaceKind):
    spreadsheet_prefix = func.left(WorkspaceDocument.template_key, 12) == "spreadsheet_"
    if kind == "spreadsheet":
        return query.filter(spreadsheet_prefix)
    if kind == "document":
        return query.filter(~spreadsheet_prefix)
    return query


def _can_view_governed(
    db: Session,
    context: TenantContext,
    document: WorkspaceDocument,
) -> bool:
    if document.owner_user_id == context.user.id:
        return True
    # Company owners receive oversight read access to every workspace item in
    # their active company. Ownership and edit/manage permissions are unchanged.
    if _is_company_owner(context) and document.company_id == context.company_id:
        return True
    collaborator = db.query(WorkspaceDocumentCollaborator.id).filter(
        WorkspaceDocumentCollaborator.document_id == document.id,
        WorkspaceDocumentCollaborator.user_id == context.user.id,
    ).first()
    if collaborator:
        return True
    if (
        document.visibility == "company"
        and context.company_id
        and document.company_id == context.company_id
    ):
        return True
    if document.visibility == "platform" and is_platform_role(context.user.role):
        return True
    return False


def _governed_document_or_404(
    db: Session,
    context: TenantContext,
    document_id: UUID,
) -> WorkspaceDocument:
    document = _base_query(db).filter(
        WorkspaceDocument.id == document_id,
        WorkspaceDocument.is_deleted.is_(False),
    ).first()
    if not document or not _can_view_governed(db, context, document):
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def _normalise_name(value: str) -> tuple[str, str]:
    name = " ".join((value or "").split()).strip() or "My workspace"
    return name[:120], name[:120].casefold()


def _personal_folder(
    db: Session,
    context: TenantContext,
    *,
    create: bool,
) -> WorkspaceDocumentFolder | None:
    if not context.company_id or not context.staff:
        return None
    name, normalised = _normalise_name(user_display_name(context.user))
    row = db.query(WorkspaceDocumentFolder).filter(
        WorkspaceDocumentFolder.owner_user_id == context.user.id,
        WorkspaceDocumentFolder.company_id == context.company_id,
        WorkspaceDocumentFolder.parent_id.is_(None),
        WorkspaceDocumentFolder.normalized_name == normalised,
        WorkspaceDocumentFolder.is_deleted.is_(False),
    ).first()
    if row or not create:
        return row
    row = WorkspaceDocumentFolder(
        owner_user_id=context.user.id,
        company_id=context.company_id,
        parent_id=None,
        name=name,
        normalized_name=normalised,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        row = db.query(WorkspaceDocumentFolder).filter(
            WorkspaceDocumentFolder.owner_user_id == context.user.id,
            WorkspaceDocumentFolder.company_id == context.company_id,
            WorkspaceDocumentFolder.parent_id.is_(None),
            WorkspaceDocumentFolder.normalized_name == normalised,
            WorkspaceDocumentFolder.is_deleted.is_(False),
        ).first()
        if not row:
            raise
    return row


def _folder_count(db: Session, folder_id: UUID, kind: WorkspaceKind) -> int:
    query = db.query(func.count(WorkspaceDocumentFolderItem.id)).join(
        WorkspaceDocument,
        WorkspaceDocument.id == WorkspaceDocumentFolderItem.document_id,
    ).filter(
        WorkspaceDocumentFolderItem.folder_id == folder_id,
        WorkspaceDocument.is_deleted.is_(False),
    )
    query = _kind_filter(query, kind)
    return int(query.scalar() or 0)


def _folder_read(
    db: Session,
    context: TenantContext,
    folder: WorkspaceDocumentFolder,
    kind: WorkspaceKind,
) -> OfficeFolderRead:
    owner_name = user_display_name(folder.owner)
    _, personal_name = _normalise_name(owner_name)
    child_count = db.query(func.count(WorkspaceDocumentFolder.id)).filter(
        WorkspaceDocumentFolder.parent_id == folder.id,
        WorkspaceDocumentFolder.is_deleted.is_(False),
    ).scalar() or 0
    return OfficeFolderRead(
        id=folder.id,
        name=folder.name,
        parent_id=folder.parent_id,
        owner_user_id=folder.owner_user_id,
        owner_display_name=owner_name,
        can_manage=folder.owner_user_id == context.user.id,
        is_personal=bool(folder.parent_id is None and folder.normalized_name == personal_name),
        document_count=_folder_count(db, folder.id, kind),
        child_count=int(child_count),
    )


@document_router.get("", response_model=WorkspaceDocumentListRead)
def list_governed_workspace_documents(
    search: str | None = None,
    document_status: str | None = Query(default=None, alias="status"),
    kind: WorkspaceKind = Query(default="document"),
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
    if _is_company_owner(context):
        visibility_conditions.append(WorkspaceDocument.company_id == context.company_id)
    if is_platform_role(context.user.role):
        visibility_conditions.append(WorkspaceDocument.visibility == "platform")

    query = _base_query(db).filter(
        WorkspaceDocument.is_deleted.is_(False),
        or_(*visibility_conditions),
    )
    query = _kind_filter(query, kind)
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


@document_router.get("/{document_id}", response_model=WorkspaceDocumentRead)
def get_governed_workspace_document(
    document_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    return _read(db, context, _governed_document_or_404(db, context, document_id))


@document_router.get("/{document_id}/brand-logo/content")
def governed_document_brand_logo_content(
    document_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _governed_document_or_404(db, context, document_id)
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


@document_router.get("/{document_id}/signatures", response_model=list[WorkspaceDocumentSignatureRead])
def list_governed_document_signatures(
    document_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _governed_document_or_404(db, context, document_id)
    rows = db.query(WorkspaceDocumentSignature).filter(
        WorkspaceDocumentSignature.document_id == document.id,
        WorkspaceDocumentSignature.revoked_at.is_(None),
    ).order_by(WorkspaceDocumentSignature.signed_at.asc()).all()
    return [_signature_read(row, viewer_user_id=context.user.id) for row in rows]


@document_router.get("/{document_id}/revisions", response_model=list[WorkspaceDocumentRevisionRead])
def list_governed_document_revisions(
    document_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _governed_document_or_404(db, context, document_id)
    return db.query(WorkspaceDocumentRevision).filter(
        WorkspaceDocumentRevision.document_id == document.id
    ).order_by(WorkspaceDocumentRevision.version.desc()).limit(100).all()


@document_router.get("/{document_id}/export/{format_name}")
def download_governed_workspace_document(
    document_id: UUID,
    format_name: str,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = _governed_document_or_404(db, context, document_id)
    content, mime_type, extension = _export_payload(db, document, format_name.lower())
    clean_name = "".join(
        character if character.isalnum() or character in " -_" else "_"
        for character in document.title
    ).strip() or "document"
    filename = f"{clean_name}.{extension}"
    encoded = quote(filename, safe="")
    return StreamingResponse(
        BytesIO(content),
        media_type=mime_type,
        headers={
            "Content-Disposition": f"attachment; filename=\"document.{extension}\"; filename*=UTF-8''{encoded}",
            "Content-Length": str(len(content)),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@office_router.get("/access", response_model=OfficeAccessRead)
def workspace_access(
    context: TenantContext = Depends(get_user_context),
):
    return OfficeAccessRead(
        is_company_owner=_is_company_owner(context),
        company_id=context.company_id,
        role=str(getattr(context.role, "value", context.role)),
    )


@office_router.get("/folders", response_model=list[OfficeFolderRead])
def list_office_folders(
    kind: WorkspaceKind = Query(default="document"),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    personal = _personal_folder(db, context, create=True)
    if personal is not None:
        db.commit()

    query = db.query(WorkspaceDocumentFolder).options(
        joinedload(WorkspaceDocumentFolder.owner).joinedload(User.person)
    ).filter(WorkspaceDocumentFolder.is_deleted.is_(False))
    if _is_company_owner(context):
        query = query.filter(WorkspaceDocumentFolder.company_id == context.company_id)
    else:
        query = query.filter(WorkspaceDocumentFolder.owner_user_id == context.user.id)
    rows = query.order_by(
        WorkspaceDocumentFolder.owner_user_id.asc(),
        WorkspaceDocumentFolder.parent_id.asc().nullsfirst(),
        WorkspaceDocumentFolder.name.asc(),
    ).all()
    return [_folder_read(db, context, row, kind) for row in rows]


@office_router.get("/folder-assignments", response_model=dict[str, str])
def office_folder_assignments(
    kind: WorkspaceKind = Query(default="document"),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    query = db.query(WorkspaceDocumentFolderItem).join(
        WorkspaceDocumentFolder,
        WorkspaceDocumentFolder.id == WorkspaceDocumentFolderItem.folder_id,
    ).join(
        WorkspaceDocument,
        WorkspaceDocument.id == WorkspaceDocumentFolderItem.document_id,
    ).filter(
        WorkspaceDocumentFolder.is_deleted.is_(False),
        WorkspaceDocument.is_deleted.is_(False),
    )
    if _is_company_owner(context):
        query = query.filter(
            WorkspaceDocumentFolder.company_id == context.company_id,
            WorkspaceDocument.company_id == context.company_id,
        )
    else:
        query = query.filter(
            WorkspaceDocumentFolder.owner_user_id == context.user.id,
            WorkspaceDocument.owner_user_id == context.user.id,
        )
    query = _kind_filter(query, kind)
    return {str(row.document_id): str(row.folder_id) for row in query.all()}


@office_router.post("/file-my-unassigned", response_model=PersonalFolderRead)
def file_my_unassigned_workspace_items(
    kind: WorkspaceKind = Query(default="all"),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    folder = _personal_folder(db, context, create=True)
    if folder is None:
        return PersonalFolderRead()
    query = db.query(WorkspaceDocument).outerjoin(
        WorkspaceDocumentFolderItem,
        WorkspaceDocumentFolderItem.document_id == WorkspaceDocument.id,
    ).filter(
        WorkspaceDocument.owner_user_id == context.user.id,
        WorkspaceDocument.company_id == context.company_id,
        WorkspaceDocument.is_deleted.is_(False),
        WorkspaceDocumentFolderItem.id.is_(None),
    )
    query = _kind_filter(query, kind)
    rows = query.all()
    for document in rows:
        db.add(WorkspaceDocumentFolderItem(folder_id=folder.id, document_id=document.id))
    db.commit()
    return PersonalFolderRead(folder_id=folder.id, name=folder.name, moved_count=len(rows))


@office_router.post("/items/{document_id}/personal-folder", response_model=PersonalFolderRead)
def file_workspace_item_to_personal_folder(
    document_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    document = db.query(WorkspaceDocument).filter(
        WorkspaceDocument.id == document_id,
        WorkspaceDocument.owner_user_id == context.user.id,
        WorkspaceDocument.is_deleted.is_(False),
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Workspace item not found")
    folder = _personal_folder(db, context, create=True)
    if folder is None:
        return PersonalFolderRead()
    assignment = db.query(WorkspaceDocumentFolderItem).filter(
        WorkspaceDocumentFolderItem.document_id == document.id
    ).first()
    if assignment:
        assignment.folder_id = folder.id
    else:
        db.add(WorkspaceDocumentFolderItem(folder_id=folder.id, document_id=document.id))
    db.commit()
    return PersonalFolderRead(folder_id=folder.id, name=folder.name, moved_count=1)


@office_router.get("/sharing-directory", response_model=list[SharingDirectoryUserRead])
def sharing_directory(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    if not context.company_id:
        return []
    rows = db.query(CompanyStaff).options(
        joinedload(CompanyStaff.user).joinedload(User.person)
    ).filter(
        CompanyStaff.company_id == context.company_id,
        CompanyStaff.is_active.is_(True),
        CompanyStaff.user_id != context.user.id,
    ).order_by(CompanyStaff.user_id.asc()).all()
    seen: set[UUID] = set()
    result: list[SharingDirectoryUserRead] = []
    for row in rows:
        if row.user_id in seen or not row.user or not row.user.is_active:
            continue
        seen.add(row.user_id)
        result.append(SharingDirectoryUserRead(
            user_id=row.user_id,
            display_name=user_display_name(row.user),
            email=row.user.email,
            phone=row.user.phone,
            role=str(getattr(row.role, "value", row.role)),
        ))
    return result
