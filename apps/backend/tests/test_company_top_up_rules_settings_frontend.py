from pathlib import Path


def test_company_settings_exposes_dedicated_top_up_rules_tab():
    root = Path(__file__).parents[2]
    page = root / "frontend" / "app" / "(dashboard)" / "company" / "settings" / "page.tsx"
    text = page.read_text(encoding="utf-8")

    assert '"top-up-rules"' in text
    assert "Loan top-up rules" in text
    assert "CompanyTopUpRulesSettings" in text
    assert "canManage={settings.canManage}" in text


def test_top_up_settings_control_every_company_policy_rule_without_stale_overwrite():
    root = Path(__file__).parents[2]
    component = (
        root
        / "frontend"
        / "app"
        / "(dashboard)"
        / "company"
        / "settings"
        / "_components"
        / "company-top-up-rules-settings.tsx"
    )
    text = component.read_text(encoding="utf-8")

    for field in (
        "allow_top_up",
        "top_up_min_paid_percent",
        "top_up_min_paid_installments",
        "top_up_owner_exception_enabled",
        "top_up_require_positive_history",
        "top_up_settle_existing_balance",
    ):
        assert field in text

    assert "originationApi.getPolicy()" in text
    assert "toOriginationPolicyUpdate(latest)" in text
    assert "originationApi.updatePolicy" in text
    assert "Only the company owner or company administrator" in text
    assert "other companies keep their own independent rules" in text
    assert 'min={0}' in text
    assert 'max={100}' in text
    assert 'max={120}' in text


def test_backend_keeps_top_up_policy_company_scoped_and_management_controlled():
    root = Path(__file__).parents[2]
    router = root / "backend" / "routers" / "origination.py"
    service = root / "backend" / "services" / "origination_service.py"
    schema = root / "backend" / "database" / "schemas" / "origination.py"

    router_text = router.read_text(encoding="utf-8")
    service_text = service.read_text(encoding="utf-8")
    schema_text = schema.read_text(encoding="utf-8")

    assert "ORIGINATION_POLICY_ROLES = COMPANY_MANAGEMENT_ROLES" in router_text
    assert "company_id=context.company_id" in router_text
    assert 'top_up_min_paid_percent: Decimal = Field(default=75, ge=0, le=100)' in schema_text
    assert 'top_up_min_paid_installments: int = Field(default=0, ge=0, le=120)' in schema_text
    assert 'allowed = bool(policy.allow_top_up and policy.top_up_settle_existing_balance)' in service_text
    assert "policy.top_up_require_positive_history" in service_text
    assert "policy.top_up_owner_exception_enabled" in service_text
