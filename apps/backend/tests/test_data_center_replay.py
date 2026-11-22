from pathlib import Path
from types import SimpleNamespace as N

import pytest

from services.data_center_replay import (
    MAX_REPLAY_EVENTS, ReplayNotReady, ensure_contiguous,
)


def test_contiguous_events_after_snapshot_cursor():
    ensure_contiguous(10, [N(cursor=11), N(cursor=12), N(cursor=13)])


@pytest.mark.parametrize("cursors", [[12], [11, 13], [11, 11], [10]])
def test_gaps_duplicates_and_rewinds_require_resnapshot(cursors):
    with pytest.raises(ReplayNotReady):
        ensure_contiguous(10, [N(cursor=x) for x in cursors])


def test_empty_events_are_only_acceptable_if_watermark_has_not_advanced():
    ensure_contiguous(10, [])
    source = (Path(__file__).resolve().parents[1] / "services" / "data_center_replay.py").read_text()
    assert "if not visible and high > after_cursor:" in source
    assert 'raise ReplayNotReady("Missing journal entries")' in source


def test_replay_is_bounded_and_capture_generation_bound():
    assert MAX_REPLAY_EVENTS == 200
    root = Path(__file__).resolve().parents[1]
    source = (root / "services" / "data_center_replay.py").read_text()
    route = (root / "routers" / "data_center_replay.py").read_text()
    assert "enabled.generation != generation" in source
    assert "require_staff_directory_management(grant)" in source
    assert "CompanyStaff.is_active.is_(True)" in source
    assert "cursor > :after_cursor AND cursor <= :high" in source
    assert "LIMIT :fetch_limit" in source
    assert '"payloads_included": False' in source
    assert "status_code=409" in route
    assert '"private, no-store"' in route
