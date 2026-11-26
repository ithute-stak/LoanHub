"""Fail-closed checks for the Principal x settlement source inventory."""
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from database.schemas.early_settlement import PrincipalXSourceCoverageRead
from payment_engine.principal_x_ledger_source_attestation import REQUIRED_SOURCE_FAMILIES
from services.principal_x_source_coverage import (
    DIAGNOSTIC_SOURCE_FAMILIES,
    principal_x_source_coverage,
)


def test_inventory_lists_every_required_financial_source_without_certification():
    rows = principal_x_source_coverage()
    assert {row.source_family for row in rows} == REQUIRED_SOURCE_FAMILIES
    assert len(rows) == len(REQUIRED_SOURCE_FAMILIES)
    assert all(row.authoritatively_verified is False for row in rows)
    assert {
        row.source_family for row in rows if row.review_stage == "diagnostic_only"
    } == DIAGNOSTIC_SOURCE_FAMILIES
    assert {
        row.source_family for row in rows
        if row.review_stage == "authoritative_adapter_missing"
    } == REQUIRED_SOURCE_FAMILIES - DIAGNOSTIC_SOURCE_FAMILIES


def test_zero_payment_history_still_cannot_certify_any_source():
    rows = principal_x_source_coverage()
    assert all(row.authoritatively_verified is False for row in rows)
    assert len([x for x in rows if x.review_stage == "authoritative_adapter_missing"]) == 4


def test_api_rejects_any_claim_of_authoritative_verification():
    with pytest.raises(ValidationError):
        PrincipalXSourceCoverageRead(
            source_family="provider_reversals",
            review_stage="authoritative_adapter_missing",
            authoritatively_verified=True,
        )


def test_api_rejects_unrecognized_source_review_stage():
    with pytest.raises(ValidationError):
        PrincipalXSourceCoverageRead(
            source_family="refunds",
            review_stage="certified",
            authoritatively_verified=False,
        )
