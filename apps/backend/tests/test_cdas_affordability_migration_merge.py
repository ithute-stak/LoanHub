"""Regression checks for the CDAS affordability / client registration Alembic merge."""
from pathlib import Path


def test_merge_revision_joins_known_heads_without_schema_mutations():
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/b7c9d1e3f055_merge_client_registration_cdas_affordability.py"
    )
    source = path.read_text(encoding="utf-8")
    namespace = {}
    exec(compile(source, str(path), "exec"), namespace)
    assert namespace["revision"] == "b7c9d1e3f055"
    assert set(namespace["down_revision"]) == {"a1r2i3d4e690", "a9c4e7b2d851"}
    assert namespace["upgrade"]() is None
    assert namespace["downgrade"]() is None
