from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[1]


def test_lelefa_managed_collections_router_is_registered():
    source = (BACKEND_ROOT / "api" / "v1" / "router.py").read_text(encoding="utf-8")
    assert "lelefa_managed_collections," in source
    assert "lelefa_managed_collections.router," in source


def test_bridge_is_opt_in_and_automatic_inside_ithute():
    service = (BACKEND_ROOT / "services" / "lelefa_managed_collections.py").read_text(encoding="utf-8")
    router = (BACKEND_ROOT / "routers" / "lelefa_managed_collections.py").read_text(encoding="utf-8")
    assert '"min_days_past_due": 120' in service
    assert '"share_national_id": False' in service
    assert '"share_employment": False' in service
    assert 'LELEFA_API_BASE_URL = "https://api.lelefadebtcollectors.co.ls"' in service
    assert 'LOANHUB_API_BASE_URL = "https://api.loanhub.co.ls/api/v1"' in service
    assert 'BRIDGE_TOKEN_HEADER = "X-Ithute-Bridge-Token"' in service
    assert "new_bridge_token" in service
    assert "X-Idempotency-Key" in service
    assert "LELEFA_DCA_BASE_URL" not in service
    assert "LELEFA_DCA_SHARED_SECRET" not in service
    assert '"bridge_status": "ithute_internal_ready"' in router


def test_referral_requires_explicit_case_selection_and_agreement():
    source = (BACKEND_ROOT / "routers" / "lelefa_managed_collections.py").read_text(encoding="utf-8")
    assert "case_ids: list[UUID]" in source
    assert "Lelefa managed collections is switched off" in source
    assert 'row.status = "offer_received"' in source
    assert 'payload.decision == "accept"' in source
    assert '"share_bank_account_numbers": False' in source
    assert '"share_documents_automatically": False' in source


def test_referral_token_is_private_and_verified_before_callbacks():
    source = (BACKEND_ROOT / "routers" / "lelefa_managed_collections.py").read_text(encoding="utf-8")
    assert 'public_data.pop("bridge_token", None)' in source
    assert '"bridge_token": new_bridge_token()' in source
    assert '@router.post("/integrations/referrals/verify")' in source
    assert "bridge_token_matches(_stored_bridge_token(row), x_ithute_bridge_token)" in source
    assert "bridge_token=bridge_token" in source


def test_company_workspace_exposes_policy_candidates_referrals_and_offers():
    page = (
        REPO_ROOT
        / "apps"
        / "frontend"
        / "app"
        / "(dashboard)"
        / "company"
        / "collections"
        / "lelefa"
        / "page.tsx"
    ).read_text(encoding="utf-8")
    assert "Lelefa managed collections" in page
    assert "Select all eligible" in page
    assert "Send request to Lelefa" in page
    assert "Lelefa commercial offer" in page
    assert "Accept offer" in page
