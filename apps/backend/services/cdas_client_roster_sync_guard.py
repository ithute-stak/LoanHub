from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from services.cdas_client_roster_sync import (
    _daily_due,
    _enabled_cdas_configurations,
    _utc_iso,
    _write_roster_sync_state,
    get_roster_sync_state,
    local_now,
    sync_company_cdas_roster,
)
from services.cdas_request_budget import get_cdas_request_budget_status


ROSTER_FAILURE_BACKOFF = timedelta(hours=6)
BUDGET_DEFER_BACKOFF = timedelta(hours=1)
# Background roster discovery is useful, but staff-facing verification and
# deduction actions are more important. Do not start an automated roster batch
# once fewer than this many local request slots remain for the CDAS account.
BACKGROUND_MIN_REMAINING = 150


def _parse_retry_not_before(value: Any, now: datetime) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        retry_at = datetime.fromisoformat(text)
    except ValueError:
        return None
    if retry_at.tzinfo is None and now.tzinfo is not None:
        retry_at = retry_at.replace(tzinfo=now.tzinfo)
    return retry_at


def _retry_blocked(state: dict[str, Any], now: datetime) -> bool:
    retry_at = _parse_retry_not_before(state.get("retry_not_before"), now)
    return retry_at is not None and now < retry_at


def _next_retry_at(now: datetime) -> str:
    return (now + ROSTER_FAILURE_BACKOFF).isoformat()


def _next_budget_check_at(now: datetime) -> str:
    return (now + BUDGET_DEFER_BACKOFF).isoformat()


def _due_mode(state: dict[str, Any], now: datetime) -> str | None:
    if not state.get("bootstrap_completed_at"):
        return "bootstrap"
    if _daily_due(state, now):
        return "daily"
    return None


async def run_guarded_cdas_client_roster_sync_cycle(
    db: Session,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Run roster work with persistent failure backoff and a request reserve.

    The 60-second scheduler is only a due-check heartbeat. Failed bootstraps are
    persisted with a six-hour retry boundary so process restarts cannot recreate
    the old every-minute request storm. Automated work is also deferred before
    it can consume the request slots reserved for staff-facing CDAS operations.
    """
    current = now or local_now()
    results: list[dict[str, Any]] = []

    for row in _enabled_cdas_configurations(db):
        state = get_roster_sync_state(row)
        if _retry_blocked(state, current):
            continue

        mode = _due_mode(state, current)
        if mode is None:
            continue

        environment = str(row.environment or "test").strip().lower()
        budget = get_cdas_request_budget_status(
            db,
            company_id=row.company_id,
            environment=environment,
        )
        remaining = int(budget.get("remaining") or 0)
        if remaining < BACKGROUND_MIN_REMAINING:
            retry_not_before = _next_budget_check_at(current)
            _write_roster_sync_state(
                db,
                row,
                {
                    "last_completed_at": _utc_iso(),
                    "last_status": "deferred",
                    "last_error": (
                        "CDAS roster sync deferred to protect the daily request "
                        f"reserve ({remaining} requests remaining)"
                    ),
                    "retry_not_before": retry_not_before,
                },
            )
            results.append(
                {
                    "company_id": str(row.company_id),
                    "mode": mode,
                    "status": "deferred",
                    "remaining_requests": remaining,
                    "retry_not_before": retry_not_before,
                }
            )
            continue

        try:
            result = await sync_company_cdas_roster(
                db,
                row=row,
                mode=mode,
                now=current,
            )
        except Exception as exc:
            db.rollback()
            retry_not_before = _next_retry_at(current)
            try:
                _write_roster_sync_state(
                    db,
                    row,
                    {
                        "last_completed_at": _utc_iso(),
                        "last_status": "failed",
                        "last_error": str(exc)[:1000],
                        "retry_not_before": retry_not_before,
                    },
                )
            except Exception:
                db.rollback()
            results.append(
                {
                    "company_id": str(row.company_id),
                    "mode": mode,
                    "status": "failed",
                    "error": str(exc),
                    "retry_not_before": retry_not_before,
                }
            )
            continue

        if str(result.get("status") or "").lower() == "failed":
            retry_not_before = _next_retry_at(current)
            _write_roster_sync_state(
                db,
                row,
                {"retry_not_before": retry_not_before},
            )
            result["retry_not_before"] = retry_not_before
        else:
            # Clear any previous circuit-breaker state after a successful or
            # partial provider pass. Partial imports already mark the bootstrap
            # complete and will not be retried every minute.
            _write_roster_sync_state(db, row, {"retry_not_before": None})

        results.append(result)

    return results
