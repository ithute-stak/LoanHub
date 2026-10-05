from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlalchemy import event, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session


ActorScope = Literal["tenant", "platform", "borrower"]

_CONTEXT_INFO_KEY = "loanhub.database_context"
_CONTEXT_KEYS = (
    "loanhub.user_id",
    "loanhub.company_id",
    "loanhub.branch_id",
    "loanhub.role",
    "loanhub.actor_scope",
)


def _apply_context(connection: Connection, values: dict[str, str]) -> None:
    for key in _CONTEXT_KEYS:
        connection.execute(
            text("SELECT set_config(:setting_name, :setting_value, true)"),
            {"setting_name": key, "setting_value": values[key]},
        )


@event.listens_for(Session, "after_begin")
def _restore_context_after_begin(
    session: Session,
    transaction,
    connection: Connection,
) -> None:
    """Re-apply request scope after a commit opens a fresh transaction."""

    values = session.info.get(_CONTEXT_INFO_KEY)
    if values:
        _apply_context(connection, values)


def bind_database_tenant_context(
    db: Session,
    *,
    user_id: UUID,
    role: str,
    actor_scope: ActorScope,
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
) -> None:
    """Bind verified authorization context to every transaction in this session.

    Values come from LoanHub's authenticated and membership-validated
    TenantContext, never directly from request headers. PostgreSQL
    `set_config(..., true)` makes each value transaction-local, preventing
    pooled connections from leaking one tenant into another. The SQLAlchemy
    after-begin hook restores the same verified values if application code
    commits and then opens another transaction during the request.

    RLS policies intentionally are not enabled here. This establishes the
    trustworthy database context that those policies can safely consume.
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

    transaction_is_active = db.in_transaction()
    db.info[_CONTEXT_INFO_KEY] = values

    # If authentication/membership resolution already opened a transaction,
    # bind the context immediately. Otherwise the after_begin hook will apply
    # it on the first database operation.
    if transaction_is_active:
        _apply_context(db.connection(), values)


def read_database_tenant_context(db: Session) -> dict[str, str | None]:
    """Return the transaction-local context for diagnostics and tests."""

    return {
        key: db.execute(
            text("SELECT current_setting(:setting_name, true)"),
            {"setting_name": key},
        ).scalar_one_or_none()
        for key in _CONTEXT_KEYS
    }
