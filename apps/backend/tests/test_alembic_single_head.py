from alembic.config import Config
from alembic.script import ScriptDirectory


def test_repository_has_one_alembic_head():
    script = ScriptDirectory.from_config(Config("alembic.ini"))
    heads = script.get_heads()
    assert len(heads) == 1, f"Expected one Alembic head, found: {heads}"
