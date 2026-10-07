from pathlib import Path

from routers.company_operating_system import CAPABILITIES

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_all_thirty_four_company_capabilities_are_governed():
    assert len(CAPABILITIES) == 34
    assert [item[0] for item in CAPABILITIES] == list(range(1, 35))
    keys = {item[1] for item in CAPABILITIES}
    assert {
        "executive_command", "crm", "credit_committee", "advanced_risk", "collateral",
        "treasury_liquidity", "portfolio_alm", "pricing_lab", "collections_strategy",
        "legal_recovery", "complaints", "communications", "marketing", "agents",
        "employer_partnerships", "reconciliation", "approval_workflows", "procurement",
        "assets", "compliance", "internal_audit", "budgeting", "profitability", "targets",
        "business_continuity", "integrations", "api_webhooks", "document_automation",
        "board_packs", "data_assistant", "govstack_interoperability",
        "data_governance", "responsible_ai", "regulatory_reporting",
    } == keys


def test_new_persistence_does_not_duplicate_financial_ledgers():
    model = text(BACKEND / "database/models/company_operating_system.py")
    assert "CompanyOperatingRecord" in model
    assert "CompanyAPIKey" in model
    assert "CompanyWebhookEndpoint" in model
    assert "principal_amount" not in model
    assert "total_repayable" not in model
    assert "payment_transactions" not in model
    assert "key_hash" in model and "secret_hash" in model


def test_migration_extends_current_single_head():
    migration = text(BACKEND / "alembic/versions/f5u9w1y3z465_company_operating_system.py")
    assert 'revision: str = "f5u9w1y3z465"' in migration
    assert 'down_revision: Union[str, Sequence[str], None] = "e4t8v0x2y354"' in migration
    assert "company_operating_records" in migration
    assert "company_api_keys" in migration
    assert "company_webhook_endpoints" in migration


def test_router_is_registered_and_tenant_role_governed():
    aggregate = text(BACKEND / "api/v1/router.py")
    router = text(BACKEND / "routers/company_operating_system.py")
    assert "company_operating_system.router" in aggregate
    assert 'prefix="/company-operating-system"' in router
    assert "get_tenant_context" in router
    assert "require_tenant_roles" in router
    assert "COMPANY_MANAGEMENT_ROLES" in router
    assert "key_hash=hashlib.sha256" in router
    assert "secret_hash=hashlib.sha256" in router


def test_company_operating_links_cannot_cross_tenant_or_branch_scope():
    router = text(BACKEND / "routers/company_operating_system.py")
    assert "def _validate_record_links" in router
    assert "def _ensure_loan_scope" in router
    assert "def _ensure_assignee_scope" in router
    assert "Loan is not available in the active company/branch scope" in router
    assert "Assigned user is not active staff of the current company" in router
    assert "Assigned staff member belongs to another branch" in router
    assert "The selected loan does not belong to the selected borrower" in router
    assert "_validate_record_links(db, context, payload)" in router


def test_branch_dashboard_does_not_aggregate_company_wide_payment_volume():
    router = text(BACKEND / "routers/company_operating_system.py")
    assert "PaymentTransaction.loan_id.in_(branch_loan_ids)" in router
    assert "if context.staff and context.staff.role not in COMPANY_MANAGEMENT_ROLES and context.branch_id" in router
    assert "payments_query = payments_query.filter(PaymentTransaction.id.is_(None))" in router


def test_financial_engines_are_reused_not_reimplemented():
    router = text(BACKEND / "routers/company_operating_system.py")
    assert "calculate_loan_terms" in router
    assert "generate_monthly_due_dates" in router
    assert "CollectionCase" in router
    assert "ReconciliationException" in router
    assert "ComplianceCase" in router
    assert "WorkflowInstance" in router
    assert "TreasuryEntry" in router
    assert "RepaymentInstallment" in router


def test_risk_profit_and_assistant_have_safety_boundaries():
    router = text(BACKEND / "routers/company_operating_system.py")
    assert "not a credit-bureau score" in router
    assert "not an automatic lending decision" in router
    assert "Accounting remains authoritative" in router
    assert "does not make credit approvals, legal decisions or accounting postings" in router


def test_company_command_centre_frontend_exposes_operational_surfaces():
    component = text(FRONTEND / "components/company/company-operating-system-centre.tsx")
    page = text(FRONTEND / "app/(dashboard)/company/command-centre/page.tsx")
    dashboard = text(FRONTEND / "app/(dashboard)/company/page.tsx")
    assert "CompanyOperatingSystemCentre" in page
    assert "/company/command-centre" in dashboard
    for label in (
        "Executive Command Centre",
        "All 34 company capabilities",
        "Operating workflows",
        "Product & pricing laboratory",
        "API keys & webhooks",
        "Board / management pack",
        "Company Data Assistant",
        "Document automation",
    ):
        assert label in component


def test_all_missing_workflow_modules_have_ui_entry_points():
    component = text(FRONTEND / "components/company/company-operating-system-centre.tsx")
    for module in (
        "crm", "credit_committee", "collateral", "legal_recovery", "complaints",
        "communications", "marketing", "agents", "employer_partnerships", "procurement",
        "assets", "internal_audit", "budgeting", "targets", "business_continuity",
        "integrations", "document_automation", "board_packs",
    ):
        assert f'["{module}",' in component


def test_generated_report_metrics_normalize_decimal_snapshots():
    reporting = text(BACKEND / "database/models/reporting.py")
    assert "_normalize_generated_report_metrics" in reporting
    assert 'event.listen(GeneratedReport, "before_insert"' in reporting


def test_management_decision_accountability_workflow_is_auditable_and_independently_verified():
    router = (ROOT / "backend" / "routers" / "company_operating_system.py").read_text(encoding="utf-8")
    schema = (ROOT / "backend" / "database" / "schemas" / "company_operating_system.py").read_text(encoding="utf-8")
    api = (ROOT / "frontend" / "api" / "companyOperatingSystem.ts").read_text(encoding="utf-8")
    panel = (ROOT / "frontend" / "components" / "company" / "management-command-intelligence-panel.tsx").read_text(encoding="utf-8")

    assert "class ManagementActionCreate" in schema
    assert "class ManagementDecisionCreate" in schema
    assert "class ManagementResolutionCreate" in schema
    assert "class ManagementVerificationCreate" in schema

    assert '@router.get("/management-actions")' in router
    assert '@router.post("/management-actions"' in router
    assert '@router.post("/management-actions/{record_id}/decisions")' in router
    assert '@router.post("/management-actions/{record_id}/resolve")' in router
    assert '@router.post("/management-actions/{record_id}/verify")' in router
    assert '@router.post("/management-actions/escalate-overdue")' in router
    assert "Independent verification requires a different user from the resolver" in router
    assert '"source_signal"' in router
    assert '"timeline"' in router
    assert '"overdue_escalation"' in router
    assert "Escalation changes workflow priority only" in router

    assert "createManagementAction" in api
    assert "recordManagementDecision" in api
    assert "resolveManagementAction" in api
    assert "verifyManagementAction" in api
    assert "escalateOverdueManagementActions" in api

    assert "Assign & track" in panel
    assert "Decision & accountability workflow" in panel
    assert "Record decision" in panel
    assert "Verify independently" in panel
    assert "Escalate overdue actions" in panel


def test_board_governance_pack_combines_verified_management_finance_risk_and_audit_evidence():
    router = (ROOT / "backend" / "routers" / "company_operating_system.py").read_text(encoding="utf-8")
    api = (ROOT / "frontend" / "api" / "companyOperatingSystem.ts").read_text(encoding="utf-8")
    centre = (ROOT / "frontend" / "components" / "company" / "company-operating-system-centre.tsx").read_text(encoding="utf-8")

    assert "build_management_command_intelligence" in router
    assert "accounting_audit_compliance_pack" in router
    assert "financial_ratio_analysis" in router
    assert "treasury_cash_forecast" in router
    assert '@router.get("/board-packs")' in router
    assert '@router.post("/board-packs")' in router
    assert '"report_type="board_governance_pack"' in router
    assert '"accountability": accountability' in router
    assert '"board_attention": board_attention' in router
    assert '"prior_pack_summary": prior_summary' in router
    assert "Critical accountability cases remain unresolved" in router
    assert "30-day downside liquidity forecast falls below zero" in router
    assert "does not constitute an audit opinion" in router

    assert "BoardGovernancePackMetrics" in api
    assert "listCompanyBoardPacks" in api
    assert "generateCompanyBoardPack" in api

    assert "Board & executive governance pack" in centre
    assert "Board attention" in centre
    assert "Accountability position" in centre
    assert "Audit & control" in centre
    assert "Treasury outlook" in centre
    assert "Prior pack comparison" in centre
    assert "Governance pack history" in centre


def test_regulatory_prudential_intelligence_is_configurable_evidence_based_and_non_assumptive():
    router = (ROOT / "backend" / "routers" / "company_operating_system.py").read_text(encoding="utf-8")
    schema = (ROOT / "backend" / "database" / "schemas" / "company_operating_system.py").read_text(encoding="utf-8")
    api = (ROOT / "frontend" / "api" / "companyOperatingSystem.ts").read_text(encoding="utf-8")
    centre = (ROOT / "frontend" / "components" / "company" / "company-operating-system-centre.tsx").read_text(encoding="utf-8")

    assert "class PrudentialProfileUpsert" in schema
    assert "class RelatedPartyRegisterCreate" in schema
    assert "class PrudentialFilingReadinessCreate" in schema

    assert "def _prudential_intelligence(" in router
    assert '@router.put("/prudential/profile")' in router
    assert '@router.post("/prudential/related-parties"' in router
    assert '@router.post("/prudential/filings"' in router
    assert '@router.get("/prudential")' in router
    assert '@router.post("/prudential/evidence-pack")' in router
    assert '"report_type="prudential_evidence_pack"' in router
    assert "Capital-to-portfolio exposure is a management monitoring proxy" in router
    assert "Related-party status is never inferred" in router
    assert '"status": "not_assessed"' in router
    assert '"single_borrower_exposure_to_equity"' in router
    assert '"related_party_exposure_to_equity"' in router
    assert '"ecl_coverage_of_stage3_exposure"' in router
    assert '"minimum_projected_liquidity"' in router

    assert "PrudentialIntelligence" in api
    assert "getPrudentialIntelligence" in api
    assert "savePrudentialProfile" in api
    assert "createRelatedPartyRegister" in api
    assert "createPrudentialFiling" in api
    assert "generatePrudentialEvidencePack" in api

    assert "Regulatory & prudential intelligence" in centre
    assert "Prudential framework configuration" in centre
    assert "Related-party register" in centre
    assert "Regulatory filing readiness" in centre
    assert "Generate evidence pack" in centre


def test_prudential_stress_testing_is_nonposting_transparent_and_threshold_driven():
    router = (ROOT / "backend" / "routers" / "company_operating_system.py").read_text(encoding="utf-8")
    schema = (ROOT / "backend" / "database" / "schemas" / "company_operating_system.py").read_text(encoding="utf-8")
    api = (ROOT / "frontend" / "api" / "companyOperatingSystem.ts").read_text(encoding="utf-8")
    centre = (ROOT / "frontend" / "components" / "company" / "company-operating-system-centre.tsx").read_text(encoding="utf-8")

    assert "class PrudentialStressScenarioRequest" in schema
    assert "class PrudentialStressPackRequest" in schema

    assert "DEFAULT_PRUDENTIAL_STRESS_SCENARIOS" in router
    assert "def _prudential_stress_scenario(" in router
    assert "def _prudential_stress_pack(" in router
    assert '@router.post("/prudential/stress-test")' in router
    assert '@router.post("/prudential/stress-evidence-pack")' in router
    assert '"report_type="prudential_stress_evidence_pack"' in router
    assert '"incremental_allowance"' in router
    assert '"equity_erosion"' in router
    assert '"stressed_equity"' in router
    assert '"minimum_projected_cash"' in router
    assert "Stress testing is a non-posting management simulation" in router
    assert "Results are only assessed against explicitly configured prudential thresholds" in router

    assert "PrudentialStressPack" in api
    assert "runPrudentialStressTest" in api
    assert "generatePrudentialStressEvidencePack" in api

    assert "Scenario capital & regulatory stress testing" in centre
    assert "Run built-in stress scenarios" in centre
    assert "Run custom scenario" in centre
    assert "Generate stress evidence pack" in centre
    assert "Equity erosion" in centre
