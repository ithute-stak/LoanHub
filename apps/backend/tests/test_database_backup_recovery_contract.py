"""Contracts for database backup integrity and restore verification."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_backup_produces_checksum_metadata_and_parses_archive() -> None:
    script = _read(ROOT / "scripts/backup_db.sh")

    assert "pg_dump" in script
    assert "--format custom" in script
    assert "pg_restore" in script
    assert "--list" in script
    assert 'sha256sum "$OUTPUT" > "$CHECKSUM"' in script
    assert "verified_archive_list=true" in script
    assert 'chmod 600 "$OUTPUT"' in script
    assert 'chmod 600 "$CHECKSUM"' in script
    assert 'chmod 600 "$METADATA"' in script


def test_restore_requires_checksum_and_fails_fast() -> None:
    script = _read(ROOT / "scripts/restore_db.sh")

    checksum_pos = script.index('sha256sum -c "$CHECKSUM_FILE"')
    confirmation_pos = script.index("Type RESTORE:")
    assert checksum_pos < confirmation_pos
    assert "pg_restore" in script
    assert "--exit-on-error" in script
    assert "Run scripts/verify_backup.sh before any production restore." in script


def test_restore_verification_uses_disposable_database_and_cleanup_trap() -> None:
    script = _read(ROOT / "scripts/verify_backup.sh")

    assert 'sha256sum -c "$CHECKSUM_FILE"' in script
    assert "pg_restore" in script
    assert "--list" in script
    assert 'VERIFY_DB="loanhub_restore_verify_' in script
    assert "createdb" in script
    assert "--exit-on-error" in script
    assert "SELECT 1" in script
    assert "SELECT version_num FROM alembic_version ORDER BY version_num" in script
    assert "trap cleanup EXIT" in script
    assert "dropdb" in script
    assert "--if-exists" in script
    assert "Restore verification passed." in script


def test_restore_verification_never_targets_production_database() -> None:
    script = _read(ROOT / "scripts/verify_backup.sh")

    restore_pos = script.index("pg_restore")
    restore_block = script[restore_pos:]
    assert '--dbname "$VERIFY_DB"' in restore_block
    assert '--dbname "$DB_NAME"' not in restore_block



def test_pitr_readiness_reports_wal_archiving_without_mutation() -> None:
    script = _read(ROOT / "scripts/check_pitr_readiness.sh")

    assert "current_setting('wal_level')" in script
    assert "current_setting('archive_mode')" in script
    assert "current_setting('archive_command')" in script
    assert "current_setting('max_wal_senders')" in script
    assert "pg_is_in_recovery()" in script
    assert "pg_current_wal_lsn()" in script
    assert 'pitr_ready=false' in script
    assert 'pitr_ready=true' in script
    assert "ALTER SYSTEM" not in script
    assert "pg_reload_conf" not in script
    assert "pg_terminate_backend" not in script
