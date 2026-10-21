from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend"
BOUNDARY = ROOT / "provider" / "realtimeScreenBoundary.tsx"
REALTIME = ROOT / "provider" / "realtimeProvider.tsx"
AUTH = ROOT / "provider" / "AuthProvider.tsx"


def test_realtime_commit_never_remounts_work_in_progress():
    source = BOUNDARY.read_text(encoding="utf-8")
    assert "RealtimeScreenBoundary" in source
    assert "return <>{children}</>;" in source
    assert "key={revision}" not in source
    assert "setRevision(" not in source
    assert 'document.addEventListener("focusout"' not in source


def test_realtime_cache_invalidation_is_still_active():
    source = REALTIME.read_text(encoding="utf-8")
    assert "cacheTagsInvalidated" in source
    assert "cacheScopeInvalidated" in source
    assert "DB_COMMIT_EVENT_NAME" in source


def test_auth_token_renewal_is_silent():
    source = AUTH.read_text(encoding="utf-8")
    assert "refreshAccessToken()" in source
    assert "window.location.reload()" not in source
    assert "router.replace(" not in source


def test_mobile_pull_refresh_revalidates_shared_data_without_page_reload():
    provider = (ROOT / "provider" / "appDataProvider.tsx").read_text(encoding="utf-8")
    pull = (ROOT / "components" / "system" / "mobile-pull-to-refresh.tsx").read_text(encoding="utf-8")
    assert 'window.addEventListener("loanhub:pull-refresh", onPullRefresh)' in provider
    assert "void refreshAllData();" in provider
    assert 'new CustomEvent("loanhub:pull-refresh"' in pull
    assert "window.location.reload()" not in pull
