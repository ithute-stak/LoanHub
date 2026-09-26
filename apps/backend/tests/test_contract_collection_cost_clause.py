from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_SERVICE = BACKEND_ROOT / "services" / "contract_service.py"
COLLECTION_SERVICE = BACKEND_ROOT / "services" / "lelefa_managed_collections.py"


def test_new_contracts_use_versioned_explicit_collection_wording() -> None:
    source = CONTRACT_SERVICE.read_text(encoding="utf-8")

    assert 'EXPLICIT_COLLECTION_TEMPLATE_VERSION = "3.2-explicit-collection-cost-basis"' in source
    assert 'terms["template_version"] = EXPLICIT_COLLECTION_TEMPLATE_VERSION' in source
    assert "Existing contracts are deliberately left untouched" in source


def test_clause_11_expressly_places_qualifying_external_recovery_costs_on_borrower() -> None:
    source = CONTRACT_SERVICE.read_text(encoding="utf-8")

    assert '"Default, debt collection and recovery costs"' in source
    assert "lawfully authorised debt collector" in source
    assert "the borrower expressly" in source
    assert "agrees to pay the lawful and reasonable external debt-collection and recovery costs" in source
    assert "actually incurred by the lender" in source
    assert "those qualifying recovery costs are for" in source
    assert "the borrower's account" in source
    assert "No collection or legal charge becomes due merely because an" in source
    assert "permitted by applicable law" in source


def test_configured_collection_commission_has_specific_signed_contract_basis() -> None:
    source = CONTRACT_SERVICE.read_text(encoding="utf-8")

    assert '"Agreed collection commission after external referral"' in source
    assert "borrower expressly agrees to pay the following collection commission" in source
    assert "account is actually referred for" in source
    assert "collection_charge_disclosure(policy)" in source
    assert '"separately shown on the borrower\'s account' in source
    assert "payable only to the extent" in source
    assert "permitted by applicable law" in source


def test_new_contract_discloses_when_no_separate_percentage_commission_is_agreed() -> None:
    source = CONTRACT_SERVICE.read_text(encoding="utf-8")

    assert '"Separate collection commission"' in source
    assert "No separate percentage-based or fixed collection commission is agreed" in source
    assert "Clause 11 still records the borrower's responsibility" in source


def test_collection_commission_engine_still_requires_signed_contract_and_external_referral() -> None:
    source = COLLECTION_SERVICE.read_text(encoding="utf-8")

    assert '"requires_signed_contract": True' in source
    assert '"trigger": "external_collection_referral"' in source
    assert 'result["status"] = "contract_not_signed"' in source
    assert 'result["status"] = "assessable_on_external_referral"' in source
