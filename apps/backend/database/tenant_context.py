from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session


ActorScope = Literal["tenant", "platform", "borrower"]

_CONTEXT_KEYS = (
    "loanhub.user_id",
    "loanhub.company_id",
    "loanhub.branch_id",
    "loanhub.role",
    "loanhub.actor_scope",
)


def bind_database_tenant_context(
    db: Session,
    *,
    user_id: UUID,
    role: str,
    actor_scope: ActorScope,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
) -> None:
    """Bind verified authorization context to the current DB transaction.

    PostgreSQL `set_config(..., true)` is transaction-local, so pooled
    connections cannot leak one request's tenant identity into another request.
    Values are derived from LoanHub's authenticated/validated TenantContext,
    never directly from untrusted request headers.

    RLS policies intentionally are not enabled here. This function establishes
    the trustworthy database-session context that future policies can consume.
    """

    if actor_scope not in {"tenant", "platform", "borrower"}:
        raise ValueError(f"Unsupported database actor scope: {actor_scope!r}")

    values = {
        "loanhub.user_id": str(user_id),
        "loanhub.company_id": str(company_id) if company_id else "",
        "loanhub.branch_id": str(branch_id) if branch_id else "",
        "loanhub.role": role,
        "loanhub.actor_scope": actor_scope,
    }
    for key in _CONTEXT_KEYS:
        db.execute(
            text("SELECT set_config(:setting_name, :setting_value, true)"),
            {"setting_name": key, "setting_value": values[key]},
        )


def read_database_tenant_context(db: Session) -> dict[str, str | None]:
    """Return the transaction-local context for diagnostics and tests."""

    return {
        key: db.execute(
            text("SELECT current_setting(:setting_name, true)"),
            {"setting_name": key},
        ).scalar_one_or_none()
        for key in _CONTEXT_KEYS
    }
