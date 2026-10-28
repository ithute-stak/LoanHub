"""Validate migration generator fails closed on branched Alembic histories."""
from types import SimpleNamespace
import pytest

from scripts.create_rollover_ledger_migration import get_single_head


def test_single_migration_head_is_accepted():
    assert get_single_head(SimpleNamespace(get_heads=lambda: ("abc123",))) == "abc123"


@pytest.mark.parametrize("heads", [(), ("abc123", "def456")])
def test_ambiguous_migration_history_is_rejected(heads):
    with pytest.raises(RuntimeError, match="exactly one Alembic head"):
        get_single_head(SimpleNamespace(get_heads=lambda: heads))
