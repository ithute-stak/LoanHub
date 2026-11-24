"""Unit guardrails for aggregate-only, never-writable linkage triage."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from services.legacy_link_triage import (
    LegacyLinkTriageUnavailable,
    inspect_legacy_link_triage,
)


def session(*, read_only="on", in_transaction=True, dialect="postgresql",
            result=(113, 96, 15, 2, 17, 17)):
    db = Mock()
    db.get_bind.return_value = SimpleNamespace(
        dialect=SimpleNamespace(name=dialect))
    db.in_transaction.return_value = in_transaction
    db.execute.side_effect = [
        SimpleNamespace(scalar_one=lambda: read_only),
        SimpleNamespace(one=lambda: result),
    ]
    return db


def test_production_shape_is_aggregate_only_and_never_enables_changes():
    db = session()
    result = inspect_legacy_link_triage(db)
    assert result.matching_identity_groups == 113
    assert result.linked_only_groups == 96
    assert result.mixed_linkage_groups == 15
    assert result.unlinked_only_groups == 2
    assert result.unlinked_legacy_rows == 17
    assert result.unlinked_with_single_borrower_and_company_account == 17
    assert result.unlinked_needing_manual_review == 17
    assert result.registration_enabled is False
    assert result.automatic_repairs_allowed is False
    db.commit.assert_not_called()
    db.add.assert_not_called()
    sql = str(db.execute.call_args_list[1].args[0])
    assert "DELETE " not in sql.upper()
    assert "UPDATE " not in sql.upper()
    assert "INSERT " not in sql.upper()


@pytest.mark.parametrize("settings", [
    {"read_only": "off"},
    {"in_transaction": False},
    {"dialect": "sqlite"},
])
def test_requires_readonly_postgres(settings):
    db = session(**settings)
    with pytest.raises(LegacyLinkTriageUnavailable):
        inspect_legacy_link_triage(db)


@pytest.mark.parametrize("counts", [
    (113, 95, 15, 2, 17, 17),
    (113, 96, 15, 2, 17, 18),
    (113, 96, 15, 2, -1, 17),
    (113, 96, 15, 2, 17, True),
])
def test_inconsistent_aggregate_evidence_fails_closed(counts):
    with pytest.raises(LegacyLinkTriageUnavailable):
        inspect_legacy_link_triage(session(result=counts))
