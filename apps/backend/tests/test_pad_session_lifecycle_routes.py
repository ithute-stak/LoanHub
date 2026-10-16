"""Regression guards for the pad session HTTP lifecycle contract."""
from pathlib import Path

ROUTER = Path(__file__).resolve().parents[1] / "routers" / "contract_email_otp.py"


def test_pad_cancel_requires_company_branch_and_operator_scope():
    source = ROUTER.read_text()
    section = source.split("def cancel_pad_signing_session(", 1)[1]
    assert "require_tenant_roles(context, CONTRACT_SIGNING_ROLES)" in section
    assert "_contract(db, context=context, contract_id=contract_id)" in section
    for requirement in (
        "ContractPadSigningSession.company_id == context.company_id",
        "ContractPadSigningSession.contract_id == contract.id",
        "ContractPadSigningSession.operator_user_id == context.user.id",
        ".with_for_update()",
    ):
        assert requirement in section
    assert 'if row.status == "completed":' in section
    assert '"capture_enabled": False' in section


def test_pad_status_invalidates_expired_or_revised_document():
    source = ROUTER.read_text()
    section = source.split("def pad_signing_session_status(", 1)[1].split(
        "@router.post(\"/contracts/{contract_id}/pad/sessions/{session_id}/cancel\")", 1
    )[0]
    assert "row.contract_hash != contract.contract_hash" in section
    assert "row.status = \"expired\" if expired else \"cancelled\"" in section
    assert "db.commit()" in section
