"""Contracts for database backup integrity and restore verification."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_backup_produces_checksum_metadata_and_parses_archive() -> None:
    script = _read(ROOT / "scripts/backup_db.sh")

    assert 'pg_dump' in script
    assert '--format custom' in script
    assert 'pg_restore \' in script
    assert '--list' in script
    assert 'sha256sum "$OUTPUT" > "$CHECKSUM"' in script
    assert 'verified_archive_list=true' in script
    assert 'chmod 600 "$OUTPUT"' in script
    assert 'chmod 600 "$CHECKSUM"' in script
    assert 'chmod 600 "$METADATA"' in script


def test_restore_requires_checksum_and_fails_fast() -> None:
    script = _read(ROOT / "scripts/restore_db.sh")

    checksum_pos = script.index('sha256sum -c "$CHECKSUM_FILE"')
    confirmation_pos = script.index('Type RESTORE:')
    restore_pos = script.index('pg_restore \\')
    assert checksum_pos < confirmation_pos
    assert '--exit-on-error' in script
    assert 'Run scripts/verify_backup.sh before any production restore.' in script
    assert restore_pos >= 0


def test_restore_verification_uses_disposable_database_and_cleanup_trap() -> None:
    script = _read(ROOT / "scripts/verify_backup.sh")

    assert 'sha256sum -c "$CHECKSUM_FILE"' in script
    assert 'pg_restore \' in script
    assert '--list' in script
    assert 'VERIFY_DB="loanhub_restore_verify_' in script
    assert 'createdb \' in script
    assert '--exit-on-error' in script
    assert 'SELECT 1' in script
    assert 'SELECT version_num FROM alembic_version ORDER BY version_num' in script
    assert 'trap cleanup EXIT' in script
    assert 'dropdb \' in script
    assert '--if-exists' in script
    assert 'Restore verification passed.' in script


def test_restore_verification_never_targets_production_database() -> None:
    script = _read(ROOT / "scripts/verify_backup.sh")

    restore_block = script[script.index('docker compose exec -T db \\\n    pg_restore'):]
    assert '--dbname "$VERIFY_DB"' in restore_block
    assert '--dbname "$DB_NAME"' not in restore_block
