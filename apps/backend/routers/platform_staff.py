from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from core.access_control import require_platform_admin, require_platform_owner
from core.security import hash_password
from database.models.finance import PlatformStaffProfile
from database.models.person import Person
from database.models.user import User
from database.schemas.platform_staff import (
    PlatformStaffAccountCreate,
    PlatformStaffAccountRead,
    PlatformStaffAccountUpdate,
)
from database.session import get_db

router = APIRouter(prefix="/platform-staff", tags=["Platform Employee Management"])


def _read(profile: PlatformStaffProfile) -> PlatformStaffAccountRead:
    user = profile.user
    person = user.person
    first_name = person.first_name if person else ""
    middle_name = person.middle_name if person else None
    last_name = person.last_name if person else ""
    full_name = person.full_name if person else (user.email or user.phone)
    return PlatformStaffAccountRead(
        id=profile.id,
        user_id=user.id,
        email=user.email,
        phone=user.phone,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        full_name=full_name,
        role=user.role,
        job_title=profile.job_title,
        department=profile.department,
        permissions=profile.permissions or [],
        is_active=bool(profile.is_active and user.is_active),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def _query(db: Session):
    return db.query(PlatformStaffProfile).options(
        joinedload(PlatformStaffProfile.user).joinedload(User.person)
    )


@router.get("", response_model=list[PlatformStaffAccountRead])
def list_platform_staff(
    search: str | None = Query(default=None, max_length=150),
    db: Session = Depends(get_db),
    _: User = Depends(require_platform_admin),
):
    query = _query(db)
    if search:
        token = f"%{search.strip()}%"
        query = query.join(User, User.id == PlatformStaffProfile.user_id).outerjoin(
            Person, Person.user_id == User.id
        ).filter(or_(
            User.phone.ilike(token),
            User.email.ilike(token),
            Person.first_name.ilike(token),
            Person.last_name.ilike(token),
            PlatformStaffProfile.job_title.ilike(token),
            PlatformStaffProfile.department.ilike(token),
        ))
    return [_read(item) for item in query.order_by(PlatformStaffProfile.created_at.desc()).all()]


@router.post("", response_model=PlatformStaffAccountRead, status_code=status.HTTP_201_CREATED)
def create_platform_staff(
    payload: PlatformStaffAccountCreate,
    db: Session = Depends(get_db),
    owner: User = Depends(require_platform_owner),
):
    phone = payload.phone.strip()
    email = str(payload.email).strip().lower() if payload.email else None
    conditions = [User.phone == phone]
    if email:
        conditions.append(User.email == email)
    if db.query(User.id).filter(or_(*conditions)).first():
        raise HTTPException(status_code=409, detail="Phone or email already exists")
    try:
        user = User(
            email=email,
            phone=phone,
            password_hash=hash_password(payload.password),
            role=payload.role,
            is_active=payload.is_active,
            is_verified=False,
        )
        db.add(user)
        db.flush()
        db.add(Person(
            user_id=user.id,
            first_name=payload.first_name.strip(),
            middle_name=payload.middle_name.strip() if payload.middle_name else None,
            last_name=payload.last_name.strip(),
        ))
        profile = PlatformStaffProfile(
            user_id=user.id,
            job_title=payload.job_title.strip(),
            department=payload.department.strip() if payload.department else None,
            permissions=sorted(set(payload.permissions)),
            is_active=payload.is_active,
            created_by_user_id=owner.id,
        )
        db.add(profile)
        db.commit()
        loaded = _query(db).filter(PlatformStaffProfile.id == profile.id).first()
        return _read(loaded)
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Platform staff account details already exist") from error


@router.put("/{profile_id}", response_model=PlatformStaffAccountRead)
def update_platform_staff(
    profile_id: UUID,
    payload: PlatformStaffAccountUpdate,
    db: Session = Depends(get_db),
    owner: User = Depends(require_platform_owner),
):
    profile = _query(db).filter(PlatformStaffProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Platform staff account not found")
    if profile.user_id == owner.id and not payload.is_active:
        raise HTTPException(status_code=409, detail="You cannot disable your own platform-owner account")
    email = str(payload.email).strip().lower() if payload.email else None
    duplicate = db.query(User.id).filter(
        User.id != profile.user_id,
        or_(User.phone == payload.phone.strip(), User.email == email if email else False),
    ).first()
    if duplicate:
        raise HTTPException(status_code=409, detail="Phone or email already exists")
    profile.user.phone = payload.phone.strip()
    profile.user.email = email
    profile.user.role = payload.role
    profile.user.is_active = payload.is_active
    profile.is_active = payload.is_active
    profile.job_title = payload.job_title.strip()
    profile.department = payload.department.strip() if payload.department else None
    profile.permissions = sorted(set(payload.permissions))
    person = profile.user.person
    if not person:
        person = Person(user_id=profile.user_id, first_name="", last_name="")
        db.add(person)
    person.first_name = payload.first_name.strip()
    person.middle_name = payload.middle_name.strip() if payload.middle_name else None
    person.last_name = payload.last_name.strip()
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail="Phone or email already exists") from error
    loaded = _query(db).filter(PlatformStaffProfile.id == profile_id).first()
    return _read(loaded)


@router.patch("/{profile_id}/status", response_model=PlatformStaffAccountRead)
def update_platform_staff_status(
    profile_id: UUID,
    is_active: bool,
    db: Session = Depends(get_db),
    owner: User = Depends(require_platform_owner),
):
    profile = _query(db).filter(PlatformStaffProfile.id == profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Platform staff account not found")
    if profile.user_id == owner.id and not is_active:
        raise HTTPException(status_code=409, detail="You cannot disable your own platform-owner account")
    profile.is_active = is_active
    profile.user.is_active = is_active
    db.commit()
    loaded = _query(db).filter(PlatformStaffProfile.id == profile_id).first()
    return _read(loaded)
