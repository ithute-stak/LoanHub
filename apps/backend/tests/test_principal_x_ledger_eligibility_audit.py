from uuid import uuid4

import pytest

from services.principal_x_ledger_eligibility_audit import audit_principal_x_ledger_eligibility


class QueryDouble:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *args):
        return self

    def all(self):
        return self.rows


class SessionDouble:
    def __init__(self, rows):
        self.rows = rows

    def query(self, model):
        return QueryDouble(self.rows)


class Payment:
    def __init__(self, status, provider_reference):
        self.status = status
        self.provider_reference = provider_reference


def test_even_clean_history_cannot_certify_authoritative_ledger():
    result = audit_principal_x_ledger_eligibility(
        SessionDouble([Payment("succeeded", "ref-1")]),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.payment_rows == 1
    assert result.incomplete_rows == 0
    assert result.missing_provider_references == 0
    assert result.can_certify_net_collected is False


def test_pending_and_missing_references_reported():
    result = audit_principal_x_ledger_eligibility(
        SessionDouble([Payment("pending", None), Payment("succeeded", "ref-2")]),
        company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.payment_rows == 2
    assert result.incomplete_rows == 1
    assert result.missing_provider_references == 1
    assert result.can_certify_net_collected is False


def test_no_rows_does_not_imply_no_external_collections():
    result = audit_principal_x_ledger_eligibility(
        SessionDouble([]), company_id=uuid4(), loan_id=uuid4(),
    )
    assert result.payment_rows == 0
    assert result.can_certify_net_collected is False


def test_invalid_tenant_identity_fails_closed():
    with pytest.raises(ValueError):
        audit_principal_x_ledger_eligibility(
            SessionDouble([]), company_id="not-uuid", loan_id=uuid4(),
        )
