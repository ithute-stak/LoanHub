"""Management-only, read-consistent preview; not a live Redux bootstrap."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.session import get_db
from services.data_center_snapshot import SnapshotUnavailable, preview_snapshot

router = APIRouter(prefix="/realtime/data-center", tags=["Data Center"])


@router.get("/snapshot-preview")
def snapshot_preview(
    response: Response,
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        return preview_snapshot(context, db)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Data Center snapshot access denied") from None
    except SnapshotUnavailable:
        raise HTTPException(status_code=409, detail="Data Center snapshot is not ready") from None
