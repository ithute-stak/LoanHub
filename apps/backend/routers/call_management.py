from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.access_control import COMPANY_MANAGEMENT_ROLES, TenantContext, get_user_context
from database.config.config import settings
from database.models.borrower import Borrower
from database.models.borrower_contact import BorrowerContact
from database.models.call_management import (
    CallManagementPolicy,
    CallQualityReview,
    CallRecording,
    ClientCall,
    EmployeeCallDevice,
    RecordingLegalHold,
)
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_staff import CompanyStaff
from database.models.enums import UserRole
from database.models.user import User
from database.schemas.call_management import (
    CallCreateRequest,
    CallDescriptionUpdateRequest,
    CallManagementPolicyUpdate,
    CallQualityReviewRequest,
    CallUpdateRequest,
    DeviceRegistrationRequest,
    LegalHoldCreateRequest,
)
from database.session import get_db
from services.call_management_service import (
    get_or_create_policy,
    issue_livekit_token,
    live_media_configured,
    normalize_lesotho_phone,
    policy_payload,
    recording_deletion_at,
    write_sensitive_audit,
)
from services.object_storage_service import StorageUnavailableError, get_storage
from services.file_service import read_file_bytes, save_upload


router = APIRouter(prefix="/call-management", tags=["Call Management and Quality Assurance"])

CALL_AGENT_ROLES: set[UserRole] = COMPANY_MANAGEMENT_ROLES | {
    UserRole.BRANCH_MANAGER,
    UserRole.LOAN_OFFICER,
    UserRole.COLLECTIONS_OFFICER,
    UserRole.CUSTOMER_SUPPORT,
    UserRole.OPERATIONS_OFFICER,
}
CALL_REVIEW_ROLES: set[UserRole] = COMPANY_MANAGEMENT_ROLES | {
    UserRole.BRANCH_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
    UserRole.PERFORMANCE_MANAGER,
    UserRole.RISK_MANAGER,
}
CALL_HOLD_ROLES: set[UserRole] = COMPANY_MANAGEMENT_ROLES | {
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
}
CALL_DELETE_ROLES: set[UserRole] = {UserRole.COMPANY_OWNER}
ALL_CALL_ROLES = CALL_AGENT_ROLES | CALL_REVIEW_ROLES
ACTIVE_CALL_STATUSES = {"started", "ringing", "answered"}

class BorrowerContactCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    relationship: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=7, max_length=32)
    is_call_permitted: bool = True



def _company_id(context: TenantContext, allowed_roles: set[UserRole]) -> UUID:
    if context.is_platform_admin:
        raise HTTPException(status_code=400, detail="Select a company-scoped account for call management")
    if not context.company_id or not context.staff:
        raise HTTPException(status_code=403, detail="An active company staff membership is required")
    if context.role not in allowed_roles:
        raise HTTPException(status_code=403, detail="The active role is not allowed to use this call-management operation")
    return context.company_id


def _branch_limited(context: TenantContext) -> bool:
    return bool(context.branch_id and context.role not in COMPANY_MANAGEMENT_ROLES)


def _display_user(user: User | None) -> str | None:
    if not user:
        return None
    if user.person:
        return user.person.full_name
    return user.email or user.phone


def _staff_name(staff: CompanyStaff | None) -> str | None:
    return _display_user(staff.user) if staff else None


def _recording_payload(recording: CallRecording | None) -> dict | None:
    if not recording:
        return None
    active_hold = next((hold for hold in recording.legal_holds if hold.status == "active"), None)
    return {
        "id": str(recording.id),
        "status": recording.status,
        "mime_type": recording.mime_type,
        "size_bytes": recording.size_bytes,
        "duration_seconds": recording.duration_seconds,
        "deletion_at": recording.deletion_at.isoformat() if recording.deletion_at else None,
        "deleted_at": recording.deleted_at.isoformat() if recording.deleted_at else None,
        "legal_hold": (
            {
                "id": str(active_hold.id),
                "reason": active_hold.reason,
                "placed_at": active_hold.placed_at.isoformat() if active_hold.placed_at else None,
            }
            if active_hold
            else None
        ),
    }


def _review_payload(review: CallQualityReview) -> dict:
    return {
        "id": str(review.id),
        "call_id": str(review.call_id),
        "reviewer_user_id": str(review.reviewer_user_id) if review.reviewer_user_id else None,
        "reviewer_name": _display_user(review.reviewer),
        "score": review.score,
        "compliance_status": review.compliance_status,
        "customer_care_status": review.customer_care_status,
        "notes": review.notes,
        "reviewed_at": review.reviewed_at.isoformat() if review.reviewed_at else None,
    }


def _call_payload(call: ClientCall, context: TenantContext | None = None) -> dict:
    borrower = call.borrower
    borrower_user = borrower.user if borrower else None
    loan = call.loan
    reviews = sorted(call.quality_reviews, key=lambda row: row.reviewed_at or datetime.min, reverse=True)
    return {
        "id": str(call.id),
        "company_id": str(call.company_id),
        "branch_id": str(call.branch_id) if call.branch_id else None,
        "employee_staff_id": str(call.employee_staff_id),
        "employee_name": _staff_name(call.employee_staff),
        "device_id": str(call.device_id) if call.device_id else None,
        "borrower_id": str(call.borrower_id) if call.borrower_id else None,
        "borrower_name": _display_user(borrower_user),
        "phone_number": call.phone_number,
        "normalized_phone": call.normalized_phone,
        "loan_id": str(call.loan_id) if call.loan_id else None,
        "loan_reference": loan.loan_reference if loan else None,
        "loan_balance": float(loan.balance or 0) if loan else None,
        "direction": call.direction,
        "status": call.status,
        "started_at": call.started_at.isoformat() if call.started_at else None,
        "answered_at": call.answered_at.isoformat() if call.answered_at else None,
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "duration_seconds": call.duration_seconds,
        "recording_status": call.recording_status,
        "outcome": call.outcome,
        "notes": call.notes,
        "is_live": call.ended_at is None and call.status in ACTIVE_CALL_STATUSES,
        "recording": _recording_payload(call.recording),
        "quality_reviews": [_review_payload(item) for item in reviews],
        "permissions": {
            "can_edit_description": bool(context and context.staff and call.employee_staff_id == context.staff.id),
            "can_delete": bool(context and context.role in CALL_DELETE_ROLES),
        } if context else None,
    }


def _device_payload(row: EmployeeCallDevice) -> dict:
    return {
        "id": str(row.id),
        "company_id": str(row.company_id),
        "branch_id": str(row.branch_id) if row.branch_id else None,
        "staff_id": str(row.staff_id),
        "employee_name": _staff_name(row.staff),
        "device_uuid": row.device_uuid,
        "device_name": row.device_name,
        "platform": row.platform,
        "os_version": row.os_version,
        "app_version": row.app_version,
        "status": row.status,
        "registered_at": row.registered_at.isoformat() if row.registered_at else None,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
    }


def _call_or_404(db: Session, context: TenantContext, call_id: UUID, roles: set[UserRole]) -> ClientCall:
    company_id = _company_id(context, roles)
    call = db.query(ClientCall).filter(
        ClientCall.id == call_id,
        ClientCall.company_id == company_id,
    ).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if _branch_limited(context) and call.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="Call is outside the active branch")
    return call


def _recording_or_404(db: Session, context: TenantContext, recording_id: UUID, roles: set[UserRole]) -> CallRecording:
    company_id = _company_id(context, roles)
    recording = db.query(CallRecording).filter(
        CallRecording.id == recording_id,
        CallRecording.company_id == company_id,
    ).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")
    call = db.get(ClientCall, recording.call_id)
    if _branch_limited(context) and call and call.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="Recording is outside the active branch")
    return recording


def _seconds_between(started_at: datetime, ended_at: datetime) -> int:
    left = started_at
    right = ended_at
    if left.tzinfo is None and right.tzinfo is not None:
        right = right.replace(tzinfo=None)
    elif left.tzinfo is not None and right.tzinfo is None:
        right = right.replace(tzinfo=left.tzinfo)
    return max(0, int((right - left).total_seconds()))


def _loan_for_company(db: Session, context: TenantContext, loan_id: UUID) -> ClientCompanyLoan:
    company_id = _company_id(context, CALL_AGENT_ROLES)
    loan = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.id == loan_id,
        ClientCompanyLoan.company_id == company_id,
    ).first()
    if not loan:
        raise HTTPException(status_code=404, detail="Loan not found in the active company")
    if _branch_limited(context) and loan.branch_id != context.branch_id:
        raise HTTPException(status_code=403, detail="Loan is outside the active branch")
    return loan


def _auto_match_phone(db: Session, context: TenantContext, normalized_phone: str) -> tuple[UUID | None, UUID | None]:
    company_id = _company_id(context, CALL_AGENT_ROLES)
    query = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.company_id == company_id)
    if _branch_limited(context):
        query = query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    matches: list[ClientCompanyLoan] = []
    for loan in query.order_by(ClientCompanyLoan.created_at.desc()).limit(2000).all():
        borrower = loan.borrower
        user = borrower.user if borrower else None
        if not user or not user.phone:
            continue
        try:
            candidate = normalize_lesotho_phone(user.phone)
        except ValueError:
            continue
        if candidate == normalized_phone:
            matches.append(loan)

    borrower_ids = {row.borrower_id for row in matches}
    if len(borrower_ids) != 1:
        return None, None
    borrower_id = next(iter(borrower_ids))
    loan_id = matches[0].id if len(matches) == 1 else None
    return borrower_id, loan_id


@router.get("/mobile/bootstrap")
def mobile_bootstrap(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, CALL_AGENT_ROLES)
    policy = get_or_create_policy(db, company_id)
    db.commit()
    return {
        "employee": {
            "staff_id": str(context.staff.id),
            "user_id": str(context.user.id),
            "name": _staff_name(context.staff),
            "role": context.role.value,
            "company_id": str(company_id),
            "company_name": context.company.name if context.company else None,
            "branch_id": str(context.branch_id) if context.branch_id else None,
        },
        "policy": policy_payload(policy),
        "media": {
            "provider": settings.CALL_MEDIA_PROVIDER,
            "configured": live_media_configured(),
            "controlled_calling_required_for_reliable_recording": True,
        },
    }


@router.post("/devices/register")
def register_device(
    payload: DeviceRegistrationRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, CALL_AGENT_ROLES)
    now = datetime.now(timezone.utc)
    row = db.query(EmployeeCallDevice).filter(
        EmployeeCallDevice.company_id == company_id,
        EmployeeCallDevice.device_uuid == payload.device_uuid.strip(),
    ).first()
    if row and row.staff_id != context.staff.id:
        raise HTTPException(status_code=409, detail="This device is already assigned to another employee")
    if row and row.status == "revoked":
        raise HTTPException(status_code=403, detail="This device has been revoked by company management")
    if not row:
        row = EmployeeCallDevice(
            company_id=company_id,
            branch_id=context.branch_id,
            staff_id=context.staff.id,
            device_uuid=payload.device_uuid.strip(),
            registered_at=now,
        )
        db.add(row)
    row.device_name = payload.device_name
    row.platform = payload.platform.strip().lower()
    row.os_version = payload.os_version
    row.app_version = payload.app_version
    row.last_seen_at = now
    row.status = "active"
    db.commit()
    db.refresh(row)
    return _device_payload(row)


@router.get("/devices")
def list_devices(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, CALL_REVIEW_ROLES)
    query = db.query(EmployeeCallDevice).filter(EmployeeCallDevice.company_id == company_id)
    if _branch_limited(context):
        query = query.filter(EmployeeCallDevice.branch_id == context.branch_id)
    return [_device_payload(row) for row in query.order_by(EmployeeCallDevice.last_seen_at.desc()).all()]


@router.post("/devices/{device_id}/revoke")
def revoke_device(
    device_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, COMPANY_MANAGEMENT_ROLES)
    row = db.query(EmployeeCallDevice).filter(
        EmployeeCallDevice.id == device_id,
        EmployeeCallDevice.company_id == company_id,
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="Device not found")
    row.status = "revoked"
    row.revoked_at = datetime.now(timezone.utc)
    db.commit()
    return _device_payload(row)


@router.get("/clients")
def list_call_clients(
    search: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, CALL_AGENT_ROLES)
    query = db.query(ClientCompanyLoan).filter(ClientCompanyLoan.company_id == company_id)
    if _branch_limited(context):
        query = query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    rows = query.order_by(ClientCompanyLoan.created_at.desc()).limit(2000).all()

    clients: dict[UUID, dict] = {}
    for loan in rows:
        borrower = loan.borrower
        user = borrower.user if borrower else None
        if not borrower or not user:
            continue
        entry = clients.setdefault(
            borrower.id,
            {
                "borrower_id": str(borrower.id),
                "name": _display_user(user),
                "phone": user.phone,
                "loans": [],
            },
        )
        entry["loans"].append(
            {
                "id": str(loan.id),
                "loan_reference": loan.loan_reference,
                "status": loan.status.value if hasattr(loan.status, "value") else str(loan.status),
                "balance": float(loan.balance or 0),
                "is_overdue": bool(loan.is_overdue),
                "branch_id": str(loan.branch_id) if loan.branch_id else None,
            }
        )

    result = list(clients.values())
    token = (search or "").strip().lower()
    if token:
        result = [
            item
            for item in result
            if token in " ".join(
                [
                    str(item.get("name") or ""),
                    str(item.get("phone") or ""),
                    *[str(loan.get("loan_reference") or "") for loan in item["loans"]],
                ]
            ).lower()
        ]
    result.sort(key=lambda item: str(item.get("name") or "").lower())
    return result[:limit]


@router.get("/clients/{borrower_id}")
def get_call_client(
    borrower_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, CALL_AGENT_ROLES)
    loan_query = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.borrower_id == borrower_id,
    )
    if _branch_limited(context):
        loan_query = loan_query.filter(ClientCompanyLoan.branch_id == context.branch_id)
    loans = loan_query.order_by(ClientCompanyLoan.created_at.desc()).all()
    if not loans:
        raise HTTPException(status_code=404, detail="Client not found in the active company")
    borrower = db.get(Borrower, borrower_id)
    user = borrower.user if borrower else None
    call_query = db.query(ClientCall).filter(
        ClientCall.company_id == company_id,
        ClientCall.borrower_id == borrower_id,
    )
    if _branch_limited(context):
        call_query = call_query.filter(ClientCall.branch_id == context.branch_id)
    calls = call_query.order_by(ClientCall.started_at.desc()).limit(50).all()
    return {
        "borrower_id": str(borrower_id),
        "name": _display_user(user),
        "phone": user.phone if user else None,
        "contacts": (
            [
                {
                    "name": _display_user(user) or "Borrower",
                    "relationship": "Borrower",
                    "phone": user.phone,
                    "is_primary": True,
                    "is_call_permitted": True,
                }
            ]
            if user and user.phone
            else []
        )
        + [
            {
                "name": contact.full_name,
                "relationship": contact.relationship,
                "phone": contact.phone,
                "is_primary": contact.is_primary,
                "is_call_permitted": contact.is_call_permitted,
            }
            for contact in db.query(BorrowerContact)
            .filter(BorrowerContact.borrower_id == borrower_id)
            .order_by(BorrowerContact.is_primary.desc(), BorrowerContact.full_name.asc())
            .all()
        ],
        "loans": [
            {
                "id": str(loan.id),
                "loan_reference": loan.loan_reference,
                "status": loan.status.value if hasattr(loan.status, "value") else str(loan.status),
                "balance": float(loan.balance or 0),
                "is_overdue": bool(loan.is_overdue),
            }
            for loan in loans
        ],
        "recent_calls": [_call_payload(row) for row in calls],
    }


@router.post("/clients/{borrower_id}/contacts", status_code=status.HTTP_201_CREATED)
def add_call_client_contact(
    borrower_id: UUID,
    payload: BorrowerContactCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    # A company can maintain call contacts only for a borrower linked by one of
    # its loans. The contact remains part of the global borrower profile.
    company_id = _company_id(context, CALL_AGENT_ROLES)
    client_loan = db.query(ClientCompanyLoan).filter(
        ClientCompanyLoan.company_id == company_id,
        ClientCompanyLoan.borrower_id == borrower_id,
    )
    if _branch_limited(context):
        client_loan = client_loan.filter(ClientCompanyLoan.branch_id == context.branch_id)
    if not client_loan.first():
        raise HTTPException(status_code=404, detail="Client not found in the active company")
    try:
        phone = normalize_lesotho_phone(payload.phone)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    row = BorrowerContact(
        borrower_id=borrower_id,
        full_name=payload.full_name.strip(),
        relationship=payload.relationship.strip(),
        phone=phone,
        is_call_permitted=payload.is_call_permitted,
    )
    db.add(row)
    db.commit()
    return {
        "name": row.full_name,
        "relationship": row.relationship,
        "phone": row.phone,
        "is_primary": row.is_primary,
        "is_call_permitted": row.is_call_permitted,
    }


@router.post("/calls", status_code=status.HTTP_201_CREATED)
def create_call(
    payload: CallCreateRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, CALL_AGENT_ROLES)
    existing = db.query(ClientCall).filter(
        ClientCall.company_id == company_id,
        ClientCall.device_call_uuid == payload.device_call_uuid.strip(),
    ).first()
    if existing:
        return _call_payload(existing, context)

    try:
        normalized_phone = normalize_lesotho_phone(payload.phone_number)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

    device = None
    if payload.device_id:
        device = db.query(EmployeeCallDevice).filter(
            EmployeeCallDevice.id == payload.device_id,
            EmployeeCallDevice.company_id == company_id,
            EmployeeCallDevice.staff_id == context.staff.id,
        ).first()
        if not device or device.status != "active":
            raise HTTPException(status_code=403, detail="An active registered employee device is required")
        device.last_seen_at = datetime.now(timezone.utc)

    borrower_id = payload.borrower_id
    loan_id = payload.loan_id
    if payload.loan_id:
        loan = _loan_for_company(db, context, payload.loan_id)
        if payload.borrower_id and payload.borrower_id != loan.borrower_id:
            raise HTTPException(status_code=422, detail="The selected loan does not belong to the selected client")
        borrower_id = loan.borrower_id
    elif borrower_id:
        customer_loan_query = db.query(ClientCompanyLoan).filter(
            ClientCompanyLoan.company_id == company_id,
            ClientCompanyLoan.borrower_id == borrower_id,
        )
        if _branch_limited(context):
            customer_loan_query = customer_loan_query.filter(ClientCompanyLoan.branch_id == context.branch_id)
        if not customer_loan_query.first():
            raise HTTPException(status_code=404, detail="Client is not linked to the active company")
    elif payload.direction == "incoming":
        borrower_id, loan_id = _auto_match_phone(db, context, normalized_phone)

    if payload.direction == "outgoing" and not borrower_id:
        raise HTTPException(status_code=422, detail="Outgoing company calls must be linked to a LoanHub client")

    policy = get_or_create_policy(db, company_id)
    controlled_media = live_media_configured()
    recording_status = (
        "pending"
        if policy.recording_enabled and controlled_media
        else "disabled" if not policy.recording_enabled else "unavailable"
    )
    row = ClientCall(
        company_id=company_id,
        branch_id=context.branch_id,
        employee_staff_id=context.staff.id,
        device_id=device.id if device else None,
        borrower_id=borrower_id,
        loan_id=loan_id,
        device_call_uuid=payload.device_call_uuid.strip(),
        phone_number=payload.phone_number.strip(),
        normalized_phone=normalized_phone,
        direction=payload.direction,
        status=payload.status,
        started_at=payload.started_at,
        recording_status=recording_status,
        media_room_name=f"loanhub-call-{uuid4().hex}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _call_payload(row, context)


@router.patch("/calls/{call_id}")
def update_call(
    call_id: UUID,
    payload: CallUpdateRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    call = _call_or_404(db, context, call_id, CALL_AGENT_ROLES)
    if call.employee_staff_id != context.staff.id and context.role not in CALL_REVIEW_ROLES:
        raise HTTPException(status_code=403, detail="Employees may update only their own calls")

    if payload.status is not None:
        call.status = payload.status
    if payload.answered_at is not None:
        call.answered_at = payload.answered_at
    if payload.ended_at is not None:
        call.ended_at = payload.ended_at
    if payload.outcome is not None:
        call.outcome = payload.outcome
    if payload.notes is not None:
        if call.employee_staff_id != context.staff.id:
            raise HTTPException(status_code=403, detail="Only the employee who made the call can edit its description")
        call.notes = payload.notes.strip() or None
    if call.status in {"completed", "missed", "failed", "cancelled"} and call.ended_at is None:
        call.ended_at = datetime.now(timezone.utc)
    if call.ended_at:
        call.duration_seconds = _seconds_between(call.started_at, call.ended_at)
    db.commit()
    return _call_payload(call, context)


@router.put("/calls/{call_id}/description")
def update_call_description(
    call_id: UUID,
    payload: CallDescriptionUpdateRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Only the employee assigned to a call may amend their call description."""
    call = _call_or_404(db, context, call_id, CALL_AGENT_ROLES)
    if call.employee_staff_id != context.staff.id:
        raise HTTPException(status_code=403, detail="Only the employee who made the call can edit its description")
    call.notes = payload.description.strip() if payload.description and payload.description.strip() else None
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=call.company_id,
        branch_id=call.branch_id,
        action="CALL_DESCRIPTION_UPDATED",
        entity_type="client_call",
        record_id=call.id,
        description="The employee updated their call description",
        actor_role=context.role.value,
    )
    db.commit()
    db.refresh(call)
    return _call_payload(call, context)


@router.delete("/calls/{call_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_call(
    call_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Company owner-only deletion, including the private recording object."""
    company_id = _company_id(context, CALL_DELETE_ROLES)
    call = db.query(ClientCall).filter(
        ClientCall.id == call_id,
        ClientCall.company_id == company_id,
    ).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.ended_at is None and call.status in ACTIVE_CALL_STATUSES:
        raise HTTPException(status_code=409, detail="End an active call before deleting its record")

    recording = call.recording
    if recording and any(hold.status == "active" for hold in recording.legal_holds):
        raise HTTPException(status_code=409, detail="A call recording with an active legal hold cannot be deleted")
    managed_file = recording.managed_file if recording else None
    if managed_file:
        try:
            get_storage(managed_file.storage_provider or "local").delete(managed_file.storage_key)
        except StorageUnavailableError as error:
            raise HTTPException(status_code=503, detail="Recording storage is temporarily unavailable") from error

    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=call.company_id,
        branch_id=call.branch_id,
        action="CALL_DELETED_BY_COMPANY_OWNER",
        entity_type="client_call",
        record_id=call.id,
        description="Company owner permanently deleted a controlled call record and its recording",
        actor_role=context.role.value,
        event_data={"recording_deleted": bool(recording)},
    )
    db.delete(call)
    if managed_file:
        db.delete(managed_file)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/calls")
def list_calls(
    direction: str | None = None,
    call_status: str | None = Query(default=None, alias="status"),
    search: str | None = None,
    limit: int = Query(300, ge=1, le=1000),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, ALL_CALL_ROLES)
    query = db.query(ClientCall).filter(ClientCall.company_id == company_id)
    if _branch_limited(context):
        query = query.filter(ClientCall.branch_id == context.branch_id)
    if context.role not in CALL_REVIEW_ROLES:
        query = query.filter(ClientCall.employee_staff_id == context.staff.id)
    if direction:
        query = query.filter(ClientCall.direction == direction.strip().lower())
    if call_status:
        query = query.filter(ClientCall.status == call_status.strip().lower())
    rows = query.order_by(ClientCall.started_at.desc()).limit(limit).all()
    result = [_call_payload(row, context) for row in rows]
    token = (search or "").strip().lower()
    if token:
        result = [
            item for item in result
            if token in " ".join(
                str(item.get(key) or "")
                for key in (
                    "borrower_name", "employee_name", "phone_number", "normalized_phone",
                    "loan_reference", "direction", "status", "outcome", "notes",
                )
            ).lower()
        ]
    return result


@router.get("/calls/{call_id}")
def get_call(
    call_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    call = _call_or_404(db, context, call_id, ALL_CALL_ROLES)
    if context.role not in CALL_REVIEW_ROLES and call.employee_staff_id != context.staff.id:
        raise HTTPException(status_code=403, detail="Employees may view only their own calls")
    return _call_payload(call, context)


@router.post("/calls/{call_id}/media-token")
def create_employee_media_token(
    call_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    call = _call_or_404(db, context, call_id, CALL_AGENT_ROLES)
    if call.employee_staff_id != context.staff.id:
        raise HTTPException(status_code=403, detail="Only the assigned employee can join this call as an agent")
    if call.ended_at or call.status not in ACTIVE_CALL_STATUSES:
        raise HTTPException(status_code=409, detail="This call is no longer active")
    policy = get_or_create_policy(db, call.company_id)
    token = issue_livekit_token(
        identity=f"employee-{context.staff.id}",
        room_name=call.media_room_name,
        can_publish=True,
        can_subscribe=True,
        hidden=False,
        metadata={
            "company_id": str(call.company_id),
            "branch_id": str(call.branch_id) if call.branch_id else None,
            "call_id": str(call.id),
            "employee_staff_id": str(context.staff.id),
            "recording_enabled": bool(policy.recording_enabled),
        },
    )
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=call.company_id,
        branch_id=call.branch_id,
        action="CALL_MEDIA_TOKEN_ISSUED",
        entity_type="client_call",
        record_id=call.id,
        description="Employee received a short-lived controlled-calling media token",
        actor_role=context.role.value,
    )
    db.commit()
    return token


@router.post("/calls/{call_id}/recording", status_code=status.HTTP_201_CREATED)
async def upload_controlled_recording(
    call_id: UUID,
    recording: UploadFile = File(...),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    call = _call_or_404(db, context, call_id, CALL_AGENT_ROLES | CALL_REVIEW_ROLES)
    if call.employee_staff_id != context.staff.id and context.role not in CALL_REVIEW_ROLES:
        raise HTTPException(status_code=403, detail="Recording upload is outside the employee's call scope")
    policy = get_or_create_policy(db, call.company_id)
    if not policy.recording_enabled:
        raise HTTPException(status_code=409, detail="Call recording is disabled by company policy")
    if not live_media_configured():
        raise HTTPException(
            status_code=409,
            detail="Reliable recording is accepted only from the configured controlled WebRTC/SIP calling path",
        )
    if call.recording:
        raise HTTPException(status_code=409, detail="This call already has a recording")

    managed = await save_upload(
        db,
        recording,
        context,
        category="call_recording",
        visibility="private",
        description=f"Controlled business call recording {call.id}",
        linked_entity_type="client_call",
        linked_entity_id=str(call.id),
        is_confidential=True,
        company_id=call.company_id,
        branch_id=call.branch_id,
    )
    row = CallRecording(
        company_id=call.company_id,
        call_id=call.id,
        managed_file_id=managed.id,
        mime_type=managed.mime_type,
        size_bytes=managed.size_bytes,
        duration_seconds=call.duration_seconds or None,
        checksum=managed.checksum_sha256,
        status="available",
        deletion_at=recording_deletion_at(policy),
    )
    db.add(row)
    call.recording_status = "available"
    db.commit()
    db.refresh(row)
    return _recording_payload(row)


@router.get("/recordings/{recording_id}/play")
def play_recording(
    recording_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    recording = _recording_or_404(db, context, recording_id, CALL_REVIEW_ROLES)
    if recording.status != "available" or not recording.managed_file:
        raise HTTPException(status_code=410, detail="This recording is not available")
    content = read_file_bytes(recording.managed_file)
    call = db.get(ClientCall, recording.call_id)
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=recording.company_id,
        branch_id=call.branch_id if call else None,
        action="RECORDING_PLAYED",
        entity_type="call_recording",
        record_id=recording.id,
        description="Authorized manager or reviewer played a call recording",
        actor_role=context.role.value,
        event_data={"call_id": str(recording.call_id)},
    )
    db.commit()
    return Response(
        content=content,
        media_type=recording.mime_type or "application/octet-stream",
        headers={
            "Cache-Control": "no-store, private",
            "Content-Disposition": f'inline; filename="call-{recording.call_id}.audio"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/live-calls")
def list_live_calls(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, CALL_REVIEW_ROLES)
    query = db.query(ClientCall).filter(
        ClientCall.company_id == company_id,
        ClientCall.ended_at.is_(None),
        ClientCall.status.in_(ACTIVE_CALL_STATUSES),
    )
    if _branch_limited(context):
        query = query.filter(ClientCall.branch_id == context.branch_id)
    return [_call_payload(row, context) for row in query.order_by(ClientCall.started_at.desc()).all()]


@router.post("/live-calls/{call_id}/monitor")
def monitor_live_call(
    call_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    call = _call_or_404(db, context, call_id, CALL_REVIEW_ROLES)
    policy = get_or_create_policy(db, call.company_id)
    if not policy.live_monitoring_enabled:
        raise HTTPException(status_code=403, detail="Live monitoring is disabled by company policy")
    if call.ended_at or call.status not in ACTIVE_CALL_STATUSES:
        raise HTTPException(status_code=409, detail="This call is no longer active")
    token = issue_livekit_token(
        identity=f"monitor-{context.user.id}-{uuid4().hex[:8]}",
        room_name=call.media_room_name,
        can_publish=False,
        can_subscribe=True,
        hidden=True,
        metadata={
            "purpose": "listen_only_quality_monitoring",
            "company_id": str(call.company_id),
            "call_id": str(call.id),
            "manager_user_id": str(context.user.id),
        },
    )
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=call.company_id,
        branch_id=call.branch_id,
        action="LIVE_MONITOR_STARTED",
        entity_type="client_call",
        record_id=call.id,
        description="Authorized listen-only live call monitoring started",
        actor_role=context.role.value,
    )
    db.commit()
    return {**token, "mode": "listen_only"}


@router.get("/policy")
def get_policy(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, ALL_CALL_ROLES)
    policy = get_or_create_policy(db, company_id)
    db.commit()
    return policy_payload(policy)


@router.put("/policy")
def update_policy(
    payload: CallManagementPolicyUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, COMPANY_MANAGEMENT_ROLES)
    policy = get_or_create_policy(db, company_id)
    for field, value in payload.model_dump().items():
        setattr(policy, field, value)
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=company_id,
        branch_id=context.branch_id,
        action="CALL_POLICY_CHANGED",
        entity_type="call_management_policy",
        record_id=policy.id,
        description="Company call recording and monitoring policy changed",
        actor_role=context.role.value,
        event_data=payload.model_dump(mode="json"),
    )
    db.commit()
    return policy_payload(policy)


@router.post("/recordings/{recording_id}/legal-hold", status_code=status.HTTP_201_CREATED)
def create_legal_hold(
    recording_id: UUID,
    payload: LegalHoldCreateRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    recording = _recording_or_404(db, context, recording_id, CALL_HOLD_ROLES)
    policy = get_or_create_policy(db, recording.company_id)
    if not policy.legal_hold_enabled:
        raise HTTPException(status_code=403, detail="Legal holds are disabled by company policy")
    existing = db.query(RecordingLegalHold).filter(
        RecordingLegalHold.recording_id == recording.id,
        RecordingLegalHold.status == "active",
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="This recording already has an active legal hold")
    now = datetime.now(timezone.utc)
    hold = RecordingLegalHold(
        company_id=recording.company_id,
        recording_id=recording.id,
        placed_by_user_id=context.user.id,
        reason=payload.reason.strip(),
        status="active",
        placed_at=now,
    )
    db.add(hold)
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=recording.company_id,
        branch_id=context.branch_id,
        action="LEGAL_HOLD_CREATED",
        entity_type="call_recording",
        record_id=recording.id,
        description="Legal hold placed on a call recording",
        actor_role=context.role.value,
        event_data={"reason": payload.reason.strip()},
    )
    db.commit()
    db.refresh(hold)
    return {"id": str(hold.id), "status": hold.status, "reason": hold.reason, "placed_at": hold.placed_at.isoformat()}


@router.post("/recordings/{recording_id}/legal-hold/{hold_id}/release")
def release_legal_hold(
    recording_id: UUID,
    hold_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    recording = _recording_or_404(db, context, recording_id, CALL_HOLD_ROLES)
    hold = db.query(RecordingLegalHold).filter(
        RecordingLegalHold.id == hold_id,
        RecordingLegalHold.recording_id == recording.id,
        RecordingLegalHold.status == "active",
    ).first()
    if not hold:
        raise HTTPException(status_code=404, detail="Active legal hold not found")
    hold.status = "released"
    hold.released_by_user_id = context.user.id
    hold.released_at = datetime.now(timezone.utc)
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=recording.company_id,
        branch_id=context.branch_id,
        action="LEGAL_HOLD_RELEASED",
        entity_type="call_recording",
        record_id=recording.id,
        description="Legal hold released from a call recording",
        actor_role=context.role.value,
        event_data={"hold_id": str(hold.id)},
    )
    db.commit()
    return {"id": str(hold.id), "status": hold.status, "released_at": hold.released_at.isoformat()}


@router.put("/calls/{call_id}/quality-review")
def upsert_quality_review(
    call_id: UUID,
    payload: CallQualityReviewRequest,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    call = _call_or_404(db, context, call_id, CALL_REVIEW_ROLES)
    row = db.query(CallQualityReview).filter(
        CallQualityReview.company_id == call.company_id,
        CallQualityReview.call_id == call.id,
        CallQualityReview.reviewer_user_id == context.user.id,
    ).first()
    if not row:
        row = CallQualityReview(
            company_id=call.company_id,
            branch_id=call.branch_id,
            call_id=call.id,
            reviewer_user_id=context.user.id,
        )
        db.add(row)
    row.score = payload.score
    row.compliance_status = payload.compliance_status
    row.customer_care_status = payload.customer_care_status
    row.notes = payload.notes.strip() if payload.notes else None
    row.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=call.company_id,
        branch_id=call.branch_id,
        action="CALL_QUALITY_REVIEWED",
        entity_type="client_call",
        record_id=call.id,
        description="Authorized reviewer scored a client call for quality assurance",
        actor_role=context.role.value,
        event_data={
            "score": row.score,
            "compliance_status": row.compliance_status,
            "customer_care_status": row.customer_care_status,
        },
    )
    db.commit()
    db.refresh(row)
    return _review_payload(row)


@router.get("/dashboard")
def call_dashboard(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _company_id(context, ALL_CALL_ROLES)
    query = db.query(ClientCall).filter(ClientCall.company_id == company_id)
    if _branch_limited(context):
        query = query.filter(ClientCall.branch_id == context.branch_id)
    if context.role not in CALL_REVIEW_ROLES:
        query = query.filter(ClientCall.employee_staff_id == context.staff.id)
    rows = query.order_by(ClientCall.started_at.desc()).limit(2000).all()

    zone = ZoneInfo(settings.APP_TIMEZONE)
    local_day = datetime.now(zone).date()
    today: list[ClientCall] = []
    for row in rows:
        started = row.started_at
        if started.tzinfo is None:
            started_day = started.date()
        else:
            started_day = started.astimezone(zone).date()
        if started_day == local_day:
            today.append(row)

    recordings = sum(1 for row in today if row.recording_status == "available")
    live = sum(1 for row in today if row.ended_at is None and row.status in ACTIVE_CALL_STATUSES)
    contacted = len({row.borrower_id for row in today if row.borrower_id})
    duration_values = [row.duration_seconds for row in today if row.duration_seconds > 0]

    result: dict = {
        "summary": {
            "today_calls": len(today),
            "incoming": sum(1 for row in today if row.direction == "incoming"),
            "outgoing": sum(1 for row in today if row.direction == "outgoing"),
            "clients_contacted": contacted,
            "live_calls": live,
            "recordings_available": recordings,
            "average_duration_seconds": round(sum(duration_values) / len(duration_values)) if duration_values else 0,
        },
        "recent_calls": [_call_payload(row, context) for row in rows[:20]],
        "policy": policy_payload(get_or_create_policy(db, company_id)),
        "media_configured": live_media_configured(),
    }

    if context.role in CALL_REVIEW_ROLES:
        grouped: dict[UUID, list[ClientCall]] = defaultdict(list)
        for row in today:
            grouped[row.employee_staff_id].append(row)
        employee_performance = []
        for staff_id, calls in grouped.items():
            staff = db.get(CompanyStaff, staff_id)
            completed_durations = [item.duration_seconds for item in calls if item.duration_seconds > 0]
            employee_performance.append(
                {
                    "staff_id": str(staff_id),
                    "employee_name": _staff_name(staff),
                    "total_calls": len(calls),
                    "incoming": sum(1 for item in calls if item.direction == "incoming"),
                    "outgoing": sum(1 for item in calls if item.direction == "outgoing"),
                    "clients_contacted": len({item.borrower_id for item in calls if item.borrower_id}),
                    "recordings": sum(1 for item in calls if item.recording_status == "available"),
                    "average_duration_seconds": (
                        round(sum(completed_durations) / len(completed_durations)) if completed_durations else 0
                    ),
                }
            )
        employee_performance.sort(key=lambda item: item["total_calls"], reverse=True)
        result["employee_performance"] = employee_performance

    db.commit()
    return result
