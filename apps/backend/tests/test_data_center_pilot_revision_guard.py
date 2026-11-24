"""The privileged Data Center pilot control accepts only explicitly reviewed heads.

This is not a way to bypass the privileged role, approval reference, company
confirmation, or pilot readiness checks.
"""
import pytest
from scripts import data_center_pilot_control as control


def test_exact_reviewed_heads_only():
    assert control.EXPECTED_REVISIONS == frozenset({
        "dc20261122002",
        "f4a6c8e0d064",
    })
    assert "e3f5a7c9d063" not in control.EXPECTED_REVISIONS
    assert "unknown-head" not in control.EXPECTED_REVISIONS


class _Row:
    def __init__(self, value):
        self.value = value
    def one(self):
        return ("migration_operator", False)
    def scalars(self):
        return self
    def all(self):
        return self.value


class _Connection:
    def __init__(self, versions):
        self.versions = versions
        self.calls = 0
    def execute(self, statement, params=None):
        self.calls += 1
        query = str(statement)
        # Privilege SQL also contains current_user; match the specific
        # privilege probe first so it does not masquerade as the role probe.
        if "has_table_privilege" in query:
            return self
        if "current_user" in query:
            return _Row(None)
        if "alembic_version" in query:
            return _Row(self.versions)
        raise AssertionError("Pilot guard must stop before company access")
    def one(self):
        return (True, True, True, True)


@pytest.mark.parametrize("versions", [
    [], ["e3f5a7c9d063"], ["unknown-head"],
    ["dc20261122002", "f4a6c8e0d064"],
])
def test_unknown_or_multiple_revisions_fail_closed(versions):
    conn = _Connection(versions)
    with pytest.raises(control.PilotControlBlocked, match="Unexpected or multiple"):
        control.verify_database(
            conn, __import__("uuid").uuid4(), action="activate", apply=False,
        )
    assert conn.calls == 3
