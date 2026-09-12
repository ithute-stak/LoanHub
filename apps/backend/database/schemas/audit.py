from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID | None = None
    company_id: UUID | None = None
    branch_id: UUID | None = None
    action: str
    table_name: str | None = None
    entity_type: str | None = None
    record_id: UUID | None = None
    description: str | None = None
    actor_role: str | None = None
    actor_name: str | None = None
    company_name: str | None = None
    branch_name: str | None = None
    entity_reference: str | None = None
    severity: str
    status: str
    before_data: dict[str, Any] = Field(default_factory=dict)
    after_data: dict[str, Any] = Field(default_factory=dict)
    changed_fields: list[str] = Field(default_factory=list)
    event_data: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    duration_ms: int | None = None
    previous_hash: str | None = None
    event_hash: str | None = None
    hash_version: str | None = None
    sealed_at: datetime | None = None
    created_at: datetime


class AuditLogListRead(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int
