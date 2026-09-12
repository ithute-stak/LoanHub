from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from database.models.enums import NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    actor_user_id: UUID | None = None
    company_id: UUID | None = None
    branch_id: UUID | None = None

    title: str
    message: str
    notification_type: NotificationType
    event_type: str
    action: str
    entity_type: str | None = None
    entity_id: str | None = None
    action_url: str | None = None
    icon: str | None = None
    priority: str
    data: dict[str, Any] = Field(default_factory=dict)

    is_read: bool
    read_at: datetime | None = None
    is_archived: bool
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class NotificationListRead(BaseModel):
    items: list[NotificationRead]
    total: int
    unread_count: int
    page: int
    page_size: int


class NotificationUnreadCountRead(BaseModel):
    unread_count: int
