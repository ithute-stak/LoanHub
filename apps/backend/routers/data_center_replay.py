"""Guarded Data Center replay; metadata only, no financial record payloads."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_tenant_context
from database.session import get_db
from services.data_center_replay import ReplayNotReady, replay_metadata

router = APIRouter(prefix="/realtime/data-center", tags=["Data Center"])


@router.get("/replay")
def replay(
    response: Response,
    generation: UUID,
    after_cursor: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
    context: TenantContext = Depends(get_tenant_context),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    try:
        return replay_metadata(
            db, context,
            after_cursor=after_cursor,
            generation=generation,
            limit=limit,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Data Center replay access denied") from None
    except ReplayNotReady:
        raise HTTPException(status_code=409, detail="Data Center replay requires fresh snapshot") from None
