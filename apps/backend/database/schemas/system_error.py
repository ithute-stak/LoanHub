from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SystemErrorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    request_id: str | None = None
    fingerprint: str
    user_id: UUID | None = None
    company_id: UUID | None = None
    branch_id: UUID | None = None
    method: str | None = None
    path: str
    status_code: int
    error_type: str
    message: str
    stack_trace: str | None = None
    severity: str
    environment: str | None = None
    user_agent: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    is_resolved: bool
    resolved_at: datetime | None = None
    resolved_by_user_id: UUID | None = None
    resolution_notes: str | None = None
    created_at: datetime
    updated_at: datetime


class SystemErrorListRead(BaseModel):
    items: list[SystemErrorRead]
    total: int
    unresolved_count: int
    page: int
    page_size: int


class SystemErrorResolveCreate(BaseModel):
    resolution_notes: str = Field(min_length=2, max_length=4000)
