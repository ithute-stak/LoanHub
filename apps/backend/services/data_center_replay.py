"""Tenant-authorized metadata-only replay for the staged Data Center journal."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from core.access_control import TenantContext
from services.data_center_branch_projection import verified_branch_grant
from services.data_center_staff_projection import require_staff_directory_management

MAX_REPLAY_EVENTS = 200
MAX_JS_CURSOR = 9007199254740991


class ReplayNotReady(RuntimeError):
    """The journal is disabled, stale, incomplete, or has a cursor gap."""


def ensure_contiguous(after_cursor: int, rows: list) -> None:
    expected = after_cursor + 1
    for row in rows:
        actual = int(row.cursor)
        if actual != expected:
            raise ReplayNotReady("Replay gap detected")
        expected += 1


def replay_metadata(
    db: Session,
    context: TenantContext,
    *,
    after_cursor: int,
    generation: UUID,
    limit: int = 100,
) -> dict:
    grant = verified_branch_grant(context)
    require_staff_directory_management(grant)
    if (
        after_cursor < 0 or after_cursor >= MAX_JS_CURSOR
        or limit < 1 or limit > MAX_REPLAY_EVENTS
    ):
        raise ReplayNotReady("Invalid replay range")

    company_id = context.company_id
    enabled = db.execute(text("""
        SELECT enabled, generation FROM public.loanhub_dc_capture
        WHERE company_id = :company_id
    """), {"company_id": company_id}).one_or_none()
    if enabled is None or not enabled.enabled or enabled.generation != generation:
        raise ReplayNotReady("Capture disabled or generation changed")

    watermark = db.execute(text("""
        SELECT cursor FROM public.loanhub_dc_clock
        WHERE company_id = :company_id
    """), {"company_id": company_id}).scalar_one_or_none()
    high = int(watermark or 0)
    if high > MAX_JS_CURSOR or after_cursor > high:
        raise ReplayNotReady("Replay cursor is ahead of the journal")

    rows = db.execute(text("""
        SELECT cursor, resource, entity_id, branch_id, action
        FROM public.loanhub_dc_event
        WHERE company_id = :company_id
          AND cursor > :after_cursor AND cursor <= :high
        ORDER BY cursor
        LIMIT :fetch_limit
    """), {
        "company_id": company_id,
        "after_cursor": after_cursor,
        "high": high,
        "fetch_limit": limit + 1,
    }).all()
    visible = rows[:limit]
    ensure_contiguous(after_cursor, visible)
    if not visible and high > after_cursor:
        raise ReplayNotReady("Missing journal entries")

    # Reject a capture toggle that raced this read. A re-enabled company
    # receives a new generation and must start from a fresh baseline.
    latest_capture = db.execute(text("""
        SELECT enabled, generation FROM public.loanhub_dc_capture
        WHERE company_id = :company_id
    """), {"company_id": company_id}).one_or_none()
    if (
        latest_capture is None or not latest_capture.enabled
        or latest_capture.generation != generation
    ):
        raise ReplayNotReady("Capture generation changed during replay")

    # The actor, company, or membership may have been revoked after the
    # initial HTTP authorization. Recheck all three before returning replay.
    from database.models.company_staff import CompanyStaff
    from database.models.company import LoanCompany
    from database.models.user import User
    active_user = db.query(User.id).filter(
        User.id == context.user.id, User.is_active.is_(True),
    ).first()
    active_company = db.query(LoanCompany.id).filter(
        LoanCompany.id == company_id, LoanCompany.is_active.is_(True),
    ).first()
    if active_user is None or active_company is None:
        raise PermissionError("Replay actor or company became inactive")
    member = db.query(CompanyStaff).filter(
        CompanyStaff.id == context.staff.id,
        CompanyStaff.user_id == context.user.id,
        CompanyStaff.company_id == company_id,
        CompanyStaff.is_active.is_(True),
    ).one_or_none()
    if (
        member is None
        or str(getattr(member.role, "value", member.role)) != grant.role
        or member.branch_id != context.branch_id
    ):
        raise PermissionError("Replay membership changed")

    next_cursor = int(visible[-1].cursor) if visible else after_cursor
    return {
        "contract": "loanhub.data-center-replay.v1",
        "company_id": grant.company_id,
        "generation": str(generation),
        "from_cursor": after_cursor,
        "next_cursor": next_cursor,
        "high_watermark": high,
        "has_more": next_cursor < high,
        "events": [{
            "cursor": int(item.cursor),
            "resource": item.resource,
            "entity_id": str(item.entity_id),
            "branch_id": str(item.branch_id) if item.branch_id else None,
            "action": item.action,
        } for item in visible],
        "payloads_included": False,
    }
