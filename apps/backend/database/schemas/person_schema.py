from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from database.models.enums import (
    Gender,
    MaritalStatus,
)


class PersonBase(BaseModel):
    first_name: str = Field(
        min_length=1,
        max_length=100,
    )

    middle_name: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    last_name: str = Field(
        min_length=1,
        max_length=100,
    )

    gender: Optional[Gender] = None
    date_of_birth: Optional[date] = None

    national_id: Optional[str] = Field(
        default=None,
        max_length=50,
    )

    passport_number: Optional[str] = Field(
        default=None,
        max_length=50,
    )

    marital_status: Optional[MaritalStatus] = None
    nationality: Optional[str] = "Mosotho"
    district: Optional[str] = None
    town_or_village: Optional[str] = None
    physical_address: Optional[str] = None


class PersonCreate(PersonBase):
    user_id: UUID


class PersonUpdate(BaseModel):
    first_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    middle_name: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    last_name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    gender: Optional[Gender] = None
    date_of_birth: Optional[date] = None
    national_id: Optional[str] = None
    passport_number: Optional[str] = None
    marital_status: Optional[MaritalStatus] = None
    nationality: Optional[str] = None
    district: Optional[str] = None
    town_or_village: Optional[str] = None
    physical_address: Optional[str] = None

class PersonRead(BaseModel):
    id: UUID
    user_id: UUID

    first_name: str
    middle_name: Optional[str] = None
    last_name: str

    full_name: str

    gender: Optional[Gender] = None
    date_of_birth: Optional[date] = None

    national_id: Optional[str] = None
    passport_number: Optional[str] = None

    marital_status: Optional[MaritalStatus] = None
    nationality: Optional[str] = None

    district: Optional[str] = None
    town_or_village: Optional[str] = None
    physical_address: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True,
    }