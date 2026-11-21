"""Static wiring regression for frontend cache invalidation races."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "frontend"


def test_late_request_cannot_restore_invalidated_client_cache():
    adapter = (ROOT / "lib" / "http-cache.ts").read_text()
    slice_ = (ROOT / "store" / "features" / "slices" / "httpCacheSlice.ts").read_text()
    assert "const requestRevision = store.getState().httpCache.revision" in adapter
    assert "requestRevision === store.getState().httpCache.revision" in adapter
    assert "const inflightKey = `${identity.key}:${state.httpCache.revision}`" in adapter
    assert "inflightRequests.get(inflightKey)" in adapter
    assert "inflightRequests.set(inflightKey" in adapter
    assert "state.revision += 1" in slice_
    assert "cacheScopeInvalidated(" in slice_
    assert "cacheTagsInvalidated(" in slice_


def test_concurrent_get_uses_same_revision_key_for_lookup_and_storage():
    adapter = (ROOT / "lib" / "http-cache.ts").read_text()
    assert "inflightRequests.get(inflightKey)" in adapter
    assert "inflightRequests.set(inflightKey, request)" in adapter
    assert "inflightRequests.set(identity.key, request)" not in adapter


def test_tag_invalidation_blocks_late_inflight_response():
    source = (ROOT / "store" / "features" / "slices" / "httpCacheSlice.ts").read_text()
    tag_handler = source.split("cacheTagsInvalidated(", 1)[1].split("cacheCleared(", 1)[0]
    assert "state.revision += 1" in tag_handler


def test_cache_key_is_branch_qualified_and_old_scope_invalidations_still_work():
    adapter = (ROOT / "lib" / "http-cache.ts").read_text()
    slice_ = (ROOT / "store" / "features" / "slices" / "httpCacheSlice.ts").read_text()
    assert "state.auth.user?.memberships ?? []" in adapter
    assert "membership.company_id === companyId" in adapter
    assert "membership.role === role" in adapter
    assert "membership.is_active" in adapter
    assert "const branchScope = matchingMemberships.length === 1" in adapter
    assert 'entry.scope.startsWith(`${action.payload.scope}:`)' in slice_
