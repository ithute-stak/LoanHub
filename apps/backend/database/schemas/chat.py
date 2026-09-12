from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from database.schemas.file_management import ManagedFileRead


class ChatUserRead(BaseModel):
    id: UUID
    display_name: str
    email: str | None = None
    phone: str
    role: str
    company_name: str | None = None
    branch_name: str | None = None
    is_online: bool = False
    last_seen_at: datetime | None = None


class ChatParticipantRead(BaseModel):
    user: ChatUserRead
    is_admin: bool
    last_read_at: datetime | None = None


class ChatMessageRead(BaseModel):
    id: UUID
    conversation_id: UUID
    sender: ChatUserRead | None = None
    message_type: str
    body: str | None = None
    reply_to_message_id: UUID | None = None
    client_message_id: str
    attachments: list[ManagedFileRead] = Field(default_factory=list)
    edited_at: datetime | None = None
    deleted_at: datetime | None = None
    created_at: datetime


class ChatConversationRead(BaseModel):
    id: UUID
    reference: str
    title: str
    conversation_type: str
    is_group: bool
    company_id: UUID | None = None
    branch_id: UUID | None = None
    context_type: str | None = None
    context_id: str | None = None
    participants: list[ChatParticipantRead]
    last_message: ChatMessageRead | None = None
    unread_count: int = 0
    last_message_at: datetime | None = None
    created_at: datetime


class ChatConversationCreate(BaseModel):
    participant_ids: list[UUID]
    title: str | None = None
    conversation_type: str = 'direct'
    context_type: str | None = None
    context_id: str | None = None

    @field_validator('participant_ids')
    @classmethod
    def participant_count(cls, value: list[UUID]) -> list[UUID]:
        unique = list(dict.fromkeys(value))
        if not unique:
            raise ValueError('At least one participant is required')
        if len(unique) > 100:
            raise ValueError('A conversation can have at most 100 participants')
        return unique


class ChatMessageCreate(BaseModel):
    body: str
    client_message_id: str = Field(min_length=8, max_length=100)
    reply_to_message_id: UUID | None = None

    @field_validator('body')
    @classmethod
    def body_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError('Message cannot be empty')
        if len(cleaned) > 10000:
            raise ValueError('Message is too long')
        return cleaned


class ChatMessageUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=10000)


class ChatUnreadCountRead(BaseModel):
    unread_count: int


class ChatExistingFileShareCreate(BaseModel):
    body: str | None = Field(default=None, max_length=2000)
    client_message_id: str = Field(min_length=8, max_length=100)

    @field_validator('body')
    @classmethod
    def clean_body(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None
