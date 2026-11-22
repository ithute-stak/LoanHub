"""Staged bridge must fail closed until an authorized replayable snapshot exists."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend"
BRIDGE = (ROOT / "provider" / "LoanHubDataCenterBridge.tsx").read_text()
REDUCER = (ROOT / "store" / "slices" / "dataCenterSlice.ts").read_text()


def test_pilot_is_explicitly_opt_in():
    assert 'process.env.NEXT_PUBLIC_LOANHUB_DATA_CENTER_ENABLED === "true"' in BRIDGE
    assert 'role !== "company_owner" && role !== "company_admin"' in BRIDGE
    assert '!authInitialized || !connected' in BRIDGE


def test_unverified_partial_snapshots_never_install():
    assert "!data.ready || !data.complete_data_center_snapshot" in BRIDGE
    assert "!data.replay_supported || !data.generation" in BRIDGE
    assert "scopeIsCurrent(data.scope)" in BRIDGE
    assert "store.getState().dataCenter" in BRIDGE
    assert "if (!installed.ready || installed.sessionId !== sessionId" in BRIDGE


def test_bridge_drops_session_on_disconnect_and_scope_change():
    assert "controller.abort();" in BRIDGE
    assert "dispatch(dataCenterActions.clear(sessionId));" in BRIDGE
    assert "branch, connected, dispatch, role, userId" in BRIDGE


def test_replay_gaps_and_overflow_fail_closed():
    assert "event.cursor !== expected++" in BRIDGE
    assert "MAX_REPLAY_PAGES" in BRIDGE
    assert "Replay completeness mismatch" in BRIDGE
    assert "revoke();" in BRIDGE
    assert "await bootstrap();" in BRIDGE


def test_allowlisted_server_borrower_ids_not_bank_data():
    assert "'borrower_id'" in REDUCER
    for sensitive in ("account_number", "national_id", "payer_phone", "provider_payload", "interest_rate"):
        assert sensitive not in REDUCER


def test_replay_is_bound_to_exact_contract_company_and_metadata_only():
    assert 'reply.contract !== "loanhub.data-center-replay.v1"' in BRIDGE
    assert "reply.company_id !== expectedScope.companyId" in BRIDGE
    assert "reply.payloads_included !== false" in BRIDGE
    assert 'typeof reply.has_more !== "boolean"' in BRIDGE
    assert "!Number.isSafeInteger(reply.from_cursor)" in BRIDGE
    assert "reply.events.length > 200" in BRIDGE
    assert "event.cursor !== expected++" in BRIDGE
    assert "event.resource" in BRIDGE
    assert "event.action" in BRIDGE
    assert "event.entity_id" in BRIDGE
    assert "event.branch_id" in BRIDGE
    assert "throw new Error(\"Replay cursor gap or invalid metadata\")" in BRIDGE
