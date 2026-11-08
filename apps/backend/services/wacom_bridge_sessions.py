"""Backend authorization for short-lived Wacom device-proof-bound sessions.

A token must accompany the user's normal LoanHub bearer token. Its server-side
identity and workstation enrollment/assignment are revalidated every request.
Never grants document signing or signature reuse. This is a short-lived bearer
credential established through device proof, not a per-request device signature.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy.orm import Session

from database.models.wacom_bridge_session import WacomBridgeSession
from database.models.wacom_workstation import WacomWorkstationEnrollment
from database.models.wacom_workstation_operator import WacomWorkstationOperator

_SESSION_PATTERN = re.compile(r"^wb1_[A-Za-z0-9_-]{43}$")
SESSION_TTL = timedelta(minutes=5)


def issue_bridge_session(db: Session, *, context, workstation_id):
    now = datetime.now(timezone.utc)
    token = "wb1_" + secrets.token_urlsafe(32)
    row = WacomBridgeSession(
        company_id=context.company_id,
        employee_user_id=context.user.id,
        workstation_id=workstation_id,
        token_sha256=hashlib.sha256(token.encode("ascii")).digest(),
        expires_at=now + SESSION_TTL,
    )
    db.add(row)
    return token, row


def authorize_bridge_session(db: Session, *, context, token: str | None, now=None) -> None:
    if not token or not _SESSION_PATTERN.fullmatch(token):
        raise HTTPException(403, "Verified Wacom workstation session required")
    if context.company_id is None or context.staff is None or not getattr(context.user, "is_active", False):
        raise HTTPException(403, "Active company staff required")
    now = now or datetime.now(timezone.utc)
    digest = hashlib.sha256(token.encode("ascii")).digest()
    row = db.query(WacomBridgeSession).filter(
        WacomBridgeSession.company_id == context.company_id,
        WacomBridgeSession.employee_user_id == context.user.id,
        WacomBridgeSession.token_sha256 == digest,
        WacomBridgeSession.revoked_at.is_(None),
        WacomBridgeSession.expires_at > now,
    ).one_or_none()
    if row is None:
        raise HTTPException(403, "Wacom session expired or unavailable")
    active_pc = db.query(WacomWorkstationEnrollment.id).filter(
        WacomWorkstationEnrollment.company_id == context.company_id,
        WacomWorkstationEnrollment.workstation_id == row.workstation_id,
        WacomWorkstationEnrollment.status == "active",
        WacomWorkstationEnrollment.approved_at.is_not(None),
        WacomWorkstationEnrollment.revoked_at.is_(None),
    ).first()
    active_assignment = db.query(WacomWorkstationOperator.id).filter(
        WacomWorkstationOperator.company_id == context.company_id,
        WacomWorkstationOperator.workstation_id == row.workstation_id,
        WacomWorkstationOperator.employee_user_id == context.user.id,
        WacomWorkstationOperator.status == "active",
        WacomWorkstationOperator.revoked_at.is_(None),
    ).first()
    if active_pc is None or active_assignment is None:
        raise HTTPException(403, "Wacom device or employee access revoked")


def bridge_enforcement_enabled() -> bool:
    # Opt-in transition only: staging's existing synthetic capture tests still
    # run before clients can consume the new session token. Enable only after
    # migrations + Go changes + gateway tests are deployed together.
    return os.getenv("LOANHUB_WACOM_REQUIRE_BRIDGE_SESSION", "") == "1"
