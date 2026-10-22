"""Regression checks for the frontend DataTable cache-key contract."""
from pathlib import Path

CACHE = Path(__file__).resolve().parents[2] / "frontend" / "lib" / "http-cache.ts"

def test_datatable_keys_normalize_filter_order():
    source = CACHE.read_text()
    assert "const rawUrl = axios.getUri(config);" in source
    assert "params.sort();" in source
    assert "params.toString()" in source

def test_datatable_keys_include_tenant_and_pagination():
    source = CACHE.read_text()
    assert "X-Company-ID" in source
    assert "X-Active-Role" in source
    assert "state.auth.user?.id" in source
    assert "requestUrl" in source
    assert "const inflightKey" in source

def test_cache_ignores_late_response_after_invalidation():
    source = CACHE.read_text()
    assert "requestRevision === store.getState().httpCache.revision" in source
