"""Guardrail tests for the read-only PostgreSQL Principal x lock adapter."""
from pathlib import Path
from uuid import uuid4

import pytest

from services.principal_x_postgres_lock_review import lock_principal_x_loan_for_review


class FakeBind:
    class dialect:
        name = "sqlite"


class FakeSession:
    def get_bind(self):
        return FakeBind()


def test_non_postgresql_adapter_rejected_before_query():
    with pytest.raises(ValueError, match="PostgreSQL required"):
        lock_principal_x_loan_for_review(
            FakeSession(), company_id=uuid4(), loan_id=uuid4()
        )


def test_invalid_tenant_identifiers_rejected():
    with pytest.raises(ValueError, match="UUID"):
        lock_principal_x_loan_for_review(
            FakeSession(), company_id="wrong", loan_id=uuid4()
        )


def test_review_adapter_never_claims_reconciliation():
    source = (
        Path(__file__).resolve().parents[1]
        / "services/principal_x_postgres_lock_review.py"
    ).read_text(encoding="utf-8")
    assert ".with_for_update()" in source
    assert "reconciled=False" in source
    assert "db.commit(" not in source
    assert "db.add(" not in source
    assert "db.execute(" not in source
