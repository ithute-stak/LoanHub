from __future__ import annotations

from sqlalchemy.orm import attributes

from database.models.cdas_booking import (
    CdasAnalysisRecord,
    CdasBookingFailure,
    CdasBookingOpportunity,
    CdasOpportunityContact,
)
from services.cdas_audit_trail import (
    CDAS_AUDIT_ACTIONS,
    _contact_summary,
    _failure_summary,
    _opportunity_action,
    _opportunity_summary,
)


def _persisted_opportunity(**values) -> CdasBookingOpportunity:
    item = CdasBookingOpportunity()
    for field, value in values.items():
        attributes.set_committed_value(item, field, value)
    return item


def test_formal_action_catalogue_covers_material_cdas_workflow() -> None:
    assert {
        "CDAS_ANALYSIS_ARCHIVED",
        "CDAS_BULK_ANALYSIS_COMPLETED",
        "CDAS_OPPORTUNITY_SAVED",
        "CDAS_PIPELINE_CHANGED",
        "CDAS_ASSIGNMENT_CHANGED",
        "CDAS_CONTACT_LOGGED",
        "CDAS_FAILURE_RECORDED",
        "CDAS_FAILURE_RETRIED",
        "CDAS_BOOKED",
    }.issubset(set(CDAS_AUDIT_ACTIONS))


def test_pipeline_change_is_classified_without_credit_scoring() -> None:
    item = _persisted_opportunity(pipeline_stage="identified", status="monitoring")
    item.pipeline_stage = "documents_required"
    assert _opportunity_action(item, {"pipeline_stage"}) == "CDAS_PIPELINE_CHANGED"


def test_assignment_change_is_classified_separately() -> None:
    item = _persisted_opportunity(pipeline_stage="identified", status="monitoring", assigned_to_user_id=None)
    item.assigned_to_user_id = "11111111-1111-1111-1111-111111111111"
    assert _opportunity_action(item, {"assigned_to_user_id"}) == "CDAS_ASSIGNMENT_CHANGED"


def test_failed_opportunity_reopen_is_classified_as_retry() -> None:
    item = _persisted_opportunity(pipeline_stage="failed", status="monitoring")
    item.pipeline_stage = "identified"
    assert _opportunity_action(item, {"pipeline_stage"}) == "CDAS_FAILURE_RETRIED"


def test_booked_transition_is_terminal_audit_action() -> None:
    item = _persisted_opportunity(pipeline_stage="approved", status="monitoring")
    item.pipeline_stage = "booked"
    item.status = "booked"
    assert _opportunity_action(item, {"pipeline_stage", "status"}) == "CDAS_BOOKED"


def test_failure_stage_is_not_double_logged_as_pipeline_change() -> None:
    item = _persisted_opportunity(pipeline_stage="approved", status="monitoring")
    item.pipeline_stage = "failed"
    assert _opportunity_action(item, {"pipeline_stage"}) is None


def test_safe_summaries_exclude_raw_snapshot_contact_notes_and_failure_details() -> None:
    opportunity = CdasBookingOpportunity(
        client_name="Client Example",
        client_reference="EMP-1",
        analysis_snapshot={"raw_text": "must never be in formal audit"},
    )
    contact = CdasOpportunityContact(
        channel="call",
        outcome="interested",
        notes="private free-form note",
    )
    failure = CdasBookingFailure(
        reason_code="system_or_submission_error",
        reason_details="private free-form failure detail",
        retry_eligible=True,
    )

    opportunity_summary = _opportunity_summary(opportunity)
    contact_summary = _contact_summary(contact)
    failure_summary = _failure_summary(failure)

    assert "analysis_snapshot" not in opportunity_summary
    assert "raw_text" not in repr(opportunity_summary)
    assert "notes" not in contact_summary
    assert contact_summary["has_notes"] is True
    assert "reason_details" not in failure_summary
    assert failure_summary["has_details"] is True


def test_supported_entities_are_the_existing_cdas_persistence_models() -> None:
    assert CdasAnalysisRecord.__tablename__ == "cdas_analysis_records"
    assert CdasBookingOpportunity.__tablename__ == "cdas_booking_opportunities"
    assert CdasOpportunityContact.__tablename__ == "cdas_opportunity_contacts"
    assert CdasBookingFailure.__tablename__ == "cdas_booking_failures"
