from uuid import UUID
from typing import Optional
from pydantic import BaseModel, EmailStr


class CompanyBranchBase(BaseModel):
    company_id: UUID
    name: str
    district: str
    town: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: bool = True
    is_headquarters: bool = False


class CompanyBranchCreate(CompanyBranchBase):
    pass


class CompanyBranchUpdate(BaseModel):
    company_id: Optional[UUID] = None
    name: Optional[str] = None
    district: Optional[str] = None
    town: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    is_active: Optional[bool] = None
    is_headquarters: Optional[bool] = None


class CompanyBranchRead(CompanyBranchBase):
    id: UUID

    model_config = {
        "from_attributes": True
    }