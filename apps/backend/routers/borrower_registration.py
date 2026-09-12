from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.security import hash_password
from database.models.borrower import Borrower
from database.models.enums import UserRole
from database.models.person import Person
from database.models.user import User
from database.schemas.borrower_registration import (
    BorrowerRegistrationCreate,
    BorrowerRegistrationResponse,
)
from database.session import get_db
from services.employer_group_service import resolve_employer_group


router = APIRouter(
    prefix="/borrower-registration",
    tags=["Borrower Registration"],
)


def clean_optional_string(
    value: str | None,
) -> str | None:
    if value is None:
        return None

    cleaned = str(value).strip()

    return cleaned or None


def registration_conflict(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=message,
    )


@router.post(
    "/",
    response_model=BorrowerRegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_borrower(
    payload: BorrowerRegistrationCreate,
    db: Session = Depends(get_db),
):
    phone = payload.phone.strip()
    email = clean_optional_string(
        str(payload.email)
        if payload.email
        else None,
    )

    national_id = clean_optional_string(
        payload.national_id,
    )

    passport_number = clean_optional_string(
        payload.passport_number,
    )

    user_filters = [
        User.phone == phone,
    ]

    if email:
        user_filters.append(
            User.email == email,
        )

    existing_user = (
        db.query(User)
        .filter(or_(*user_filters))
        .first()
    )

    if existing_user:
        if existing_user.phone == phone:
            raise registration_conflict(
                "This phone number is already registered. "
                "Sign in with the existing account instead, or use "
                "Forgot password if you cannot access it."
            )

        raise registration_conflict(
            "This email address is already registered. "
            "Sign in with the existing account instead, or use "
            "Forgot password if you cannot access it."
        )

    person_filters = []

    if national_id:
        person_filters.append(
            Person.national_id == national_id,
        )

    if passport_number:
        person_filters.append(
            Person.passport_number == passport_number,
        )

    if person_filters:
        existing_person = (
            db.query(Person)
            .filter(or_(*person_filters))
            .first()
        )

        if existing_person:
            raise registration_conflict(
                "This national ID or passport is already linked to a "
                "LoanHub borrower profile. Do not create a second profile; "
                "sign in or recover the existing account."
            )

    try:
        employer_group = resolve_employer_group(
            db,
            employer_group_id=payload.employer_group_id,
            new_employer_group=payload.new_employer_group,
        )

        user = User(
            email=email,
            phone=phone,
            password_hash=hash_password(
                payload.password_hash,
            ),
            role=UserRole.BORROWER,
            is_active=True,
            is_verified=False,
        )

        db.add(user)
        db.flush()

        person = Person(
            user_id=user.id,
            first_name=payload.first_name.strip(),
            middle_name=clean_optional_string(
                payload.middle_name,
            ),
            last_name=payload.last_name.strip(),
            gender=payload.gender,
            date_of_birth=payload.date_of_birth,
            national_id=national_id,
            passport_number=passport_number,
            marital_status=payload.marital_status,
            nationality=payload.nationality,
            district=payload.district,
            town_or_village=clean_optional_string(
                payload.town_or_village,
            ),
            physical_address=clean_optional_string(
                payload.physical_address,
            ),
        )

        db.add(person)
        db.flush()

        borrower = Borrower(
            user_id=user.id,
            employment_status=payload.employment_status,
            employer_name=(
                employer_group.name
                if employer_group is not None
                else clean_optional_string(payload.employer_name)
            ),
            employer_group_id=(employer_group.id if employer_group is not None else None),
            income_day=payload.income_day,
            job_title=clean_optional_string(
                payload.job_title,
            ),
            monthly_income=payload.monthly_income,
            salary_date=(
                str(payload.income_day)
                if payload.income_day is not None
                else clean_optional_string(payload.salary_date)
            ),
            has_existing_loans=(
                payload.has_existing_loans
            ),
            existing_loan_total=(
                payload.existing_loan_total
            ),
            consent_to_share_profile=(
                payload.consent_to_share_profile
            ),
            consent_to_credit_checks=(
                payload.consent_to_credit_checks
            ),
        )

        db.add(borrower)

        db.commit()

        db.refresh(user)
        db.refresh(person)
        db.refresh(borrower)

        return BorrowerRegistrationResponse(
            user_id=user.id,
            person_id=person.id,
            borrower_id=borrower.id,
            email=user.email,
            phone=user.phone,
            role=user.role,
            first_name=person.first_name,
            last_name=person.last_name,
            district=person.district,
            created_at=person.created_at,
        )

    except IntegrityError as error:
        db.rollback()

        raise registration_conflict(
            "These details match an existing LoanHub account or borrower "
            "profile. Sign in instead, or use Forgot password if you cannot "
            "access the existing account."
        ) from error

    except Exception:
        db.rollback()
        raise
