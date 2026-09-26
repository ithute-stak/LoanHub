from pathlib import Path
from uuid import uuid4

from services.signed_contract_intake import ClientIdentity, match_against_identities


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[1]


def _identity(*, name: str, national_id: str, contract: str, loan: str, application: str):
    account_id = uuid4()
    return account_id, ClientIdentity(
        account_id=account_id,
        borrower_id=uuid4(),
        branch_id=uuid4(),
        display_name=name,
        national_id=national_id,
        contract_numbers={contract},
        loan_references={loan},
        application_references={application},
    )


def test_name_alone_never_auto_files_a_signed_contract():
    account_id, identity = _identity(
        name="Mpho Test",
        national_id="123456789012",
        contract="LHC-2026-001",
        loan="LN-2026-001",
        application="APP-2026-001",
    )
    result = match_against_identities({account_id: identity}, "Borrower: Mpho Test")
    assert result.status == "review"
    assert result.account_id is None
    assert "name alone" in result.reason


def test_contract_number_auto_files_to_one_client_even_with_scan_punctuation_changes():
    account_id, identity = _identity(
        name="Mpho Test",
        national_id="123456789012",
        contract="LHC-2026-001",
        loan="LN-2026-001",
        application="APP-2026-001",
    )
    result = match_against_identities(
        {account_id: identity},
        "LOAN AGREEMENT\nContract No: LHC 2026 001\nSigned by borrower",
    )
    assert result.status == "filed"
    assert result.account_id == account_id
    assert result.evidence_types == ["contract_number"]


def test_conflicting_strong_identifiers_are_sent_to_review():
    first_id, first = _identity(
        name="First Client",
        national_id="111111111111",
        contract="LHC-ONE-001",
        loan="LN-ONE-001",
        application="APP-ONE-001",
    )
    second_id, second = _identity(
        name="Second Client",
        national_id="222222222222",
        contract="LHC-TWO-002",
        loan="LN-TWO-002",
        application="APP-TWO-002",
    )
    result = match_against_identities(
        {first_id: first, second_id: second},
        "Contract LHC-ONE-001 National ID 222222222222",
    )
    assert result.status == "review"
    assert result.account_id is None
    assert "conflict" in result.reason.lower()


def test_global_intake_preserves_original_scan_and_uses_client_file_link():
    router = (BACKEND_ROOT / "routers" / "signed_contract_intake.py").read_text(encoding="utf-8")
    service = (BACKEND_ROOT / "services" / "signed_contract_intake.py").read_text(encoding="utf-8")
    api_router = (BACKEND_ROOT / "api" / "v1" / "router.py").read_text(encoding="utf-8")

    assert 'SIGNED_CONTRACT_CATEGORY = "borrower_signed_contract"' in service
    assert 'CLIENT_FILE_LINK_TYPE = "company_borrower_account"' in service
    assert "store_bytes(" in router
    assert "extract_contract_text(content, record.mime_type)" in router
    assert 'record.linked_entity_type = CLIENT_FILE_LINK_TYPE' in router
    assert 'record.linked_entity_id = str(match.account_id)' in router
    assert "signed_contract_intake.router" in api_router


def test_unmatched_contracts_go_to_review_and_exact_duplicates_are_detected():
    router = (BACKEND_ROOT / "routers" / "signed_contract_intake.py").read_text(encoding="utf-8")
    service = (BACKEND_ROOT / "services" / "signed_contract_intake.py").read_text(encoding="utf-8")

    assert 'SIGNED_CONTRACT_REVIEW_CATEGORY = "signed_contract_review"' in service
    assert "find_existing_intake_file" in router
    assert 'status="duplicate"' in router
    assert '@router.get("/review"' in router
    assert '@router.post("/review/{file_id}/assign"' in router


def test_signed_contract_ocr_is_local_and_bounded():
    service = (BACKEND_ROOT / "services" / "signed_contract_intake.py").read_text(encoding="utf-8")
    dockerfile = (BACKEND_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert 'shutil.which("tesseract")' in service
    assert 'shutil.which("pdftoppm")' in service
    assert "MAX_OCR_PAGES = 4" in service
    assert "httpx" not in service
    assert "requests" not in service
    assert "tesseract-ocr" in dockerfile
    assert "poppler-utils" in dockerfile


def test_frontend_exposes_global_upload_and_manual_review_workflow():
    page = REPO_ROOT / "apps" / "frontend" / "app" / "(dashboard)" / "company" / "contracts" / "signed-upload" / "page.tsx"
    component = REPO_ROOT / "apps" / "frontend" / "components" / "contracts" / "signed-contract-intake.tsx"
    api = REPO_ROOT / "apps" / "frontend" / "api" / "signedContracts.ts"

    assert page.exists()
    source = component.read_text(encoding="utf-8")
    api_source = api.read_text(encoding="utf-8")
    assert "Global Signed Contract Upload" in source
    assert "Signed Contracts" in source
    assert "A name alone is never enough" in source
    assert "Needs review" in source
    assert "File under Signed Contracts" in source
    assert '"/signed-contracts/intake"' in api_source
    assert '"/signed-contracts/review"' in api_source
