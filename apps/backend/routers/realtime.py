from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_user_context
from database.models.mobile_push import MobilePushDevice
from database.session import get_db
from services.mobile_push_service import install_realtime_push_bridge, push_configured

# Install once when the API router is composed. Existing chat/presence/domain
# code continues sending through the established WebSocket manager; eligible
# events automatically gain the background push wake path.
install_realtime_push_bridge()

router = APIRouter(prefix="/realtime", tags=["Realtime"])


class PushDeviceRegister(BaseModel):
    device_uuid: str = Field(min_length=8, max_length=120)
    push_token: str = Field(min_length=16, max_length=4096)
    platform: str = Field(default="android", max_length=24)
    provider: str = Field(default="fcm", max_length=24)
    app_version: str | None = Field(default=None, max_length=40)


@router.get("/configuration")
def realtime_configuration(context: TenantContext = Depends(get_user_context)):
    return {
        "websocket_path": "/ws",
        "event_contract": "loanhub.realtime.v1",
        "push_transport": "fcm",
        "push_server_configured": push_configured(),
        "background_strategy": "push_plus_periodic_catchup",
    }


@router.post("/devices/register")
def register_push_device(
    payload: PushDeviceRegister,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    device_uuid = payload.device_uuid.strip()
    push_token = payload.push_token.strip()
    now = datetime.now(timezone.utc)

    # A push token/device installation must belong to only the currently signed-in
    # LoanHub account. If the same phone changes accounts, deactivate the old
    # registrations before assigning the token to the new session.
    stale_rows = (
        db.query(MobilePushDevice)
        .filter(
            MobilePushDevice.user_id != context.user.id,
            MobilePushDevice.is_active.is_(True),
            (
                (MobilePushDevice.push_token == push_token)
                | (MobilePushDevice.device_uuid == device_uuid)
            ),
        )
        .all()
    )
    for stale in stale_rows:
        stale.is_active = False
        stale.revoked_at = now

    row = (
        db.query(MobilePushDevice)
        .filter(
            MobilePushDevice.user_id == context.user.id,
            MobilePushDevice.device_uuid == device_uuid,
        )
        .first()
    )
    if row is None:
        row = MobilePushDevice(
            user_id=context.user.id,
            device_uuid=device_uuid,
        )
        db.add(row)
    row.push_token = push_token
    row.platform = payload.platform.strip().lower() or "android"
    row.provider = payload.provider.strip().lower() or "fcm"
    row.app_version = payload.app_version.strip() if payload.app_version else None
    row.is_active = True
    row.revoked_at = None
    row.last_seen_at = now
    db.commit()
    db.refresh(row)
    return {
        "id": str(row.id),
        "device_uuid": row.device_uuid,
        "platform": row.platform,
        "provider": row.provider,
        "active": row.is_active,
        "registered_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.delete("/devices/{device_uuid}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_push_device(
    device_uuid: str,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    row = (
        db.query(MobilePushDevice)
        .filter(
            MobilePushDevice.user_id == context.user.id,
            MobilePushDevice.device_uuid == device_uuid,
        )
        .first()
    )
    if row:
        row.is_active = False
        row.revoked_at = datetime.now(timezone.utc)
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
