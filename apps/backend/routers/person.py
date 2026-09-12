from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from core.access_control import (
    COMPANY_MANAGEMENT_ROLES,
    get_current_active_user,
    require_platform_admin,
    require_tenant_roles,
    resolve_tenant_context,
)
from database.models.company_staff import CompanyStaff
from database.models.enums import UserRole
from database.models.person import Person
from database.models.user import User
from database.schemas.person_schema import PersonCreate, PersonRead, PersonUpdate
from database.session import get_db


router = APIRouter(prefix="/people", tags=["People"])


def clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def person_or_404(db: Session, person_id: UUID) -> Person:
    person = db.query(Person).filter(Person.id == person_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


def assert_can_manage_person(
    db: Session,
    current_user: User,
    target_user_id: UUID,
    x_company_id: str | None,
    x_active_role: str | None = None,
) -> None:
    if current_user.role == UserRole.SUPERADMIN or current_user.id == target_user_id:
        return

    context = resolve_tenant_context(db, current_user, x_company_id, x_active_role)
    require_tenant_roles(context, COMPANY_MANAGEMENT_ROLES)
    target_membership = (
        db.query(CompanyStaff.id)
        .filter(
            CompanyStaff.user_id == target_user_id,
            CompanyStaff.company_id == context.company_id,
        )
        .first()
    )
    if not target_membership:
        raise HTTPException(status_code=403, detail="Target user does not belong to your company")


def ensure_unique_identity(
    db: Session,
    *,
    national_id: str | None,
    passport_number: str | None,
    exclude_person_id: UUID | None = None,
) -> None:
    filters = []
    if national_id:
        filters.append(Person.national_id == national_id)
    if passport_number:
        filters.append(Person.passport_number == passport_number)
    if not filters:
        return

    query = db.query(Person).filter(or_(*filters))
    if exclude_person_id:
        query = query.filter(Person.id != exclude_person_id)
    if query.first():
        raise HTTPException(status_code=409, detail="National ID or passport number already exists")


@router.get("/", response_model=list[PersonRead])
def list_people(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    return db.query(Person).order_by(Person.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/me", response_model=PersonRead)
def get_my_person(current_user: User = Depends(get_current_active_user)):
    if not current_user.person:
        raise HTTPException(status_code=404, detail="Person profile not found")
    return current_user.person


@router.get("/user/{user_id}", response_model=PersonRead)
def get_person_by_user_id(
    user_id: UUID,
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    assert_can_manage_person(db, current_user, user_id, x_company_id, x_active_role)
    person = db.query(Person).filter(Person.user_id == user_id).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person profile not found")
    return person


@router.get("/{person_id}", response_model=PersonRead)
def get_person(
    person_id: UUID,
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    person = person_or_404(db, person_id)
    assert_can_manage_person(db, current_user, person.user_id, x_company_id, x_active_role)
    return person


@router.post("/", response_model=PersonRead, status_code=status.HTTP_201_CREATED)
def create_person(
    payload: PersonCreate,
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    assert_can_manage_person(db, current_user, payload.user_id, x_company_id, x_active_role)
    user = db.query(User).filter(User.id == payload.user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if db.query(Person).filter(Person.user_id == payload.user_id).first():
        raise HTTPException(status_code=409, detail="This user already has a person profile")

    data = payload.model_dump()
    data["national_id"] = clean_optional_string(payload.national_id)
    data["passport_number"] = clean_optional_string(payload.passport_number)
    ensure_unique_identity(
        db,
        national_id=data["national_id"],
        passport_number=data["passport_number"],
    )

    person = Person(**data)
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


@router.put("/{person_id}", response_model=PersonRead)
def update_person(
    person_id: UUID,
    payload: PersonUpdate,
    x_company_id: str | None = Header(default=None, alias="X-Company-ID"),
    x_active_role: str | None = Header(default=None, alias="X-Active-Role"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    person = person_or_404(db, person_id)
    assert_can_manage_person(db, current_user, person.user_id, x_company_id, x_active_role)

    changes = payload.model_dump(exclude_unset=True)
    if "national_id" in changes:
        changes["national_id"] = clean_optional_string(changes["national_id"])
    if "passport_number" in changes:
        changes["passport_number"] = clean_optional_string(changes["passport_number"])

    ensure_unique_identity(
        db,
        national_id=changes.get("national_id", person.national_id),
        passport_number=changes.get("passport_number", person.passport_number),
        exclude_person_id=person.id,
    )

    for field, value in changes.items():
        setattr(person, field, value)
    db.commit()
    db.refresh(person)
    return person


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(
    person_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    person = person_or_404(db, person_id)
    db.delete(person)
    db.commit()
