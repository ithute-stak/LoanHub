from types import SimpleNamespace

from services import contract_service


def _rebuilt_terms() -> dict:
    return {
        "company": {"name": "LoanHub Lender", "phone": "59000000"},
        "branch": {"name": "Maseru"},
        "borrower": {"name": "Borrower One"},
        "bank_account": {"bank_name": "Example Bank"},
        "loan_reference": "LN-NEW",
        "principal_amount": "500.00",
    }


def test_repair_legacy_contract_terms_rebuilds_missing_sections(monkeypatch):
    monkeypatch.setattr(contract_service, "build_terms", lambda _db, _loan: _rebuilt_terms())
    contract = SimpleNamespace(
        loan=object(),
        loan_id="loan-id",
        contract_hash=None,
        terms_snapshot={
            "loan_reference": "LN-HISTORIC",
            "principal_amount": "400.00",
        },
    )

    repaired = contract_service._repair_legacy_terms_snapshot(object(), contract)

    assert repaired["company"]["name"] == "LoanHub Lender"
    assert repaired["branch"]["name"] == "Maseru"
    assert repaired["borrower"]["name"] == "Borrower One"
    assert repaired["bank_account"]["bank_name"] == "Example Bank"
    assert repaired["loan_reference"] == "LN-HISTORIC"
    assert repaired["principal_amount"] == "400.00"
    assert contract.terms_snapshot == repaired
    assert contract.contract_hash


def test_repair_legacy_contract_terms_preserves_complete_snapshot(monkeypatch):
    original = {
        "company": {"name": "Historic lender"},
        "branch": {"name": "Historic branch"},
        "borrower": {"name": "Historic borrower"},
        "bank_account": {"bank_name": "Historic bank"},
    }
    monkeypatch.setattr(
        contract_service,
        "build_terms",
        lambda *_args: (_ for _ in ()).throw(AssertionError("should not rebuild")),
    )
    contract = SimpleNamespace(terms_snapshot=original, loan=None, loan_id="loan-id")

    assert contract_service._repair_legacy_terms_snapshot(object(), contract) == original
