"""Pilot preflight cannot enable capture or return private customer records."""
from pathlib import Path

from scripts.data_center_pilot_preflight import (
    EXPECTED_REVISION, RESOURCE_TABLES, SNAPSHOT_CAP,
    classify_readiness,
)


def baseline():
    return {
        "revision": EXPECTED_REVISION,
        "schema_complete": True,
        "triggers_present": {resource: True for resource in RESOURCE_TABLES},
        "counts": {resource: 2 for resource in RESOURCE_TABLES},
        "capture_enabled": True,
        "generation_valid": True,
        "cursor": 3,
        "event_count": 3,
        "earliest_cursor": 1,
        "latest_cursor": 3,
    }


def test_complete_small_tenant_and_contiguous_replay_pass():
    assert classify_readiness(**baseline()) == []


def test_default_disabled_is_never_pilot_ready():
    params = baseline()
    params["capture_enabled"] = False
    assert any("disabled" in x for x in classify_readiness(**params))


def test_missing_trigger_blocks():
    params = baseline()
    params["triggers_present"]["payments"] = False
    assert any("trigger" in x for x in classify_readiness(**params))


def test_oversized_loan_portfolio_blocks_without_truncation():
    params = baseline()
    params["counts"]["loans"] = SNAPSHOT_CAP + 1
    assert any("loans exceeds" in x for x in classify_readiness(**params))


def test_missing_or_deleted_events_block():
    params = baseline()
    params["event_count"] = 2
    assert any("count" in x for x in classify_readiness(**params))


def test_wrong_journal_generation_blocks():
    params = baseline()
    params["generation_valid"] = False
    assert any("generation" in x for x in classify_readiness(**params))


def test_unexpected_database_migration_blocks():
    params = baseline()
    params["revision"] = "outdated"
    assert any("migration" in x for x in classify_readiness(**params))


def test_read_only_source_never_changes_capture():
    source = (
        Path(__file__).resolve().parents[1] /
        "scripts" / "data_center_pilot_preflight.py"
    ).read_text()
    assert 'SET TRANSACTION READ ONLY' in source
    assert 'LIMIT :max_rows' in source
    assert 'return 2' in source
    assert 'set_config(\'loanhub.company_id\'' in source
    assert 'SET enabled' not in source
    assert 'UPDATE loanhub_dc_capture' not in source
    assert 'INSERT INTO loanhub_dc_capture' not in source
