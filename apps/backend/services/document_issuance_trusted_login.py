"""Fail-closed login identity prerequisite for non-routed official PDF issuance.

The dedicated issuer database login MUST be separately provisioned and kept
outside normal application connection pools. PostgreSQL session_user cannot be
supplied via tenant GUCs. This check is necessary but NOT sufficient: it does
not authenticate a human caller or certify connection isolation, RLS, grants,
source locks, or a secure single-transaction issuer worker.
"""
from __future__ import annotations

import os
import re

from sqlalchemy import text
from sqlalchemy.orm import Session


_LOGIN_PATTERN = re.compile(r"[a-z_][a-z0-9_]{2,62}\Z")


def require_trusted_issuer_database_login(*, db: Session) -> None:
    """Reject unspecified, shared, switched-role and privileged SQL logins."""
    expected = os.getenv("LOANHUB_ISSUANCE_TRUSTED_DB_LOGIN", "")
    ordinary = os.getenv("DB_USER", "")
    if (not _LOGIN_PATTERN.fullmatch(expected)
            or expected == ordinary
            or db.bind is None or db.bind.dialect.name != "postgresql"):
        raise PermissionError("Dedicated document issuer database login is not configured")
    identity = db.execute(text("""
        SELECT session_user AS login_name, current_user AS active_role,
               r.rolsuper AS is_superuser, r.rolbypassrls AS bypasses_rls,
               r.rolcanlogin AS can_login,
               r.rolcreatedb AS can_create_db,
               r.rolcreaterole AS can_create_role,
               r.rolreplication AS can_replicate
        FROM pg_roles r WHERE r.rolname = session_user
    """)).mappings().one_or_none()
    if (identity is None
            or identity["login_name"] != expected
            or identity["active_role"] != expected
            or identity["is_superuser"] is not False
            or identity["bypasses_rls"] is not False
            or identity["can_login"] is not True
            or identity["can_create_db"] is not False
            or identity["can_create_role"] is not False
            or identity["can_replicate"] is not False):
        raise PermissionError("Untrusted document issuer database login")
