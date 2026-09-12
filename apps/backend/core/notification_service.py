# core/notification_service.py

from sqlalchemy.orm import Session

from core.websocket_manager import manager
from database.models.notificat import Broadcast


async def notify(
    *,
    db: Session,
    channel: str,
    title: str,
    message: str,
    event_type: str,
    user_id=None,
    entity=None,
    entity_id=None,
    data=None,
):
    notification = Broadcast(
        user_id=user_id,
        channel=channel,
        title=title,
        message=message,
        event_type=event_type,
        entity=entity,
        entity_id=str(entity_id) if entity_id else None,
        data=data or {},
        is_read=False,
    )

    db.add(notification)
    db.commit()
    db.refresh(notification)

    payload = {
        "id": str(notification.id),
        "channel": notification.channel,
        "title": notification.title,
        "message": notification.message,
        "event_type": notification.event_type,
        "entity": notification.entity,
        "entity_id": notification.entity_id,
        "data": notification.data,
        "is_read": notification.is_read,
        "created_at": str(notification.created_at),
    }

    await manager.send_to_channel(channel, payload)

    return notification