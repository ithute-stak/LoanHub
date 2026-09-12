from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from core.access_control import require_platform_owner
from database.models.audit_log import AuditLog
from database.models.user import User
from database.schemas.system_update import SystemUpdateCreate, SystemUpdateStatusRead
from database.session import get_db
from services.system_update_service import (
    SystemUpdaterError,
    get_system_update_status,
    trigger_system_update,
)


router = APIRouter(prefix="/system-updates", tags=["System Updates"])


@router.get("/status", response_model=SystemUpdateStatusRead)
def read_system_update_status(
    _: User = Depends(require_platform_owner),
):
    return get_system_update_status()


@router.post("/update", response_model=SystemUpdateStatusRead)
def start_system_update(
    payload: SystemUpdateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_platform_owner),
):
    if payload.confirmation.strip() != "UPDATE":
        raise HTTPException(status_code=422, detail='Type "UPDATE" exactly to confirm the deployment')

    try:
        status = trigger_system_update()
    except SystemUpdaterError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="system_update_requested",
            table_name="system_updates",
            entity_type="system_update",
            description="The platform owner requested a LoanHub production update.",
            actor_role=current_user.role.value,
            severity="warning",
            status="success",
            after_data={
                "state": status.get("state"),
                "message": status.get("message"),
            },
            changed_fields=["deployment"],
            event_data={
                "source": "superadmin_system_update",
                "service": "loanhub",
            },
        )
    )
    db.commit()
    return status
