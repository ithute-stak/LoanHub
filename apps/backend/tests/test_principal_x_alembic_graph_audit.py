from pathlib import Path

from scripts.audit_principal_x_alembic_graph import audit_graph


def _revision(folder, filename, revision, parent):
    (folder / filename).write_text(
        f"revision = {revision!r}\ndown_revision = {parent!r}\n",
        encoding="utf-8",
    )


def test_single_linear_head(tmp_path: Path):
    _revision(tmp_path, "first.py", "a", None)
    _revision(tmp_path, "second.py", "b", "a")
    heads, errors, count = audit_graph(tmp_path)
    assert heads == ["b"]
    assert errors == []
    assert count == 2


def test_multiple_heads_block(tmp_path: Path):
    _revision(tmp_path, "first.py", "a", None)
    _revision(tmp_path, "other.py", "b", None)
    _, errors, _ = audit_graph(tmp_path)
    assert any("Expected one migration head" in error for error in errors)


def test_missing_parent_blocks(tmp_path: Path):
    _revision(tmp_path, "child.py", "child", "missing")
    _, errors, _ = audit_graph(tmp_path)
    assert any("Missing parent revision" in error for error in errors)


def test_duplicate_revision_blocks(tmp_path: Path):
    _revision(tmp_path, "first.py", "a", None)
    _revision(tmp_path, "second.py", "a", None)
    _, errors, _ = audit_graph(tmp_path)
    assert any("Duplicate revision" in error for error in errors)


def test_non_literal_revision_blocks(tmp_path: Path):
    (tmp_path / "bad.py").write_text("revision = get_revision()\ndown_revision = None\n")
    _, errors, _ = audit_graph(tmp_path)
    assert any("not a literal" in error for error in errors)
