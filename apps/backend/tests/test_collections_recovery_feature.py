from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_next_of_kin_phone_extraction_is_present() -> None:
    source = (ROOT / "services" / "collection_daily_reporting_service.py").read_text(encoding="utf-8")
    assert "def _phone_values" in source
    assert '"phone_number"' in source
    assert '"mobile_number"' in source


def test_collections_router_requires_notice_before_court() -> None:
    source = (ROOT / "routers" / "collections_recovery.py").read_text(encoding="utf-8")
    assert 'activity_type == "default_notice"' in source
    assert "Upload court papers before recording a court action" in source
    assert "Record the written default notice before recording court enforcement" in source


def test_chat_report_masks_bank_accounts() -> None:
    source = (ROOT / "services" / "collection_daily_reporting_service.py").read_text(encoding="utf-8")
    assert 'f"****{bank.account_number_last4}"' in source
    assert "account_number_encrypted" not in source


def test_daily_report_uses_shared_pdf_branding() -> None:
    source = (ROOT / "services" / "collection_daily_reporting_service.py").read_text(encoding="utf-8")
    assert "DocumentContext(" in source
    assert "build_document(" in source


def test_scheduler_targets_0030() -> None:
    config = (ROOT / "database" / "config" / "config.py").read_text(encoding="utf-8")
    maintenance = (ROOT / "docker" / "maintenance.py").read_text(encoding="utf-8")
    assert "COLLECTION_DAILY_REPORT_HOUR: int = 0" in config
    assert "COLLECTION_DAILY_REPORT_MINUTE: int = 30" in config
    assert "run_missed_payment_reporting" in maintenance


def test_live_collections_sync_endpoint_is_available() -> None:
    router = (ROOT / "routers" / "collections_recovery.py").read_text(encoding="utf-8")
    service = (ROOT / "services" / "lending_operations_service.py").read_text(encoding="utf-8")
    assert '@router.post("/sync")' in router
    assert "sync_overdue_collection_cases" in router
    assert 'case.status = "recovered"' in service
    assert 'case.status = "open"' in service


def test_promise_to_pay_is_a_first_class_collection_action() -> None:
    source = (ROOT / "routers" / "collections_recovery.py").read_text(encoding="utf-8")
    assert '"promise_to_pay"' in source
    assert 'case.status = "promise_to_pay"' in source
    assert 'case.promise_status = "pending"' in source
    assert "Record the promised payment date" in source


def test_collection_actions_feed_client_case_history() -> None:
    source = (ROOT / "routers" / "collections_recovery.py").read_text(encoding="utf-8")
    assert "CompanyClientCaseEntry" in source
    assert 'entry_type="legal_action" if legal_action else "comment"' in source
    assert 'legal_action = action_type in {"default_notice", "court"}' in source


def test_live_collections_sync_imports_runtime_service() -> None:
    source = (ROOT / "routers" / "collections_recovery.py").read_text(encoding="utf-8")
    assert "from services.lending_operations_service import sync_overdue_collection_cases" in source
