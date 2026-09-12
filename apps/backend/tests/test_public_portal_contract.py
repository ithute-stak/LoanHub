from __future__ import annotations

from database.schemas.public_portal import PublicPlatformStats
from routers import public_portal


def test_public_platform_stats_exposes_aggregate_fields_only():
    fields = set(PublicPlatformStats.model_fields)
    assert fields == {
        "approved_institutions",
        "active_branches",
        "borrower_profiles",
        "company_client_accounts",
        "loan_requests",
        "loan_offers",
        "loan_accounts",
        "active_loans",
        "completed_loans",
        "employee_profiles",
        "managed_files",
        "generated_reports",
        "updated_at",
    }

    forbidden_fragments = {
        "name",
        "email",
        "phone",
        "address",
        "balance",
        "principal",
        "income",
        "document",
        "company_id",
        "borrower_id",
    }
    assert not any(
        fragment in field
        for field in fields
        for fragment in forbidden_fragments
    )


def test_public_stats_route_requires_database_only():
    route = next(
        route
        for route in public_portal.router.routes
        if getattr(route, "path", "") == "/public/stats"
    )
    dependency_names = {
        dependency.call.__name__
        for dependency in route.dependant.dependencies
        if dependency.call is not None
    }
    assert dependency_names == {"get_db"}
