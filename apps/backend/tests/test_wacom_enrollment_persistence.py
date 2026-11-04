"""Schema and SQL guardrail checks; a real PostgreSQL integration remains required."""
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone

from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy import create_mock_engine
from database.models.wacom_workstation import (
    WacomWorkstationEnrollment, WacomWorkstationChallengeRecord,
)
from services.wacom_challenge_persistence import consume_verified_wacom_challenge


def test_enrollment_schema_is_tenant_scoped_and_replay_persistent():
    enrollment = WacomWorkstationEnrollment.__table__
    challenge = WacomWorkstationChallengeRecord.__table__
    assert {"company_id", "workstation_id", "ed25519_public_key", "approved_at", "revoked_at"} <= set(enrollment.c.keys())
    assert {"company_id", "enrollment_id", "session_id", "nonce", "expires_at", "consumed_at"} <= set(challenge.c.keys())
    assert any(c.name == "uq_wacom_enrollment_company_workstation" for c in enrollment.constraints)
    assert any(c.name == "uq_wacom_challenge_nonce" for c in challenge.constraints)


def test_consume_constructs_atomic_update_not_read_then_write():
    seen = []
    class FakeResult:
        def scalar_one_or_none(self):
            return challenge_id
    class FakeSession:
        def execute(self, statement):
            seen.append(str(statement.compile(dialect=postgresql.dialect())))
            return FakeResult()
    challenge_id, company_id, enrollment_id, session_id = (uuid4() for _ in range(4))
    assert consume_verified_wacom_challenge(
        FakeSession(), challenge_id=challenge_id, company_id=company_id,
        enrollment_id=enrollment_id, session_id=session_id,
        now=datetime(2026, 11, 4, tzinfo=timezone.utc),
    )
    sql = seen[0]
    assert "UPDATE wacom_workstation_challenges" in sql
    assert "consumed_at IS NULL" in sql
    assert "expires_at >" in sql
    assert "wacom_workstation_enrollments" in sql
    assert "RETURNING" in sql


def test_migration_chains_from_existing_wacom_signature_head():
    root = Path(__file__).resolve().parents[1]
    migration = (root / "alembic/versions/w2c4e6g8h020_wacom_workstation_enrollment.py").read_text()
    assert 'down_revision = "x1w2s3g4n517"' in migration
    assert 'op.create_table(' in migration
    assert '"wacom_workstation_enrollments"' in migration
    assert '"wacom_workstation_challenges"' in migration
