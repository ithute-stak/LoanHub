from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from database.models.enums import UserRole


class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    phone: str
    role: UserRole
    is_active: bool = True
    is_verified: bool = False
    must_change_password: bool = False


class UserCreate(UserBase):
    password_hash: str


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password_hash: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserRead(UserBase):
    id: UUID
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
