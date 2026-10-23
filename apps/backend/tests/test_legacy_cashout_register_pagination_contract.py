from pathlib import Path


def test_legacy_register_supports_offset_pagination():
    source = (Path(__file__).resolve().parents[1] / "routers" / "legacy_cashout.py").read_text()
    assert "offset: int = Query(default=0, ge=0)" in source
    assert ".offset(offset).limit(limit).all()" in source


def test_frontend_loads_subsequent_batches():
    source = (Path(__file__).resolve().parents[2] / "frontend" / "api" / "legacyCashout.ts").read_text()
    assert "while (true)" in source
    assert "params: { limit: pageSize, offset }" in source
    assert "records.push(...response.data)" in source
    assert "response.data.length < pageSize" in source
