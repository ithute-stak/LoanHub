from types import SimpleNamespace
from uuid import uuid4

from scripts.ithutepay_master_company_preflight import inspect_single_company


class FakeDb:
    def __init__(self, count, company=None):
        self.count = count
        self.company = company
        self.queries = []

    def scalar(self, statement):
        self.queries.append(statement)
        return self.count if len(self.queries) == 1 else self.company


def test_no_company_is_not_linked():
    result = inspect_single_company(FakeDb(0))
    assert result["ready_for_identity_review"] is False
    assert result["company_count"] == 0
    assert "company_id" not in result


def test_multiple_companies_never_auto_select():
    result = inspect_single_company(FakeDb(2))
    assert result["ready_for_identity_review"] is False
    assert "company_id" not in result


def test_exact_single_company_returns_identity_but_never_activates_money():
    company_id = uuid4()
    company = SimpleNamespace(
        id=company_id,
        name="Single Company Ltd",
        status=SimpleNamespace(value="approved"),
        is_active=True,
    )
    result = inspect_single_company(FakeDb(1, company))
    assert result["ready_for_identity_review"] is True
    assert result["company_id"] == str(company_id)
    assert result["company_name"] == "Single Company Ltd"
    assert result["platform_fee"] == "0.00"
    assert result["money_movement_enabled"] is False
    assert result["shared_custody_approved"] is False
