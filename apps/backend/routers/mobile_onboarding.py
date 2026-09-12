from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import hash_password
from database.models.borrower import Borrower
from database.models.enums import EmploymentStatus, UserRole
from database.models.person import Person
from database.models.user import User
from database.session import get_db


router = APIRouter(prefix="/mobile-onboarding", tags=["Mobile Onboarding"])


class InterestedClientCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=7, max_length=30)
    password: str = Field(min_length=8, max_length=128)
    email: str | None = Field(default=None, max_length=255)

    @field_validator("first_name", "last_name", "phone", "password")
    @classmethod
    def trim_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field is required")
        return cleaned

    @field_validator("email")
    @classmethod
    def trim_email(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned or None


class InterestedClientRead(BaseModel):
    user_id: str
    borrower_id: str
    phone: str
    role: str
    profile_status: str
    message: str


@router.post(
    "/interested-client",
    response_model=InterestedClientRead,
    status_code=status.HTTP_201_CREATED,
)
def register_interested_client(
    payload: InterestedClientCreate,
    db: Session = Depends(get_db),
):
    filters = [User.phone == payload.phone]
    if payload.email:
        filters.append(User.email == payload.email)
    existing = db.query(User).filter(or_(*filters)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This phone number or email is already registered. Sign in to the existing LoanHub account.",
        )

    try:
        user = User(
            phone=payload.phone,
            email=payload.email,
            password_hash=hash_password(payload.password),
            role=UserRole.BORROWER,
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.flush()

        person = Person(
            user_id=user.id,
            first_name=payload.first_name,
            last_name=payload.last_name,
            nationality="Mosotho",
        )
        db.add(person)
        db.flush()

        # Interested clients start with a deliberately incomplete borrower
        # profile. Loan applications remain subject to the normal profile,
        # document, affordability, consent and credit-assessment requirements.
        borrower = Borrower(
            user_id=user.id,
            employment_status=EmploymentStatus.UNEMPLOYED,
            other_monthly_income=0,
            monthly_living_expenses=0,
            monthly_debt_repayments=0,
            dependants=0,
            has_existing_loans=False,
            existing_loan_total=0,
            consent_to_share_profile=False,
            consent_to_share_documents=False,
            consent_to_credit_checks=False,
        )
        db.add(borrower)
        db.commit()
        db.refresh(borrower)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="That LoanHub account already exists.",
        ) from exc

    return InterestedClientRead(
        user_id=str(user.id),
        borrower_id=str(borrower.id),
        phone=user.phone,
        role=user.role.value,
        profile_status="interested_client",
        message=(
            "LoanHub account created. You can sign in, chat with LoanHub and explore services. "
            "Complete your borrower profile before applying for credit."
        ),
    )
