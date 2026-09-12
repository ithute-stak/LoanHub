from database.schemas.origination import (
    ContractGenerateRequest,
    ContractRegenerateRequest,
)


def test_contract_generate_request_defaults_to_loanhub_standard() -> None:
    payload = ContractGenerateRequest()
    assert payload.template_style == "loanhub_standard"


def test_contract_generate_request_accepts_filizwa_style() -> None:
    payload = ContractGenerateRequest(template_style="filizwa_style")
    assert payload.template_style == "filizwa_style"


def test_contract_regenerate_request_accepts_style_or_none() -> None:
    assert ContractRegenerateRequest().template_style is None
    assert ContractRegenerateRequest(template_style="filizwa_style").template_style == "filizwa_style"
