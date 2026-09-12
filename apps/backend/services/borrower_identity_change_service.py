from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from database.models.audit_log import AuditLog
from database.models.company_client_identity_change import CompanyClientIdentityChangeRequest
from database.models.company_staff import CompanyStaff
from database.models.enums import NotificationType, UserRole
from database.models.notification import Notification
from database.models.origination import BorrowerKYCProfile
from database.models.person import Person
from database.models.user import User
from database.schemas.company_clients import CompanyClientNationalIdChangeRequestRead


PENDING_STATUS = "pending"
FINAL_STATUSES = {"applied", "rejected", "cancelled", "expired", "stale"}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalise_national_id(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = "".join(str(value).strip().split())
    return cleaned or None


def national_id_change_reference() -> str:
    return f"NID{utcnow():%y%m%d}{secrets.token_hex(3).upper()}"


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def expire_request_if_needed(row: CompanyClientIdentityChangeRequest) -> bool:
    if row.status == PENDING_STATUS and _aware(row.expires_at) <= utcnow():
        row.status = "expired"
        return True
    return False


def serialize_identity_change_request(
    row: CompanyClientIdentityChangeRequest,
) -> CompanyClientNationalIdChangeRequestRead:
    expire_request_if_needed(row)
    return CompanyClientNationalIdChangeRequestRead(
        id=row.id,
        reference=row.reference,
        company_id=row.company_id,
        branch_id=row.branch_id,
        company_borrower_account_id=row.company_borrower_account_id,
        borrower_id=row.borrower_id,
        current_national_id=row.current_national_id,
        proposed_national_id=row.proposed_national_id,
        reason=row.reason,
        status=row.status,
        borrower_approved_at=row.borrower_approved_at,
        company_owner_approved_at=row.company_owner_approved_at,
        rejected_at=row.rejected_at,
        rejected_by_role=row.rejected_by_role,
        rejection_reason=row.rejection_reason,
        applied_at=row.applied_at,
        expires_at=row.expires_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def assert_national_id_available(
    db: Session,
    *,
    proposed_national_id: str,
    exclude_person_id: UUID,
) -> None:
    duplicate = (
        db.query(Person.id)
        .filter(
            Person.id != exclude_person_id,
            func.lower(func.trim(Person.national_id)) == proposed_national_id.lower(),
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The proposed National ID is already linked to another LoanHub person",
        )


def _company_owner_user_ids(db: Session, company_id: UUID) -> list[UUID]:
    return [
        user_id
        for (user_id,) in (
            db.query(CompanyStaff.user_id)
            .join(User, User.id == CompanyStaff.user_id)
            .filter(
                CompanyStaff.company_id == company_id,
                CompanyStaff.role == UserRole.COMPANY_OWNER,
                CompanyStaff.is_active.is_(True),
                User.is_active.is_(True),
            )
            .distinct()
            .all()
        )
    ]


def _add_notification(
    db: Session,
    *,
    user_id: UUID,
    actor_user_id: UUID | None,
    row: CompanyClientIdentityChangeRequest,
    title: str,
    message: str,
    action_url: str,
    event_type: str,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            actor_user_id=actor_user_id,
            company_id=row.company_id,
            branch_id=row.branch_id,
            title=title,
            message=message,
            notification_type=NotificationType.SYSTEM,
            event_type=event_type,
            action="review",
            entity_type="company_client_identity_change_request",
            entity_id=str(row.id),
            action_url=action_url,
            icon="id-card",
            priority="high",
            deduplication_key=f"{event_type}:{row.id}:{user_id}",
            data={
                "reference": row.reference,
                "account_id": str(row.company_borrower_account_id),
                "proposed_national_id": row.proposed_national_id,
            },
        )
    )


def notify_request_created(
    db: Session,
    *,
    row: CompanyClientIdentityChangeRequest,
    borrower_user_id: UUID,
    actor_user_id: UUID,
) -> None:
    _add_notification(
        db,
        user_id=borrower_user_id,
        actor_user_id=actor_user_id,
        row=row,
        title="National ID change requires your approval",
        message=(
            f"Request {row.reference} proposes changing the National ID on your LoanHub profile. "
            "Review and approve or reject it from My Account."
        ),
        action_url="/borrower/account",
        event_type="borrower.identity_change.borrower_review_required",
    )
    for owner_user_id in _company_owner_user_ids(db, row.company_id):
        _add_notification(
            db,
            user_id=owner_user_id,
            actor_user_id=actor_user_id,
            row=row,
            title="Borrower National ID change requires owner approval",
            message=(
                f"Request {row.reference} requires a company-owner decision. "
                "The identity will not change until both approvals are recorded."
            ),
            action_url="/company/clients",
            event_type="borrower.identity_change.company_owner_review_required",
        )


def _audit(
    db: Session,
    *,
    row: CompanyClientIdentityChangeRequest,
    user_id: UUID | None,
    actor_role: str,
    action: str,
    description: str,
    before_data: dict | None = None,
    after_data: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            company_id=row.company_id,
            branch_id=row.branch_id,
            action=action,
            table_name="people",
            entity_type="borrower_identity",
            record_id=row.person_id,
            description=description,
            actor_role=actor_role,
            severity="high" if action.endswith("applied") else "info",
            status="success",
            before_data=before_data or {},
            after_data=after_data or {},
            changed_fields=["national_id"],
            event_data={
                "request_id": str(row.id),
                "request_reference": row.reference,
                "account_id": str(row.company_borrower_account_id),
            },
        )
    )


def create_identity_change_request(
    db: Session,
    *,
    company_id: UUID,
    branch_id: UUID | None,
    account_id: UUID,
    borrower_id: UUID,
    person: Person,
    requested_by_user_id: UUID,
    proposed_national_id: str,
    reason: str,
) -> CompanyClientIdentityChangeRequest:
    proposed = normalise_national_id(proposed_national_id)
    current = normalise_national_id(person.national_id)
    if not proposed:
        raise HTTPException(status_code=422, detail="A proposed National ID is required")
    if proposed == current:
        raise HTTPException(status_code=409, detail="The proposed National ID matches the current value")
    assert_national_id_available(db, proposed_national_id=proposed, exclude_person_id=person.id)

    pending = (
        db.query(CompanyClientIdentityChangeRequest)
        .filter(
            CompanyClientIdentityChangeRequest.company_borrower_account_id == account_id,
            CompanyClientIdentityChangeRequest.status == PENDING_STATUS,
        )
        .first()
    )
    if pending:
        expire_request_if_needed(pending)
        if pending.status == PENDING_STATUS:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"National ID change request {pending.reference} is already pending",
            )

    row = CompanyClientIdentityChangeRequest(
        reference=national_id_change_reference(),
        company_id=company_id,
        branch_id=branch_id,
        company_borrower_account_id=account_id,
        borrower_id=borrower_id,
        person_id=person.id,
        requested_by_user_id=requested_by_user_id,
        current_national_id=current,
        proposed_national_id=proposed,
        reason=reason.strip(),
        status=PENDING_STATUS,
        expires_at=utcnow() + timedelta(days=30),
    )
    db.add(row)
    db.flush()
    notify_request_created(
        db,
        row=row,
        borrower_user_id=person.user_id,
        actor_user_id=requested_by_user_id,
    )
    _audit(
        db,
        row=row,
        user_id=requested_by_user_id,
        actor_role="company_staff",
        action="borrower.identity_change.requested",
        description="A dual-approval National ID change was requested.",
        before_data={"national_id": current},
        after_data={"proposed_national_id": proposed},
    )
    return row


def reject_identity_change_request(
    db: Session,
    *,
    row: CompanyClientIdentityChangeRequest,
    user_id: UUID,
    actor_role: str,
    reason: str | None,
) -> CompanyClientIdentityChangeRequest:
    if expire_request_if_needed(row) or row.status != PENDING_STATUS:
        raise HTTPException(status_code=409, detail="This National ID change request is no longer pending")
    row.status = "rejected"
    row.rejected_at = utcnow()
    row.rejected_by_user_id = user_id
    row.rejected_by_role = actor_role
    row.rejection_reason = (reason or "").strip() or None
    _audit(
        db,
        row=row,
        user_id=user_id,
        actor_role=actor_role,
        action="borrower.identity_change.rejected",
        description="The proposed National ID change was rejected.",
    )
    return row


def apply_identity_change_if_ready(
    db: Session,
    *,
    row: CompanyClientIdentityChangeRequest,
    actor_user_id: UUID,
) -> bool:
    if row.status != PENDING_STATUS:
        return False
    if not row.borrower_approved_at or not row.company_owner_approved_at:
        return False

    person = db.query(Person).filter(Person.id == row.person_id).with_for_update().first()
    if person is None:
        row.status = "stale"
        return False
    current = normalise_national_id(person.national_id)
    if current != normalise_national_id(row.current_national_id):
        row.status = "stale"
        return False

    assert_national_id_available(
        db,
        proposed_national_id=row.proposed_national_id,
        exclude_person_id=person.id,
    )
    before_value = person.national_id
    person.national_id = row.proposed_national_id
    if person.user:
        person.user.is_verified = False

    db.query(BorrowerKYCProfile).filter(
        BorrowerKYCProfile.borrower_id == row.borrower_id,
    ).update(
        {
            BorrowerKYCProfile.identity_verified: False,
            BorrowerKYCProfile.status: "requires_review",
            BorrowerKYCProfile.reviewed_at: None,
            BorrowerKYCProfile.reviewed_by_user_id: None,
        },
        synchronize_session=False,
    )

    row.status = "applied"
    row.applied_at = utcnow()
    row.applied_by_user_id = actor_user_id
    _audit(
        db,
        row=row,
        user_id=actor_user_id,
        actor_role="dual_approval",
        action="borrower.identity_change.applied",
        description="The National ID was changed after borrower and company-owner approval.",
        before_data={"national_id": before_value},
        after_data={"national_id": row.proposed_national_id, "verification_reset": True},
    )

    recipients = {person.user_id, *_company_owner_user_ids(db, row.company_id)}
    for recipient_id in recipients:
        _add_notification(
            db,
            user_id=recipient_id,
            actor_user_id=actor_user_id,
            row=row,
            title="National ID change completed",
            message=(
                f"Request {row.reference} was approved by the borrower and company owner. "
                "Identity verification has been reset for review."
            ),
            action_url=("/borrower/account" if recipient_id == person.user_id else "/company/clients"),
            event_type="borrower.identity_change.applied",
        )
    return True


def approve_as_borrower(
    db: Session,
    *,
    row: CompanyClientIdentityChangeRequest,
    borrower_user_id: UUID,
) -> CompanyClientIdentityChangeRequest:
    if expire_request_if_needed(row) or row.status != PENDING_STATUS:
        raise HTTPException(status_code=409, detail="This National ID change request is no longer pending")
    person = db.query(Person).filter(Person.id == row.person_id).first()
    if not person or person.user_id != borrower_user_id:
        raise HTTPException(status_code=403, detail="Only the borrower who owns this identity may approve it")
    if not row.borrower_approved_at:
        row.borrower_approved_at = utcnow()
        row.borrower_approved_by_user_id = borrower_user_id
        _audit(
            db,
            row=row,
            user_id=borrower_user_id,
            actor_role="borrower",
            action="borrower.identity_change.borrower_approved",
            description="The borrower approved the proposed National ID change.",
        )
    apply_identity_change_if_ready(db, row=row, actor_user_id=borrower_user_id)
    return row


def approve_as_company_owner(
    db: Session,
    *,
    row: CompanyClientIdentityChangeRequest,
    owner_user_id: UUID,
) -> CompanyClientIdentityChangeRequest:
    if expire_request_if_needed(row) or row.status != PENDING_STATUS:
        raise HTTPException(status_code=409, detail="This National ID change request is no longer pending")
    owner_membership = (
        db.query(CompanyStaff.id)
        .filter(
            CompanyStaff.company_id == row.company_id,
            CompanyStaff.user_id == owner_user_id,
            CompanyStaff.role == UserRole.COMPANY_OWNER,
            CompanyStaff.is_active.is_(True),
        )
        .first()
    )
    if not owner_membership:
        raise HTTPException(status_code=403, detail="Only an active company owner may approve this request")
    if not row.company_owner_approved_at:
        row.company_owner_approved_at = utcnow()
        row.company_owner_approved_by_user_id = owner_user_id
        _audit(
            db,
            row=row,
            user_id=owner_user_id,
            actor_role=UserRole.COMPANY_OWNER.value,
            action="borrower.identity_change.company_owner_approved",
            description="A company owner approved the proposed National ID change.",
        )
    apply_identity_change_if_ready(db, row=row, actor_user_id=owner_user_id)
    return row
