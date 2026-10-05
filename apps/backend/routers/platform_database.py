from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.access_control import require_platform_owner
from database.models.user import User
from database.session import get_db
from services.database_management_service import database_health_snapshot


router = APIRouter(
    prefix="/platform-owner/database",
    tags=["Platform Owner Database Management"],
)


@router.get("/health")
def get_database_health(
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_owner),
):
    return database_health_snapshot(db)
