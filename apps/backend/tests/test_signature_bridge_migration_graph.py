"""Ensure Signature Bridge migration is attached to the installed Alembic graph."""
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory


def test_signature_bridge_revision_has_resolvable_parent():
    backend = Path(__file__).resolve().parents[1]
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    script = ScriptDirectory.from_config(config)
    revision = script.get_revision("sb20261105q01")
    assert revision is not None
    assert revision.down_revision
    assert script.get_revision(revision.down_revision) is not None
