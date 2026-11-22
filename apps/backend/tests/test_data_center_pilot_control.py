"""Privileged lifecycle control must stay opt-in and auditable."""
from argparse import Namespace
from pathlib import Path
from uuid import uuid4

import pytest

from scripts.data_center_pilot_control import (
    PilotControlBlocked, validate_request, run,
)


def test_operator_and_approval_are_always_required():
    cid = uuid4()
    for operator, approval in (("", "CHANGE-1"), ("admin", "")):
        with pytest.raises(PilotControlBlocked):
            validate_request(
                action="activate", company_id=cid, confirm_company=cid,
                apply=True, operator=operator, approval_ref=approval,
            )


def test_applying_any_transition_requires_exact_company_confirmation():
    cid = uuid4()
    for action in ("activate", "disable"):
        with pytest.raises(PilotControlBlocked, match="confirm-company"):
            validate_request(
                action=action, company_id=cid, confirm_company=uuid4(),
                apply=True, operator="change-manager", approval_ref="APPROVED-123",
            )
    validate_request(
        action="disable", company_id=cid, confirm_company=cid,
        apply=True, operator="change-manager", approval_ref="APPROVED-123",
    )


def test_dry_run_never_requires_apply_confirmation():
    validate_request(
        action="activate", company_id=uuid4(), confirm_company=None,
        apply=False, operator="change-manager", approval_ref="APPROVED-123",
    )


def test_control_requires_explicit_privileged_connection(monkeypatch):
    monkeypatch.delenv("LOANHUB_DC_OPERATOR_DATABASE_URL", raising=False)
    cid = uuid4()
    with pytest.raises(PilotControlBlocked, match="privileged"):
        run(Namespace(
            action="activate", company_id=cid, confirm_company=None,
            apply=False, operator="change-manager", approval_ref="APPROVED-123",
        ))


def test_runtime_app_role_never_becomes_operator():
    src = (Path(__file__).resolve().parents[1] /
           "scripts" / "data_center_pilot_control.py").read_text()
    assert 'row[0] == "loanhub_app"' in src
    assert 'SET TRANSACTION READ ONLY' in src
    assert 'if not args.apply:' in src
    assert 'confirm_company != company_id' in src
    assert "INSERT INTO public.loanhub_dc_pilot_audit" in src
    assert 'event_count != cursor' in src


def test_audit_migration_is_disabled_by_default():
    migration = (Path(__file__).resolve().parents[1] /
                 "alembic" / "versions" /
                 "dc20261122002_pilot_activation_audit.py").read_text()
    assert 'down_revision = "dc20261122001"' in migration
    assert 'CREATE' not in migration or "loanhub_dc_pilot_audit" in migration
    assert "ENABLED ROW LEVEL SECURITY" not in migration
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "op.create_table(" in migration
    assert "loanhub_dc_capture SET enabled" not in migration
