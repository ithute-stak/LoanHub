from services.contract_email_otp_service import _otp_digest, mask_email


def test_mask_email_preserves_domain_without_exposing_local_part():
    assert mask_email("borrower@example.com") == "b*******@example.com"
    assert mask_email("a@example.com") == "a***@example.com"


def test_otp_digest_is_deterministic_and_bound_to_challenge():
    contract_id = "11111111-2222-3333-4444-555555555555"
    first = _otp_digest(contract_id, "ESIGN-ABC", "123456")
    same = _otp_digest(contract_id, "ESIGN-ABC", "123456")
    different_code = _otp_digest(contract_id, "ESIGN-ABC", "654321")
    different_reference = _otp_digest(contract_id, "ESIGN-XYZ", "123456")

    assert first == same
    assert first != different_code
    assert first != different_reference
    assert "123456" not in first
