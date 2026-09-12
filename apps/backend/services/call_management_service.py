from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from livekit import api as livekit_api
from sqlalchemy.orm import Session

from database.config.config import settings
from database.models.audit_log import AuditLog
from database.models.call_management import (
    CallManagementPolicy,
    CallRecording,
    ClientCall,
    RecordingLegalHold,
)
from database.models.file_management import ManagedFile
from services.object_storage_service import StorageUnavailableError, get_storage


DEFAULT_RECORDING_NOTICE = (
    "This business call may be recorded for service, compliance and quality assurance "
    "in accordance with the company's approved policy."
)


def normalize_lesotho_phone(value: str) -> str:
    """Return a canonical digits-only phone value suitable for matching.

    Local eight-digit Lesotho numbers are represented with country code 266.
    International values are preserved as digits after removing formatting.
    """
    raw = (value or "").strip()
    digits = re.sub(r"\D+", "", raw)
    if digits.startswith("00"):
        digits = digits[2:]
    if len(digits) == 8:
        digits = f"266{digits}"
    if digits.startswith("266") and len(digits) == 11:
        return digits
    if not 7 <= len(digits) <= 15:
        raise ValueError("Phone number must contain 7 to 15 digits")
    return digits


def get_or_create_policy(db: Session, company_id: UUID) -> CallManagementPolicy:
    policy = (
        db.query(CallManagementPolicy)
        .filter(CallManagementPolicy.company_id == company_id)
        .first()
    )
    if policy:
        return policy
    policy = CallManagementPolicy(
        company_id=company_id,
        recording_enabled=False,
        recording_retention_days=30,
        call_metadata_retention_months=24,
        automatic_deletion_enabled=True,
        live_monitoring_enabled=False,
        manager_downloads_enabled=False,
        legal_hold_enabled=True,
        recording_notice=DEFAULT_RECORDING_NOTICE,
        sip_outbound_trunk_id=None,
        sip_caller_number=None,
    )
    db.add(policy)
    db.flush()
    return policy


def policy_payload(policy: CallManagementPolicy) -> dict[str, Any]:
    return {
        "id": str(policy.id),
        "company_id": str(policy.company_id),
        "recording_enabled": bool(policy.recording_enabled),
        "recording_retention_days": int(policy.recording_retention_days or 30),
        "call_metadata_retention_months": int(policy.call_metadata_retention_months or 24),
        "automatic_deletion_enabled": bool(policy.automatic_deletion_enabled),
        "live_monitoring_enabled": bool(policy.live_monitoring_enabled),
        "manager_downloads_enabled": bool(policy.manager_downloads_enabled),
        "legal_hold_enabled": bool(policy.legal_hold_enabled),
        "recording_notice": policy.recording_notice or DEFAULT_RECORDING_NOTICE,
        "sip_outbound_trunk_id": policy.sip_outbound_trunk_id,
        "sip_caller_number": policy.sip_caller_number,
    }


def live_media_configured() -> bool:
    return bool(
        settings.CALL_MEDIA_PROVIDER.strip().lower() == "livekit"
        and settings.LIVEKIT_URL
        and settings.LIVEKIT_API_KEY
        and settings.LIVEKIT_API_SECRET
    )


def sip_outbound_configured(policy: CallManagementPolicy) -> bool:
    return bool(live_media_configured() and policy.sip_outbound_trunk_id)


def issue_livekit_token(
    *,
    identity: str,
    room_name: str,
    can_publish: bool,
    can_subscribe: bool,
    hidden: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, str | int]:
    if not live_media_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Controlled calling media is not configured for this LoanHub deployment",
        )

    now = int(time.time())
    ttl = max(60, min(int(settings.CALL_TOKEN_TTL_SECONDS), 900))
    payload: dict[str, Any] = {
        "iss": settings.LIVEKIT_API_KEY,
        "sub": identity,
        "nbf": now - 5,
        "exp": now + ttl,
        "video": {
            "roomJoin": True,
            "room": room_name,
            "canPublish": can_publish,
            "canPublishData": False,
            "canSubscribe": can_subscribe,
            "hidden": hidden,
        },
    }
    if metadata:
        payload["metadata"] = json.dumps(metadata, separators=(",", ":"), default=str)

    token = jwt.encode(payload, settings.LIVEKIT_API_SECRET, algorithm="HS256")
    return {
        "server_url": str(settings.LIVEKIT_URL),
        "token": token,
        "room_name": room_name,
        "expires_in": ttl,
    }


def _livekit_http_url(value: str) -> str:
    if value.startswith("wss://"):
        return "https://" + value[6:]
    if value.startswith("ws://"):
        return "http://" + value[5:]
    return value


async def place_outbound_sip_call(
    *,
    call: ClientCall,
    policy: CallManagementPolicy,
    participant_name: str | None,
) -> dict[str, Any]:
    """Create a SIP participant that dials the client into the call's LiveKit room."""
    if not live_media_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Controlled LiveKit calling is not configured",
        )
    if not policy.sip_outbound_trunk_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The company has not configured an outbound SIP trunk",
        )

    target = f"+{call.normalized_phone}"
    client = livekit_api.LiveKitAPI(
        _livekit_http_url(str(settings.LIVEKIT_URL)),
        str(settings.LIVEKIT_API_KEY),
        str(settings.LIVEKIT_API_SECRET),
    )
    try:
        request = livekit_api.CreateSIPParticipantRequest(
            sip_trunk_id=policy.sip_outbound_trunk_id,
            sip_call_to=target,
            room_name=call.media_room_name,
            participant_identity=f"client-{call.borrower_id or call.id}",
            participant_name=participant_name or "LoanHub client",
            wait_until_answered=False,
            sip_number=policy.sip_caller_number or "",
        )
        info = await client.sip.create_sip_participant(request)
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The SIP provider could not start the outbound client call",
        ) from error
    finally:
        await client.aclose()

    return {
        "participant_id": getattr(info, "participant_id", None),
        "participant_identity": getattr(info, "participant_identity", None),
        "sip_call_id": getattr(info, "sip_call_id", None),
        "target": target,
    }


def recording_deletion_at(policy: CallManagementPolicy, *, now: datetime | None = None) -> datetime | None:
    if not policy.automatic_deletion_enabled:
        return None
    current = now or datetime.now(timezone.utc)
    return current + timedelta(days=max(1, int(policy.recording_retention_days or 30)))


def write_sensitive_audit(
    db: Session,
    *,
    user_id: UUID | None,
    company_id: UUID,
    branch_id: UUID | None,
    action: str,
    entity_type: str,
    record_id: UUID,
    description: str,
    actor_role: str | None,
    event_data: dict[str, Any] | None = None,
) -> AuditLog:
    row = AuditLog(
        user_id=user_id,
        company_id=company_id,
        branch_id=branch_id,
        action=action,
        table_name="call_management",
        entity_type=entity_type,
        record_id=record_id,
        description=description,
        actor_role=actor_role,
        severity="info",
        status="success",
        before_data={},
        after_data={},
        changed_fields=[],
        event_data=event_data or {},
    )
    db.add(row)
    db.flush()
    return row


def has_active_legal_hold(db: Session, recording_id: UUID) -> bool:
    return bool(
        db.query(RecordingLegalHold.id)
        .filter(
            RecordingLegalHold.recording_id == recording_id,
            RecordingLegalHold.status == "active",
        )
        .first()
    )


def delete_expired_recordings(db: Session, *, limit: int = 100) -> dict[str, int]:
    """Delete expired audio while keeping call metadata and an audit trail.

    The operation is retry-safe: records already marked deleted are excluded,
    legal holds are skipped, and failed storage deletes return to AVAILABLE.
    """
    now = datetime.now(timezone.utc)
    rows = (
        db.query(CallRecording)
        .filter(
            CallRecording.status == "available",
            CallRecording.deletion_at.isnot(None),
            CallRecording.deletion_at <= now,
        )
        .order_by(CallRecording.deletion_at.asc())
        .limit(max(1, min(limit, 1000)))
        .all()
    )

    deleted = 0
    held = 0
    failed = 0
    for recording in rows:
        policy = get_or_create_policy(db, recording.company_id)
        if not policy.automatic_deletion_enabled:
            continue
        if has_active_legal_hold(db, recording.id):
            held += 1
            continue

        recording.status = "deleting"
        db.flush()
        managed = db.get(ManagedFile, recording.managed_file_id) if recording.managed_file_id else None
        try:
            if managed and not managed.is_deleted:
                get_storage(managed.storage_provider or "local").delete(managed.storage_key)
                managed.is_deleted = True
                managed.deleted_at = now
            recording.status = "deleted"
            recording.deleted_at = now
            call = db.get(ClientCall, recording.call_id)
            if call:
                call.recording_status = "deleted"
            write_sensitive_audit(
                db,
                user_id=None,
                company_id=recording.company_id,
                branch_id=call.branch_id if call else None,
                action="RECORDING_DELETED",
                entity_type="call_recording",
                record_id=recording.id,
                description="Expired call recording deleted by the retention worker",
                actor_role="system",
                event_data={"call_id": str(recording.call_id), "deletion_at": str(recording.deletion_at)},
            )
            deleted += 1
        except (StorageUnavailableError, OSError):
            recording.status = "available"
            failed += 1

    db.commit()
    return {"deleted": deleted, "held": held, "failed": failed}
