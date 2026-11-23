"""Role-bound issuer tenancy is not controlled by spoofable tenant GUCs."""
from unittest.mock import Mock
from uuid import UUID

import pytest

from services.document_issuance_role_tenant_binding import (
    require_issuer_role_tenant_binding,
)

TENANT = UUID("aaaaaaaa-aaaa-4aaa-aaaa-aaaaaaaaaaaa")
OTHER = UUID("bbbbbbbb-bbbb-4bbb-bbbb-bbbbbbbbbbbb")


def db_for(*, bound=TENANT, active_role="issuer_a", owner=False,
           can_insert=False, can_update=False, can_delete=False):
    db = Mock()
    db.bind.dialect.name = "postgresql"
    identity = {
        "login_name": "issuer_a", "active_role": active_role,
        "is_superuser": False, "bypasses_rls": False, "creates_roles": False,
    }
    mapping = {
        "owns_mapping": owner, "can_insert": can_insert,
        "can_update": can_update, "can_delete": can_delete,
    }
    result1 = Mock()
    result1.mappings.return_value.one_or_none.return_value = identity
    result2 = Mock()
    result2.mappings.return_value.one_or_none.return_value = mapping
    result3 = Mock()
    result3.scalar_one_or_none.return_value = bound
    db.execute.side_effect = [result1, result2, result3]
    return db


def test_bound_role_only_accepts_matching_tenant():
    db = db_for()
    require_issuer_role_tenant_binding(db=db, authenticated_tenant_id=TENANT)
    assert db.execute.call_count == 3


def test_other_tenant_denied_even_if_caller_changes_guc():
    db = db_for()
    with pytest.raises(PermissionError, match="not bound"):
        require_issuer_role_tenant_binding(db=db, authenticated_tenant_id=OTHER)


@pytest.mark.parametrize("changes", [
    {"active_role": "issuer_b"}, {"owner": True},
    {"can_insert": True}, {"can_update": True}, {"can_delete": True},
])
def test_privileged_or_role_switched_mapping_denied(changes):
    db = db_for(**changes)
    with pytest.raises(PermissionError):
        require_issuer_role_tenant_binding(db=db, authenticated_tenant_id=TENANT)


def test_missing_mapping_denied():
    db = db_for(bound=None)
    with pytest.raises(PermissionError, match="not bound"):
        require_issuer_role_tenant_binding(db=db, authenticated_tenant_id=TENANT)


def test_non_postgresql_denied_without_query():
    db = db_for()
    db.bind.dialect.name = "sqlite"
    with pytest.raises(PermissionError, match="PostgreSQL"):
        require_issuer_role_tenant_binding(db=db, authenticated_tenant_id=TENANT)
    db.execute.assert_not_called()
