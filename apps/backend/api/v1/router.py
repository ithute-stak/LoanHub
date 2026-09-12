from __future__ import annotations

from fastapi import APIRouter

from routers import (
    account,
    accounting,
    analytics,
    audit,
    auth,
    billing,
    borrower,
    borrower_financial_command,
    borrower_registration,
    borrower_workspace,
    branches,
    call_management,
    call_media,
    chat,
    collections_recovery,
    company,
    company_clients,
    company_operating_system,
    company_registration,
    company_staff,
    company_websites,
    credit_bureau,
    credit_bureau_configuration,
    employees,
    employer_groups,
    hrms,
    institution_governance,
    expense_management,
    files,
    finance_config,
    governance_controls,
    ithute_auth,
    lending_operations,
    legacy_cashout,
    lelefa_managed_collections,
    loan_offers,
    loan_payment_operations,
    loan_products,
    loan_request,
    loan_settings,
    loans,
    loanhub_money,
    lelefa_paygate,
    lelefa_paygate_admin,
    marketplace,
    maturity_recovery,
    mobile_onboarding,
    notifications,
    origination,
    payments,
    performance,
    performance_system_ratings,
    person,
    platform_credit_bureau,
    platform_staff,
    professional_lending,
    public_file_shares,
    public_portal,
    realtime,
    reports,
    sandbox,
    social_sharing,
    system_errors,
    system_updates,
    workspace_creation_policy,
    workspace_document_organization,
    workspace_documents,
    workspace_office_governance,
    workspace_spreadsheets,
    ws,
)


api_router = APIRouter()

# The governance layer intentionally replaces a small set of legacy Document
# Studio route contracts. Remove those route objects from the legacy router
# before composition so FastAPI exposes exactly one handler per method/path.
# The legacy Python functions remain importable and are reused internally by
# the policy wrappers, so this does not duplicate business logic.
_WORKSPACE_DOCUMENT_ROUTE_OVERRIDES = {
    ("GET", "/workspace-documents"),
    ("POST", "/workspace-documents"),
    ("GET", "/workspace-documents/{document_id}"),
    ("GET", "/workspace-documents/{document_id}/brand-logo/content"),
    ("GET", "/workspace-documents/{document_id}/signatures"),
    ("GET", "/workspace-documents/{document_id}/revisions"),
    ("GET", "/workspace-documents/{document_id}/export/{format_name}"),
}


def _without_workspace_document_overrides(router: APIRouter) -> APIRouter:
    router.routes[:] = [
        route
        for route in router.routes
        if not any(
            (method, getattr(route, "path", "")) in _WORKSPACE_DOCUMENT_ROUTE_OVERRIDES
            for method in (getattr(route, "methods", None) or set())
        )
    ]
    return router


_legacy_workspace_documents_router = _without_workspace_document_overrides(
    workspace_documents.router
)

# Keep the complete API composition in one declarative registry. This avoids
# recovery patches accidentally importing the same router twice or adding a
# critical router after the aggregate router has already been mounted.
_ROUTE_REGISTRY = (
    public_portal.router,
    auth.router,
    ithute_auth.router,
    sandbox.router,
    account.router,
    analytics.router,
    lending_operations.router,
    collections_recovery.router,
    lelefa_managed_collections.router,
    call_management.router,
    call_media.router,
    maturity_recovery.router,
    notifications.router,
    realtime.router,
    audit.router,
    governance_controls.router,
    company_registration.router,
    borrower_registration.router,
    employer_groups.router,
    mobile_onboarding.router,
    company.router,
    institution_governance.router,
    company_operating_system.router,
    company_staff.router,
    company_websites.router,
    employees.router,
    hrms.router,
    performance.router,
    performance_system_ratings.router,
    branches.router,
    person.router,
    borrower.router,
    borrower_financial_command.router,
    borrower_workspace.router,
    loan_request.router,
    marketplace.router,
    loan_offers.router,
    loan_products.router,
    loan_settings.router,
    loans.router,
    payments.router,
    loanhub_money.router,
    lelefa_paygate.router,
    lelefa_paygate_admin.router,
    loan_payment_operations.router,
    billing.router,
    system_errors.router,
    system_updates.router,
    files.router,
    public_file_shares.router,
    social_sharing.router,
    chat.router,
    accounting.router,
    reports.router,
    ws.router,
    professional_lending.router,
    company_clients.router,
    legacy_cashout.router,
    finance_config.router,
    platform_staff.router,
    platform_credit_bureau.router,
    # This static route must precede the generic `/origination/integrations/{provider}`
    # route so company users cannot reintroduce Experian credentials through the
    # legacy tenant integration editor.
    platform_credit_bureau.company_guard_router,
    origination.router,
    credit_bureau_configuration.router,
    credit_bureau.router,
    expense_management.router,
    # Static folder/import routes must stay ahead of dynamic document IDs.
    workspace_document_organization.router,
    # Governance owns canonical document read contracts so staff isolation,
    # company-public work, and company-owner oversight are consistent.
    workspace_office_governance.office_router,
    workspace_office_governance.document_router,
    # Ordinary company work is private until the staff member deliberately
    # makes it Company public or shares it with named collaborators.
    workspace_creation_policy.router,
    _legacy_workspace_documents_router,
    workspace_spreadsheets.router,
)

for child_router in _ROUTE_REGISTRY:
    api_router.include_router(child_router)
