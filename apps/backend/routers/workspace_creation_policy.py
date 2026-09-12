from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_user_context
from database.schemas.workspace_document import WorkspaceDocumentCreate, WorkspaceDocumentRead
from database.session import get_db
from routers.workspace_documents import create_workspace_document as create_legacy_workspace_document
from services.client_document_template_service import CLIENT_LETTER_TEMPLATE_KEYS


router = APIRouter(prefix="/workspace-documents", tags=["Office Workspace Governance"])


@router.post("", response_model=WorkspaceDocumentRead, status_code=status.HTTP_201_CREATED)
def create_governed_workspace_document(
    payload: WorkspaceDocumentCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Create normal staff work privately, then let users share deliberately.

    Older Document Studio screens historically submitted ``company`` as their
    default visibility. That made every new staff document visible company-wide
    even when the user had not chosen to publish it. Company client letters are
    the intentional exception because the existing verified-letter workflow is
    explicitly company-visible.
    """
    if (
        context.company_id
        and payload.visibility == "company"
        and payload.template_key not in CLIENT_LETTER_TEMPLATE_KEYS
    ):
        payload = payload.model_copy(update={"visibility": "private"})
    return create_legacy_workspace_document(payload=payload, db=db, context=context)
