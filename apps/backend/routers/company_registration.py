from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import hash_password
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.enums import CompanyStatus, UserRole
from database.models.institution_governance import InstitutionGovernanceProfile
from database.models.person import Person
from database.models.user import User
from database.schemas.company_registration import CompanyOwnerRegistrationCreate, CompanyOwnerRegistrationRead
from database.session import get_db


router = APIRouter(prefix="/company-registration", tags=["Company Registration"])


@router.post("/", response_model=CompanyOwnerRegistrationRead, status_code=status.HTTP_201_CREATED)
def register_company_owner(
    payload: CompanyOwnerRegistrationCreate,
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(User)
        .filter(
            or_(
                User.phone == payload.owner_phone.strip(),
                User.email == payload.owner_email if payload.owner_email else False,
            )
        )
        .first()
    )
    if existing_user:
        raise HTTPException(status_code=409, detail="Owner phone or email already exists")

    existing_company = (
        db.query(LoanCompany)
        .filter(
            or_(
                LoanCompany.name == payload.company_name.strip(),
                LoanCompany.registration_number == payload.registration_number
                if payload.registration_number
                else False,
            )
        )
        .first()
    )
    if existing_company:
        raise HTTPException(status_code=409, detail="Company already exists")

    try:
        company = LoanCompany(
            name=payload.company_name.strip(),
            institution_type=payload.institution_type,
            registration_number=payload.registration_number,
            license_number=payload.license_number,
            phone=payload.company_phone.strip(),
            email=str(payload.company_email) if payload.company_email else None,
            website=payload.website,
            address=payload.address,
            district=payload.district,
            status=CompanyStatus.PENDING,
            is_active=False,
        )
        db.add(company)
        db.flush()
        db.add(InstitutionGovernanceProfile(company_id=company.id))

        user = User(
            email=str(payload.owner_email) if payload.owner_email else None,
            phone=payload.owner_phone.strip(),
            password_hash=hash_password(payload.password),
            role=UserRole.COMPANY_OWNER,
            is_active=True,
            is_verified=False,
        )
        db.add(user)
        db.flush()

        person = Person(
            user_id=user.id,
            first_name=payload.first_name.strip(),
            middle_name=payload.middle_name,
            last_name=payload.last_name.strip(),
            gender=payload.gender,
            date_of_birth=payload.date_of_birth,
            national_id=payload.national_id,
            passport_number=payload.passport_number,
            marital_status=payload.marital_status,
            nationality=payload.nationality,
            district=payload.district,
            town_or_village=payload.town_or_village,
            physical_address=payload.physical_address,
        )
        db.add(person)

        membership = CompanyStaff(
            user_id=user.id,
            company_id=company.id,
            branch_id=None,
            role=UserRole.COMPANY_OWNER,
            is_active=True,
        )
        db.add(membership)
        db.commit()
        db.refresh(membership)

        return CompanyOwnerRegistrationRead(
            company_id=company.id,
            institution_type=company.institution_type,
            owner_user_id=user.id,
            staff_membership_id=membership.id,
            status=company.status.value,
            message=f"{company.institution_type.value.replace('_', ' ').title()} account submitted for platform approval",
        )
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Registration details already exist") from error
    except Exception:
        db.rollback()
        raise
