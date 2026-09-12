from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from livekit import api as livekit_api
from sqlalchemy.orm import Session

from core.access_control import TenantContext, get_user_context
from database.config.config import settings
from database.models.call_management import ClientCall
from database.models.company_staff import CompanyStaff
from database.models.enums import UserRole
from database.schemas.call_management import SipPolicyUpdate
from database.session import get_db
from services.call_management_service import (
    get_or_create_policy,
    live_media_configured,
    normalize_lesotho_phone,
    place_outbound_sip_call,
    sip_outbound_configured,
    write_sensitive_audit,
)


router = APIRouter(prefix="/call-management", tags=["Controlled Call Media"])

DIAL_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
    UserRole.BRANCH_MANAGER,
    UserRole.LOAN_OFFICER,
    UserRole.COLLECTIONS_OFFICER,
    UserRole.CUSTOMER_SUPPORT,
    UserRole.OPERATIONS_OFFICER,
}
MANAGEMENT_ROLES: set[UserRole] = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
}


def _owned_call(db: Session, context: TenantContext, call_id: UUID) -> ClientCall:
    if not context.company_id or not context.staff or context.role not in DIAL_ROLES:
        raise HTTPException(status_code=403, detail="An authorized company calling role is required")
    call = db.query(ClientCall).filter(
        ClientCall.id == call_id,
        ClientCall.company_id == context.company_id,
    ).first()
    if not call:
        raise HTTPException(status_code=404, detail="Call not found")
    if call.employee_staff_id != context.staff.id:
        raise HTTPException(status_code=403, detail="Only the assigned employee can control this call")
    return call


def _management_company(context: TenantContext) -> UUID:
    if not context.company_id or not context.staff or context.role not in MANAGEMENT_ROLES:
        raise HTTPException(status_code=403, detail="Company management access is required")
    return context.company_id


def _livekit_http_url(value: str) -> str:
    if value.startswith("wss://"):
        return "https://" + value[6:]
    if value.startswith("ws://"):
        return "http://" + value[5:]
    return value


def _staff_name(staff: CompanyStaff) -> str:
    user = staff.user
    if user and user.person:
        return user.person.full_name
    return (user.email or user.phone) if user else "LoanHub employee"


def _staff_telephony(staff: CompanyStaff) -> tuple[str | None, str | None]:
    """Return (transfer target, extension) without trusting mobile input.

    EmployeeProfile.target_config is intentionally used as the provider-neutral
    place for PBX metadata so Vodacom/another provider can later supply a SIP
    URI without another schema migration. Supported keys are:
    telephony_address / sip_uri and telephony_extension / extension.
    """
    profile = staff.employee_profile
    config = (profile.target_config or {}) if profile else {}
    extension = config.get("telephony_extension") or config.get("extension")
    raw = config.get("telephony_address") or config.get("sip_uri")
    if raw:
        value = str(raw).strip()
        if value.startswith(("sip:", "tel:")):
            return value, str(extension) if extension else None
        try:
            return f"tel:+{normalize_lesotho_phone(value)}", str(extension) if extension else None
        except ValueError:
            pass

    if staff.user and staff.user.phone:
        try:
            return (
                f"tel:+{normalize_lesotho_phone(staff.user.phone)}",
                str(extension) if extension else None,
            )
        except ValueError:
            pass
    return None, str(extension) if extension else None


def _seconds_between(started_at: datetime, ended_at: datetime) -> int:
    right = ended_at if started_at.tzinfo is not None else ended_at.replace(tzinfo=None)
    return max(0, int((right - started_at).total_seconds()))


@router.get("/desktop-capability")
def desktop_calling_capability(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    """Return safe, non-secret readiness information for the web softphone."""
    if not context.company_id or not context.staff or context.role not in DIAL_ROLES:
        raise HTTPException(status_code=403, detail="An authorized company calling role is required")
    policy = get_or_create_policy(db, context.company_id)
    db.commit()
    media_configured = live_media_configured()
    outbound_configured = sip_outbound_configured(policy)
    return {
        "media_configured": media_configured,
        "outbound_configured": outbound_configured,
        "calling_available": bool(media_configured and outbound_configured),
        "recording_enabled": bool(policy.recording_enabled),
        "recording_notice": policy.recording_notice,
    }


@router.get("/sip-settings")
def get_sip_settings(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _management_company(context)
    policy = get_or_create_policy(db, company_id)
    db.commit()
    return {
        "media_configured": live_media_configured(),
        "outbound_configured": sip_outbound_configured(policy),
        "outbound_trunk_id": policy.sip_outbound_trunk_id,
        "caller_number": policy.sip_caller_number,
    }


@router.put("/sip-settings")
def update_sip_settings(
    payload: SipPolicyUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    company_id = _management_company(context)
    policy = get_or_create_policy(db, company_id)
    policy.sip_outbound_trunk_id = payload.outbound_trunk_id
    policy.sip_caller_number = payload.caller_number
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=company_id,
        branch_id=context.branch_id,
        action="CALL_SIP_ROUTING_CHANGED",
        entity_type="call_management_policy",
        record_id=policy.id,
        description="Company outbound SIP routing was updated",
        actor_role=context.role.value,
        event_data={
            "outbound_trunk_configured": bool(payload.outbound_trunk_id),
            "caller_number_configured": bool(payload.caller_number),
        },
    )
    db.commit()
    return {
        "media_configured": live_media_configured(),
        "outbound_configured": sip_outbound_configured(policy),
        "outbound_trunk_id": policy.sip_outbound_trunk_id,
        "caller_number": policy.sip_caller_number,
    }


@router.get("/team-directory")
def team_directory(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    if not context.company_id or not context.staff or context.role not in DIAL_ROLES:
        raise HTTPException(status_code=403, detail="An authorized company calling role is required")

    rows = (
        db.query(CompanyStaff)
        .filter(
            CompanyStaff.company_id == context.company_id,
            CompanyStaff.is_active.is_(True),
            CompanyStaff.role.in_(DIAL_ROLES),
        )
        .order_by(CompanyStaff.is_primary.desc())
        .all()
    )
    result = []
    for row in rows:
        target, extension = _staff_telephony(row)
        result.append(
            {
                "staff_id": str(row.id),
                "name": _staff_name(row),
                "role": row.role.value,
                "branch_id": str(row.branch_id) if row.branch_id else None,
                "phone": row.user.phone if row.user else None,
                "extension": extension,
                "transfer_target_configured": bool(target),
                "is_current_employee": row.id == context.staff.id,
            }
        )
    return result


@router.post("/calls/{call_id}/dial")
async def dial_client(
    call_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    call = _owned_call(db, context, call_id)
    if call.direction != "outgoing":
        raise HTTPException(status_code=409, detail="Only outgoing calls can start a SIP dial")
    if call.ended_at or call.status in {"completed", "failed", "cancelled", "missed", "transferred"}:
        raise HTTPException(status_code=409, detail="This call has already ended")
    policy = get_or_create_policy(db, call.company_id)
    borrower_user = call.borrower.user if call.borrower else None
    participant_name = borrower_user.person.full_name if borrower_user and borrower_user.person else None
    result = await place_outbound_sip_call(call=call, policy=policy, participant_name=participant_name)
    call.status = "ringing"
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=call.company_id,
        branch_id=call.branch_id,
        action="OUTBOUND_SIP_DIAL_STARTED",
        entity_type="client_call",
        record_id=call.id,
        description="Employee started an outbound client call through the controlled SIP path",
        actor_role=context.role.value,
        event_data={"target": result.get("target"), "participant_identity": result.get("participant_identity")},
    )
    db.commit()
    return {"call_id": str(call.id), "status": call.status, **result}


@router.post("/calls/{call_id}/transfer/{target_staff_id}")
async def transfer_client_call(
    call_id: UUID,
    target_staff_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    call = _owned_call(db, context, call_id)
    if call.ended_at or call.status in {"completed", "failed", "cancelled", "missed", "transferred"}:
        raise HTTPException(status_code=409, detail="This call has already ended")
    if target_staff_id == context.staff.id:
        raise HTTPException(status_code=409, detail="Choose another employee for the transfer")

    target_staff = db.query(CompanyStaff).filter(
        CompanyStaff.id == target_staff_id,
        CompanyStaff.company_id == call.company_id,
        CompanyStaff.is_active.is_(True),
    ).first()
    if not target_staff:
        raise HTTPException(status_code=404, detail="Transfer employee not found")

    transfer_to, extension = _staff_telephony(target_staff)
    if not transfer_to:
        raise HTTPException(
            status_code=409,
            detail="The selected employee does not have a phone or SIP transfer address configured",
        )
    if not live_media_configured():
        raise HTTPException(status_code=503, detail="Controlled LiveKit calling is not configured")

    participant_identity = f"client-{call.borrower_id or call.id}"
    client = livekit_api.LiveKitAPI(
        _livekit_http_url(str(settings.LIVEKIT_URL)),
        str(settings.LIVEKIT_API_KEY),
        str(settings.LIVEKIT_API_SECRET),
    )
    try:
        request = livekit_api.TransferSIPParticipantRequest(
            room_name=call.media_room_name,
            participant_identity=participant_identity,
            transfer_to=transfer_to,
            play_dialtone=True,
        )
        await client.sip.transfer_sip_participant(request)
    except Exception as error:
        raise HTTPException(
            status_code=502,
            detail="The telephony provider could not transfer the call",
        ) from error
    finally:
        await client.aclose()

    ended_at = datetime.now(timezone.utc)
    call.ended_at = ended_at
    call.duration_seconds = _seconds_between(call.started_at, ended_at)
    call.status = "transferred"
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=call.company_id,
        branch_id=call.branch_id,
        action="CONTROLLED_CALL_TRANSFERRED",
        entity_type="client_call",
        record_id=call.id,
        description="Employee transferred a controlled client call to another LoanHub employee",
        actor_role=context.role.value,
        event_data={
            "target_staff_id": str(target_staff.id),
            "target_employee": _staff_name(target_staff),
            "target_extension": extension,
            "transfer_target_type": "sip" if transfer_to.startswith("sip:") else "telephone",
            "duration_seconds": call.duration_seconds,
        },
    )
    db.commit()
    return {
        "call_id": str(call.id),
        "status": call.status,
        "transferred_to_staff_id": str(target_staff.id),
        "transferred_to_name": _staff_name(target_staff),
        "extension": extension,
        "ended_at": call.ended_at.isoformat(),
        "duration_seconds": call.duration_seconds,
    }


@router.post("/calls/{call_id}/hangup")
async def hangup_client(
    call_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    call = _owned_call(db, context, call_id)
    if call.ended_at:
        return {"call_id": str(call.id), "status": call.status, "ended_at": call.ended_at.isoformat()}

    media_warning = None
    if live_media_configured():
        client = livekit_api.LiveKitAPI(
            _livekit_http_url(str(settings.LIVEKIT_URL)),
            str(settings.LIVEKIT_API_KEY),
            str(settings.LIVEKIT_API_SECRET),
        )
        try:
            await client.room.delete_room(livekit_api.DeleteRoomRequest(room=call.media_room_name))
        except Exception:
            media_warning = "The call was closed in LoanHub, but the media server did not confirm room termination."
        finally:
            await client.aclose()

    ended_at = datetime.now(timezone.utc)
    call.ended_at = ended_at
    call.duration_seconds = _seconds_between(call.started_at, ended_at)
    call.status = "completed"
    write_sensitive_audit(
        db,
        user_id=context.user.id,
        company_id=call.company_id,
        branch_id=call.branch_id,
        action="CONTROLLED_CALL_ENDED",
        entity_type="client_call",
        record_id=call.id,
        description="Employee ended the controlled client call",
        actor_role=context.role.value,
        event_data={"duration_seconds": call.duration_seconds, "media_warning": media_warning},
    )
    db.commit()
    return {
        "call_id": str(call.id),
        "status": call.status,
        "ended_at": call.ended_at.isoformat(),
        "duration_seconds": call.duration_seconds,
        "warning": media_warning,
    }
