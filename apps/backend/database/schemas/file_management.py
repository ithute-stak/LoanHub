from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ManagedFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    reference: str
    owner_user_id: UUID | None = None
    company_id: UUID | None = None
    branch_id: UUID | None = None
    original_name: str
    mime_type: str
    detected_mime_type: str | None = None
    extension: str | None = None
    size_bytes: int
    checksum_sha256: str
    is_encrypted: bool = False
    scan_status: str = 'validated'
    category: str
    visibility: str
    description: str | None = None
    linked_entity_type: str | None = None
    linked_entity_id: str | None = None
    is_confidential: bool
    created_at: datetime
    updated_at: datetime


class ManagedFileListRead(BaseModel):
    items: list[ManagedFileRead]
    total: int
