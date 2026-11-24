"""Phase 79 safety contracts: no PII, no DDL, no implicit approval."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import pytest

from services.identity_index_rollout_preflight import IndexRolloutPreflightError
from scripts.report_identity_index_rollout import (
    render_approval_report, generate_read_only_report, main,
)


def scan(*, collisions=(0, 0, 0, 0), blanks=(0, 0, 0, 0)):
    return SimpleNamespace(
        checked_at=datetime(2026, 11, 18, tzinfo=timezone.utc),
        collision_groups=collisions,
        empty_identity_counts=blanks,
        invalid_existing_index_names=("uq_people_national_id_normalized",),
        requires_manual_legacy_reconciliation=bool(
            any(collisions) or any(blanks)),
        operator_review_candidate=not (any(collisions) or any(blanks)),
        proposed_statements=(
            "CREATE UNIQUE INDEX CONCURRENTLY uq_people_national_id_normalized "
            "ON people (lower(btrim(national_id)))",
        ),
    )


def test_clean_report_is_never_permission_to_migrate_or_register():
    report = render_approval_report(
        scan(), database_role="identity_audit_reader",
        database_name="loanhub_sandbox",
        legacy_audit=SimpleNamespace(national_id_overlap_groups=0,
                                     passport_overlap_groups=0,
                                     repeated_legacy_passport_groups=0),
        legacy_triage=SimpleNamespace(
            matching_identity_groups=0, linked_only_groups=0,
            mixed_linkage_groups=0, unlinked_only_groups=0,
            unlinked_legacy_rows=0,
            unlinked_with_single_borrower_and_company_account=0,
            unlinked_needing_manual_review=0))
    assert report["operator_review_candidate"]
    assert not report["safe_to_execute"]
    assert not report["production_approved"]
    assert not report["registration_enabled"]
    assert len(report["manual_approvals_required"]) == 4


def test_collisions_and_blanks_require_manual_reconciliation():
    report = render_approval_report(
        scan(collisions=(1, 0, 0, 0), blanks=(0, 0, 2, 0)),
        database_role="identity_audit_reader",
        database_name="loanhub_sandbox")
    assert report["requires_manual_legacy_reconciliation"]
    assert report["collision_groups"]["national_id"] == 1
    assert report["blank_identity_rows"]["phone"] == 2
    assert not report["operator_review_candidate"]


def test_unreliable_evidence_refused():
    for invalid in ((-1, 0, 0, 0), (None, 0, 0, 0), (True, 0, 0, 0)):
        with pytest.raises(IndexRolloutPreflightError):
            render_approval_report(scan(collisions=invalid),
                                   database_role="identity_audit_reader",
                                   database_name="loanhub_sandbox")


def test_no_configuration_prevents_db_connection(monkeypatch):
    monkeypatch.delenv("LOANHUB_IDENTITY_AUDIT_ACK", raising=False)
    with patch("scripts.report_identity_index_rollout.create_engine") as engine:
        with pytest.raises(SystemExit):
            main([])
    engine.assert_not_called()


def test_non_postgresql_engine_refused_and_disposed():
    engine = MagicMock()
    engine.dialect.name = "sqlite"
    with patch("scripts.report_identity_index_rollout.create_engine",
               return_value=engine):
        with pytest.raises(IndexRolloutPreflightError, match="PostgreSQL"):
            generate_read_only_report(
                "sqlite://", expected_role="identity_audit_reader")
    engine.connect.assert_not_called()
    engine.dispose.assert_called_once()


def test_missing_role_refused_without_connection():
    with patch("scripts.report_identity_index_rollout.create_engine") as engine:
        with pytest.raises(IndexRolloutPreflightError):
            generate_read_only_report(
                "postgresql://synthetic-host/test", expected_role="")
    engine.assert_not_called()


def test_report_output_refuses_overwrite_without_db_writes(tmp_path, monkeypatch):
    destination = tmp_path / "approval.json"
    destination.write_text("existing")
    monkeypatch.setenv("LOANHUB_IDENTITY_AUDIT_ACK", "read_only_identity_audit")
    monkeypatch.setenv("LOANHUB_IDENTITY_AUDIT_DATABASE_URL",
                       "postgresql://fake-host/fake")
    monkeypatch.setenv("LOANHUB_IDENTITY_AUDIT_EXPECTED_ROLE",
                       "identity_audit_reader")
    with patch("scripts.report_identity_index_rollout.generate_read_only_report",
               return_value=render_approval_report(
                   scan(), database_role="identity_audit_reader",
                   database_name="loanhub_sandbox")):
        assert main(["--output", str(destination)]) == 2
    assert destination.read_text() == "existing"


def test_legacy_intersections_block_operator_review_even_with_clean_main_indexes():
    legacy = SimpleNamespace(
        national_id_overlap_groups=0,
        passport_overlap_groups=2,
        repeated_legacy_passport_groups=1,
    )
    report = render_approval_report(
        scan(), database_role="identity_audit_reader",
        database_name="loanhub_sandbox", legacy_audit=legacy)
    assert report["legacy_cross_source_audit_complete"] is True
    assert report["legacy_cross_source_counts"]["passport_overlap_groups"] == 2
    assert report["operator_review_candidate"] is False
    assert report["production_approved"] is False


def test_legacy_audit_missing_blocks_candidate_review():
    report = render_approval_report(
        scan(), database_role="identity_audit_reader",
        database_name="loanhub_sandbox")
    assert report["legacy_cross_source_audit_complete"] is False
    assert report["operator_review_candidate"] is False


def test_legacy_link_triage_is_aggregate_only_and_never_approves_registration():
    report = render_approval_report(
        scan(), database_role="identity_audit_reader",
        database_name="loanhub_sandbox",
        legacy_audit=SimpleNamespace(
            national_id_overlap_groups=113,
            passport_overlap_groups=6,
            repeated_legacy_passport_groups=0),
        legacy_triage=SimpleNamespace(
            matching_identity_groups=113,
            linked_only_groups=96, mixed_linkage_groups=15,
            unlinked_only_groups=2, unlinked_legacy_rows=17,
            unlinked_with_single_borrower_and_company_account=17,
            unlinked_needing_manual_review=17),
    )
    assert report["legacy_linkage_review_complete"] is True
    assert report["legacy_linkage_review"]["unresolved_identity_groups"] == 17
    assert report["legacy_linkage_review"]["linked_only_groups"] == 96
    assert report["operator_review_candidate"] is False
    assert report["production_approved"] is False
    assert report["registration_enabled"] is False
    assert "national_id" not in report["legacy_linkage_review"]


def test_conflicting_cross_source_legacy_audits_fail_closed():
    with pytest.raises(IndexRolloutPreflightError, match="disagree"):
        render_approval_report(
            scan(), database_role="identity_audit_reader",
            database_name="loanhub_sandbox",
            legacy_audit=SimpleNamespace(
                national_id_overlap_groups=1,
                passport_overlap_groups=0,
                repeated_legacy_passport_groups=0),
            legacy_triage=SimpleNamespace(
                matching_identity_groups=0, linked_only_groups=0,
                mixed_linkage_groups=0, unlinked_only_groups=0,
                unlinked_legacy_rows=0,
                unlinked_with_single_borrower_and_company_account=0,
                unlinked_needing_manual_review=0),
        )


def test_production_shaped_audit_identifies_specific_release_blockers():
    """Technical DDL candidacy must not masquerade as save-client approval."""
    report = render_approval_report(
        scan(), database_role="identity_audit_reader",
        database_name="loanhub_sandbox",
        legacy_audit=SimpleNamespace(
            national_id_overlap_groups=113,
            passport_overlap_groups=6,
            repeated_legacy_passport_groups=0,
        ),
        legacy_triage=SimpleNamespace(
            matching_identity_groups=113,
            linked_only_groups=96,
            mixed_linkage_groups=15,
            unlinked_only_groups=2,
            unlinked_legacy_rows=17,
            unlinked_with_single_borrower_and_company_account=17,
            unlinked_needing_manual_review=17,
        ),
    )
    assert report["report_version"] == 4
    assert report["identity_index_migration_review_candidate"] is True
    assert report["operator_review_candidate"] is False
    assert "unresolved_historical_borrower_links" in report["registration_release_blockers"]
    assert "historical_passport_overlap_requires_review" in report["registration_release_blockers"]
    assert "identity_indexes_missing_or_invalid" in report["registration_release_blockers"]
    assert "four_manual_production_approvals_required" in report["registration_release_blockers"]
    assert "protected_registration_route_not_released" in report["registration_release_blockers"]
    assert not report["safe_to_execute"]
    assert not report["production_approved"]
    assert not report["registration_enabled"]


def test_missing_historical_evidence_is_an_explicit_release_blocker():
    report = render_approval_report(
        scan(), database_role="identity_audit_reader",
        database_name="loanhub_sandbox",
    )
    assert report["identity_index_migration_review_candidate"]
    assert "historical_identity_audit_missing" in report["registration_release_blockers"]
    assert "historical_linkage_triage_missing" in report["registration_release_blockers"]
    assert not report["operator_review_candidate"]


def test_duplicate_keys_block_even_technical_index_review():
    report = render_approval_report(
        scan(collisions=(2, 0, 0, 0), blanks=(0, 1, 0, 0)),
        database_role="identity_audit_reader",
        database_name="loanhub_sandbox",
    )
    assert report["identity_index_migration_review_candidate"] is False
    assert "normalized_identity_collisions" in report["registration_release_blockers"]
    assert "blank_identity_values" in report["registration_release_blockers"]
    assert report["registration_enabled"] is False
