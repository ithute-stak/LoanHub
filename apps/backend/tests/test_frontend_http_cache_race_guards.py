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
