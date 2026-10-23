"""Reconciliation must check provider status and identity, not just requested query filter."""
from services.cdas_operation_ledger import _provider_status_matches


def test_matching_status_is_accepted():
    assert _provider_status_matches({"DeductionStatus": 4}, 4)
    assert _provider_status_matches({"DeductionStatus": "7"}, 7)


def test_wrong_or_missing_status_is_rejected():
    assert not _provider_status_matches({"DeductionStatus": 3}, 4)
    assert not _provider_status_matches({"DeductionID": 50}, 4)
    assert not _provider_status_matches({"DeductionStatus": None}, 4)
    assert not _provider_status_matches({"DeductionStatus": "Approved"}, 4)
    assert not _provider_status_matches({"DeductionStatus": True}, 1)


def test_alternate_documented_provider_status_key():
    assert _provider_status_matches({"deductionStatus": 6}, 6)
