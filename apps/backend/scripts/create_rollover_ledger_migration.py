"""Create the rollover-ledger Alembic revision against the *actual* current head.

Run from apps/backend with: python scripts/create_rollover_ledger_migration.py
Do not commit or apply the generated revision before reviewing it.
"""
from __future__ import annotations

from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND / "alembic.ini"


def get_single_head(script: ScriptDirectory) -> str:
    heads = tuple(script.get_heads())
    if len(heads) != 1:
        raise RuntimeError(f"Expected exactly one Alembic head, got {heads!r}; resolve branches before generating ledger migration")
    return heads[0]


def generate() -> Path:
    if not ALEMBIC_INI.exists():
        raise RuntimeError(f"Missing Alembic configuration: {ALEMBIC_INI}")
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    head = get_single_head(script)
    from alembic import command
    # Generate migration from ORM metadata so the actual FK/unique/check
    # constraints are represented. Review and manually validate before merge.
    created = command.revision(cfg, message="add loan rollover transfer ledger", autogenerate=True, head=head)
    if created is None:
        raise RuntimeError("Alembic did not create a revision")
    return Path(created.path)


if __name__ == "__main__":
    print(generate())
