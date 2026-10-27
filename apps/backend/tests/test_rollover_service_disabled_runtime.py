"""Verify disabled rollover posting refuses calls before any database access."""
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi import HTTPException

from services.final_installment_rollover_posting import post_final_rollover


class ForbiddenDatabase:
    def __getattr__(self, key):
        raise AssertionError(f"Posting unexpectedly accessed database: {key}")


def test_disabled_posting_has_no_database_side_effects():
    with pytest.raises(HTTPException) as exc:
        post_final_rollover(
            ForbiddenDatabase(),
            company_id=uuid4(),
            parent_id=uuid4(),
            installment_id=uuid4(),
            approved_amount=Decimal("19.50"),
            due_date=date(2026, 12, 1),
            agreement_reference="SIGNED-AGREEMENT",
            approval_reference="APPROVAL-123",
            actor_user_id=uuid4(),
            actor_role="company_owner",
            as_of=date(2026, 10, 27),
        )
    assert exc.value.status_code == 503


def test_disabled_posting_rejects_component_evidence_without_database_use():
    with pytest.raises(HTTPException) as exc:
        post_final_rollover(
            ForbiddenDatabase(),
            company_id=uuid4(), parent_id=uuid4(), installment_id=uuid4(),
            approved_amount=Decimal("3.00"), due_date=date(2026, 12, 1),
            agreement_reference="SIGNED-AGREEMENT",
            approval_reference="APPROVAL-123", actor_user_id=uuid4(),
            actor_role="company_owner", as_of=date(2026, 10, 27),
            component_evidence={"source_reference": "REF", "verified_by": "TEST"},
        )
    assert exc.value.status_code == 503
