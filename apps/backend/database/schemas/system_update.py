from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SystemUpdateStep(BaseModel):
    name: str
    status: str
    message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class SystemUpdateStatusRead(BaseModel):
    configured: bool = False
    state: str = "unavailable"
    message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    previous_image: str | None = None
    current_image: str | None = None
    target_image: str | None = None
    last_error: str | None = None
    steps: list[SystemUpdateStep] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class SystemUpdateCreate(BaseModel):
    confirmation: str = Field(min_length=1, max_length=20)
