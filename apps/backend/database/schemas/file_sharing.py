from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


ALLOWED_SHARE_CHANNELS = {
    "native",
    "copy",
    "whatsapp",
    "facebook",
    "linkedin",
    "x",
    "telegram",
    "email",
}


class CompanySocialShareSettingsUpdate(BaseModel):
    external_sharing_enabled: bool = False
    default_expiry_hours: int = Field(default=24, ge=1, le=168)
    default_message: str | None = Field(default=None, max_length=1000)
    enabled_channels: list[str] = Field(default_factory=lambda: ["native", "whatsapp", "email"])

    whatsapp_number: str | None = Field(default=None, max_length=40)
    facebook_url: str | None = Field(default=None, max_length=500)
    instagram_url: str | None = Field(default=None, max_length=500)
    linkedin_url: str | None = Field(default=None, max_length=500)
    x_handle: str | None = Field(default=None, max_length=100)
    telegram_username: str | None = Field(default=None, max_length=100)
    youtube_url: str | None = Field(default=None, max_length=500)

    @field_validator("enabled_channels")
    @classmethod
    def validate_channels(cls, value: list[str]) -> list[str]:
        cleaned = list(dict.fromkeys(item.strip().lower() for item in value if item.strip()))
        invalid = set(cleaned) - ALLOWED_SHARE_CHANNELS
        if invalid:
            raise ValueError(f"Unsupported sharing channels: {', '.join(sorted(invalid))}")
        return cleaned

    @field_validator(
        "default_message",
        "whatsapp_number",
        "facebook_url",
        "instagram_url",
        "linkedin_url",
        "x_handle",
        "telegram_username",
        "youtube_url",
    )
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CompanySocialShareSettingsRead(CompanySocialShareSettingsUpdate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    company_id: UUID
    configured_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ExternalFileShareCreate(BaseModel):
    expires_in_hours: int | None = Field(default=None, ge=1, le=168)
    label: str | None = Field(default=None, max_length=180)
    allow_download: bool = True

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ExternalFileShareRead(BaseModel):
    id: UUID
    file_id: UUID
    company_id: UUID | None = None
    created_by_user_id: UUID | None = None
    label: str | None = None
    share_url: str | None = None
    expires_at: datetime
    revoked_at: datetime | None = None
    access_count: int
    allow_download: bool
    created_at: datetime
