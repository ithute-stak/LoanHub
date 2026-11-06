"""Built-image signature resolver contract tests."""
from services.signature_bridge_matching import SignatureCandidate, normalized_phone_aliases, resolve_candidates

def test_slash_phone_aliases():
    assert normalized_phone_aliases("58123456 / +26663123456 / 58123456") == ("26658123456", "26663123456")

def test_conflicting_signatures_blocked():
    result = resolve_candidates(company_id="tenant-a", candidates=[
        SignatureCandidate("sig-a", "client-a", "tenant-a"),
        SignatureCandidate("sig-b", "client-b", "tenant-a"),
    ])
    assert result["status"] == "conflict"
    assert result["auto_apply"] is False

def test_matching_never_signs():
    result = resolve_candidates(company_id="tenant-a", candidates=[
        SignatureCandidate("sig-a", "client-a", "tenant-a")
    ])
    assert result["status"] == "match"
    assert result["auto_apply"] is False

def test_company_isolation():
    result = resolve_candidates(company_id="tenant-a", candidates=[
        SignatureCandidate("sig-b", "client-b", "tenant-b")
    ])
    assert result["status"] == "not_found"
