from database.schemas.lelefa_paygate import (
    LelefaPayGateConfigurationRead,
    LelefaPayGateConfigurationUpdate,
)


def test_lelefapaygate_admin_read_contract_never_contains_plaintext_secret_fields():
    fields = set(LelefaPayGateConfigurationRead.model_fields)
    assert "api_key" not in fields
    assert "webhook_secret" not in fields
    assert {"api_key_configured", "api_key_hint", "webhook_secret_configured"} <= fields


def test_lelefapaygate_admin_update_contract_supports_rotation_without_echoing():
    payload = LelefaPayGateConfigurationUpdate(
        enabled=False,
        base_url="https://pay.example.com/api/v1",
        api_key="ipb_test_1234567890abcdef",
        webhook_secret="whsec_1234567890abcdef",
    )
    assert payload.api_key.startswith("ipb_test_")
    assert payload.webhook_secret.startswith("whsec_")
    assert payload.request_signing_enabled is True
