from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BOUNDARY = ROOT / "apps" / "frontend" / "provider" / "realtimeScreenBoundary.tsx"
COMMIT = ROOT / "apps" / "frontend" / "lib" / "realtime-commit.ts"
API = ROOT / "apps" / "frontend" / "lib" / "api.ts"


def test_local_mutation_batches_do_not_remount_stateful_screen() -> None:
    source = BOUNDARY.read_text(encoding="utf-8")

    assert "if (detail.hasRemoteChanges === false) return;" in source
    assert "shouldRefreshRouteForCommit(pathname, detail)" in source
    assert "setRevision((current) => current + 1)" in source


def test_local_mutation_request_ids_are_tracked_end_to_end() -> None:
    api = API.read_text(encoding="utf-8")
    commit = COMMIT.read_text(encoding="utf-8")

    assert 'config.headers["X-Request-ID"] = requestId' in api
    assert "rememberLocalMutationRequest(requestId)" in api
    assert "isLocalMutationRequest" in commit
    assert "RECENT_REQUEST_TTL_MS = 60_000" in commit
