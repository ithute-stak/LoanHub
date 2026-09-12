from pathlib import Path

ROOT = Path(__file__).parents[1]
FRONTEND = ROOT.parent / "frontend"


def test_maturity_policy_is_safe_by_default() -> None:
    model = (ROOT / "database" / "models" / "maturity_recovery.py").read_text(encoding="utf-8")
    migration = (ROOT / "alembic" / "versions" / "c2r6t8v0w132_maturity_renewal_recovery.py").read_text(encoding="utf-8")
    assert "enabled = Column(Boolean, nullable=False, default=False" in model
    assert 'sa.Column("enabled", sa.Boolean(), server_default=sa.false()' in migration
    assert "include_processing_fee = Column(Boolean, nullable=False, default=False" in model


def test_renewal_preserves_master_loan_and_creates_no_disbursement() -> None:
    service = (ROOT / "services" / "maturity_renewal_service.py").read_text(encoding="utf-8")
    assert "LoanRenewalCycle(" in service
    assert "loan.renewal_cycle_count = cycle_number" in service
    assert "loan.total_repayable = money(loan.amount_paid) + money(renewed_total)" in service
    assert "PaymentTransaction(" not in service
    assert "LOAN_DISBURSEMENT" not in service


def test_superseded_installments_leave_live_payment_and_collections_queues() -> None:
    loan_service = (ROOT / "services" / "loan_service.py").read_text(encoding="utf-8")
    operations = (ROOT / "services" / "lending_operations_service.py").read_text(encoding="utf-8")
    collections = (ROOT / "routers" / "collections_recovery.py").read_text(encoding="utf-8")
    assert "RepaymentInstallment.is_superseded.is_(False)" in loan_service
    # getattr keeps historical test fixtures/backfills that predate the column compatible.
    assert 'getattr(installment, "is_superseded", False)' in loan_service
    assert "RepaymentInstallment.is_superseded.is_(False)" in operations
    assert "RepaymentInstallment.is_superseded.is_(False)" in collections
    assert "already been capitalised into a maturity renewal" in loan_service


def test_maintenance_processes_renewals_before_overdue_marking() -> None:
    source = (ROOT / "services" / "maintenance_service.py").read_text(encoding="utf-8")
    renewal_index = source.index("process_maturity_renewals")
    overdue_query_index = source.index("installments = (")
    assert renewal_index < overdue_query_index
    assert "process_collection_reminders" in source


def test_collection_actions_are_claimed_and_custom_action_is_supported() -> None:
    router = (ROOT / "routers" / "collections_recovery.py").read_text(encoding="utf-8")
    maturity_router = (ROOT / "routers" / "maturity_recovery.py").read_text(encoding="utf-8")
    assert "assert_or_claim_collection_case" in router
    assert "release_collection_case_claim" in router
    assert "custom_action_title" in router
    assert '"/collections/cases/{case_id}/claim"' in maturity_router
    assert "Record the date and time for the next recovery action" in router


def test_reminder_engine_has_day_before_and_due_day_deduplication() -> None:
    source = (ROOT / "services" / "collection_followup_service.py").read_text(encoding="utf-8")
    assert "local_now.hour < 7" in source
    assert "today + timedelta(days=1)" in source
    assert 'kind = "today"' in source
    assert "collection-reminder:" in source
    assert "deduplication_key" in source


def test_maturity_recovery_scheduler_is_started_by_api_lifecycle() -> None:
    scheduler = (ROOT / "services" / "maturity_recovery_scheduler.py").read_text(encoding="utf-8")
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "run_maturity_recovery_cycle" in scheduler
    assert "timeout=max(30, interval_seconds)" in scheduler
    assert "start_maturity_recovery_scheduler(60)" in main
    assert "stop_maturity_recovery_scheduler()" in main


def test_borrower_loan_and_payment_pages_have_phone_specific_layouts() -> None:
    loans = (FRONTEND / "app" / "(dashboard)" / "borrower" / "loans" / "page.tsx").read_text(encoding="utf-8")
    payments = (FRONTEND / "components" / "payments" / "cash-payments-page.tsx").read_text(encoding="utf-8")
    assert 'className="space-y-3 md:hidden"' in loans
    assert 'className="hidden overflow-x-auto rounded-2xl border md:block"' in loans
    assert "renewal_cycles" in loans
    assert 'className="space-y-3 p-4 md:hidden"' in payments
    assert 'className="hidden overflow-x-auto md:block"' in payments


def test_maturity_management_page_exposes_stop_resume_and_policy_warning() -> None:
    source = (FRONTEND / "app" / "(dashboard)" / "company" / "collections" / "maturity" / "page.tsx").read_text(encoding="utf-8")
    assert "Automatic maturity renewal" in source
    assert "Stop & recover" in source
    assert "Resume renewal" in source
    assert "signed loan agreement" in source
