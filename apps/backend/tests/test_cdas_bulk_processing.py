from __future__ import annotations

from services.cdas_bulk_processing import (
    build_bulk_error_item,
    build_bulk_result_item,
    build_bulk_summary,
)


def test_bulk_success_result_uses_effective_identity_and_archive_state() -> None:
    result = build_bulk_result_item(
        index=2,
        client_name=None,
        client_reference=None,
        analysis={
            "profile": {"full_name": "Mpho Mokoena", "employee_no": "EMP-77", "nid": "NID-1"},
            "decision": "WAIT_UNTIL",
            "next_possible_booking_date": "2026-12-01",
            "data_quality_issue_count": 1,
            "capacity": {"assessed_available_amount": 3250.5},
        },
        analysis_id="analysis-1",
        archived_new=True,
    )

    assert result == {
        "index": 2,
        "status": "SUCCESS",
        "client_name": "Mpho Mokoena",
        "client_reference": "EMP-77",
        "analysis_id": "analysis-1",
        "archived_new": True,
        "decision": "WAIT_UNTIL",
        "next_possible_booking_date": "2026-12-01",
        "assessed_available_amount": 3250.5,
        "data_quality_issue_count": 1,
        "error": None,
    }
    assert "raw_text" not in result


def test_bulk_error_result_is_explicit_and_contains_no_analysis_data() -> None:
    result = build_bulk_error_item(
        index=3,
        client_name="Bad Row",
        client_reference="REF-3",
        error="Could not find a valid CDAS deduction table",
    )

    assert result["status"] == "ERROR"
    assert result["index"] == 3
    assert result["analysis_id"] is None
    assert result["decision"] is None
    assert result["error"] == "Could not find a valid CDAS deduction table"
    assert "raw_text" not in result


def test_bulk_summary_counts_success_errors_dedupe_and_decisions() -> None:
    items = [
        {"status": "SUCCESS", "archived_new": True, "decision": "BOOK_NOW"},
        {"status": "SUCCESS", "archived_new": False, "decision": "REVIEW_REQUIRED"},
        {"status": "SUCCESS", "archived_new": True, "decision": "BOOK_NOW"},
        {"status": "ERROR", "archived_new": False, "decision": None},
    ]

    summary = build_bulk_summary(items)

    assert summary["total"] == 4
    assert summary["successful"] == 3
    assert summary["errors"] == 1
    assert summary["archived_new"] == 2
    assert summary["archive_reused"] == 1
    assert summary["review_required"] == 1
    assert summary["decisions"] == {"BOOK_NOW": 2, "REVIEW_REQUIRED": 1}
