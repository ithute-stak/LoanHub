"""Bounded, repeatable-read directory snapshot preview.

This preview is intentionally NOT an installable Redux Data Center snapshot:
there is no transactional outbox, ordered replay cursor or reconnect gap
recovery yet. The endpoint refuses incomplete data rather than claiming ready.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy.orm import Session

from core.access_control import TenantContext
from database.models.branch import CompanyBranch
from database.models.company_client import CompanyBorrowerAccount
from database.models.company_staff import CompanyStaff
from database.models.client_loan_company import ClientCompanyLoan
from database.models.loan_product import LoanProduct
from database.models.payment import PaymentTransaction
from database.tenant_context import bind_database_tenant_context
from services.data_center_branch_projection import (
    BranchGrant,
    safe_branch_row,
    verified_branch_grant,
)
from services.data_center_client_projection import safe_client_row
from services.data_center_financial_projection import safe_loan_row, safe_payment_row
from services.data_center_loan_product_projection import safe_loan_product_row
from services.data_center_staff_projection import safe_staff_row

KINDS = ("branches", "loanProducts", "staff", "clients", "loans", "payments")
MAX_RESOURCE_ROWS = 500


class SnapshotUnavailable(RuntimeError):
    """The server cannot certify a bounded complete directory preview."""


def require_snapshot_management(grant: BranchGrant) -> None:
    # The payment and staff projections are management-only. Never create a
    # partly visible six-resource projection for a branch-scoped employee.
    if not grant.company_wide or grant.role not in {"company_owner", "company_admin"}:
        raise PermissionError("Company management membership required")


def bucket_from_rows(
    rows: list[Any], grant: BranchGrant, projection: Callable[[Any, BranchGrant], dict],
) -> dict[str, Any]:
    by_id: dict[str, dict] = {}
    for row in rows:
        projected = projection(row, grant)
        key = projected["id"]
        if key in by_id:
            raise SnapshotUnavailable("Duplicate directory row identifier")
        by_id[key] = projected
    return {"ids": list(by_id), "byId": by_id}


def preview_snapshot(context: TenantContext, request_db: Session) -> dict[str, Any]:
    grant = verified_branch_grant(context)
    require_snapshot_management(grant)

    # Start a NEW connection/transaction because authenticating the context
    # already queried the request Session, whose isolation level cannot safely
    # be changed mid-transaction. All six reads use one MVCC snapshot.
    engine = request_db.get_bind()
    if engine is None:
        raise SnapshotUnavailable("Snapshot database unavailable")

    with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
        with connection.begin():
            with Session(bind=connection) as db:
                bind_database_tenant_context(
                    db, user_id=context.user.id, company_id=context.company_id,
                    branch_id=context.branch_id, role=context.role.value,
                    actor_scope="tenant",
                )
                # Recheck membership in the same read-consistent transaction.
                membership = db.query(CompanyStaff).filter(
                    CompanyStaff.id == context.staff.id,
                    CompanyStaff.company_id == context.company_id,
                    CompanyStaff.user_id == context.user.id,
                    CompanyStaff.is_active.is_(True),
                ).one_or_none()
                if (
                    membership is None
                    or str(getattr(membership.role, "value", membership.role)) != grant.role
                    or membership.branch_id != context.branch_id
                ):
                    raise PermissionError("Snapshot membership changed")

                specs = (
                    ("branches", CompanyBranch, safe_branch_row),
                    ("loanProducts", LoanProduct, safe_loan_product_row),
                    ("staff", CompanyStaff, safe_staff_row),
                    ("clients", CompanyBorrowerAccount, safe_client_row),
                    ("loans", ClientCompanyLoan, safe_loan_row),
                    ("payments", PaymentTransaction, safe_payment_row),
                )
                buckets: dict[str, Any] = {}
                for kind, model, projection in specs:
                    rows = (
                        db.query(model)
                        .filter(model.company_id == context.company_id)
                        .order_by(model.id)
                        .limit(MAX_RESOURCE_ROWS + 1)
                        .all()
                    )
                    if len(rows) > MAX_RESOURCE_ROWS:
                        raise SnapshotUnavailable(f"{kind} exceeds bounded snapshot capacity")
                    buckets[kind] = bucket_from_rows(rows, grant, projection)
                if tuple(buckets) != KINDS:
                    raise SnapshotUnavailable("Incomplete snapshot")

    return {
        "contract": "loanhub.directory-preview.v1",
        "scope": {
            "userId": str(context.user.id),
            "companyId": grant.company_id,
            "role": grant.role,
            "branchId": None,
        },
        "buckets": buckets,
        "read_consistency": "repeatable_read",
        "event_cursor": None,
        "replay_supported": False,
        "ready": False,
        "complete_data_center_snapshot": False,
    }
