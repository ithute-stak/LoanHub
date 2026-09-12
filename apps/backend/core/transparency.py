from __future__ import annotations

import asyncio
import hashlib
import threading
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from core.websocket_manager import manager
from database.models.audit_log import AuditLog
from database.models.borrower import Borrower
from database.models.company import LoanCompany
from database.models.company_staff import CompanyStaff
from database.models.client_loan_company import ClientCompanyLoan
from database.models.employee import EmployeeProfile
from database.models.enums import LoanRequestStatus, NotificationType, UserRole
from database.models.loan_request import LoanRequest
from database.models.notification import Notification
from database.models.repayment import RepaymentInstallment
from database.models.user import User
from utils.convex import (
    current_impersonator_id,
    current_ip_address,
    current_request_id,
    current_user_agent,
    current_user_id,
)


EXCLUDED_TABLES = {
    "audit_logs",
    "notifications",
    "broadcast",
    "system_error_logs",
    "refresh_tokens",
}

SENSITIVE_FIELDS = {
    "password_hash",
    "password",
    "secret",
    "access_token",
    "refresh_token",
    "provider_payload",
    "jti",
}

# Technical presence fields change whenever a socket connects or disconnects.
# They are useful for chat presence but are not business CRUD events and must
# never create inbox notifications or audit spam.
NON_ACTIONABLE_UPDATE_FIELDS: dict[str, set[str]] = {
    "users": {"last_seen_at", "updated_at"},
}

MANAGEMENT_ROLES = {
    UserRole.COMPANY_OWNER,
    UserRole.COMPANY_ADMIN,
}

HR_ROLES = MANAGEMENT_ROLES | {
    UserRole.BRANCH_MANAGER,
    UserRole.HR_MANAGER,
    UserRole.PERFORMANCE_MANAGER,
    UserRole.AUDITOR,
}

LENDING_ROLES = MANAGEMENT_ROLES | {
    UserRole.BRANCH_MANAGER,
    UserRole.LOAN_OFFICER,
    UserRole.RISK_MANAGER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
}

FINANCIAL_ROLES = MANAGEMENT_ROLES | {
    UserRole.BRANCH_MANAGER,
    UserRole.FINANCE_OFFICER,
    UserRole.COLLECTIONS_OFFICER,
    UserRole.COMPLIANCE_OFFICER,
    UserRole.AUDITOR,
}

TABLE_ROLE_POLICY: dict[str, set[UserRole]] = {
    "loan_companies": MANAGEMENT_ROLES | {UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR},
    "company_branches": MANAGEMENT_ROLES | {UserRole.BRANCH_MANAGER, UserRole.AUDITOR},
    "company_staff": HR_ROLES,
    "employee_profiles": HR_ROLES,
    "performance_goals": HR_ROLES,
    "performance_reviews": HR_ROLES,
    "loan_products": LENDING_ROLES,
    "loan_requests": LENDING_ROLES,
    "loan_offers": LENDING_ROLES,
    "client_company_loan": FINANCIAL_ROLES | {UserRole.LOAN_OFFICER, UserRole.RISK_MANAGER},
    "payment_transactions": FINANCIAL_ROLES,
    "repayment_installments": FINANCIAL_ROLES,
    "payment_allocations": FINANCIAL_ROLES,
    "company_subscriptions": MANAGEMENT_ROLES | {UserRole.FINANCE_OFFICER, UserRole.AUDITOR},
    "subscription_plans": set(),
    "marketplace_unlocks": LENDING_ROLES | {UserRole.FINANCE_OFFICER},
    "lender_access_requests": LENDING_ROLES,
    "borrowers": {UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR},
}

TABLE_ICON = {
    "loan_companies": "building-2",
    "company_branches": "git-branch",
    "company_staff": "users",
    "employee_profiles": "contact-round",
    "performance_goals": "target",
    "performance_reviews": "chart-no-axes-combined",
    "loan_products": "package-search",
    "loan_requests": "radio",
    "loan_offers": "badge-dollar-sign",
    "client_company_loan": "hand-coins",
    "payment_transactions": "wallet-cards",
    "repayment_installments": "calendar-check",
    "company_subscriptions": "credit-card",
    "subscription_plans": "layers-3",
    "system_error_logs": "triangle-alert",
}

TABLE_NOTIFICATION_TYPE = {
    "loan_requests": NotificationType.LOAN_REQUEST,
    "loan_offers": NotificationType.OFFER,
    "payment_transactions": NotificationType.PAYMENT,
    "company_subscriptions": NotificationType.SUBSCRIPTION,
    "subscription_plans": NotificationType.SUBSCRIPTION,
    "lender_access_requests": NotificationType.ACCESS_REQUEST,
}

TABLE_LABELS = {
    "loan_companies": "company",
    "company_branches": "branch",
    "company_staff": "staff membership",
    "employee_profiles": "employee profile",
    "performance_goals": "performance goal",
    "performance_reviews": "performance review",
    "loan_products": "loan product",
    "loan_requests": "loan request",
    "loan_offers": "loan offer",
    "client_company_loan": "loan",
    "payment_transactions": "payment",
    "repayment_installments": "repayment instalment",
    "payment_allocations": "payment allocation",
    "company_subscriptions": "subscription",
    "subscription_plans": "subscription plan",
    "marketplace_unlocks": "marketplace unlock",
    "lender_access_requests": "access request",
    "borrowers": "borrower profile",
    "people": "person profile",
    "users": "user account",
}


TABLE_ROLE_POLICY.update({
    "managed_files": MANAGEMENT_ROLES | {UserRole.BRANCH_MANAGER, UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR},
    "chat_conversations": set(),
    "chat_participants": set(),
    "chat_messages": set(),
    "chat_message_attachments": set(),
    "accounting_accounts": FINANCIAL_ROLES,
    "journal_entries": FINANCIAL_ROLES,
    "journal_lines": set(),
    "report_schedules": MANAGEMENT_ROLES | {UserRole.FINANCE_OFFICER, UserRole.PERFORMANCE_MANAGER, UserRole.AUDITOR},
    "generated_reports": MANAGEMENT_ROLES | {UserRole.BRANCH_MANAGER, UserRole.FINANCE_OFFICER, UserRole.PERFORMANCE_MANAGER, UserRole.AUDITOR},
})
TABLE_ICON.update({
    "managed_files": "folder-open",
    "chat_conversations": "messages-square",
    "chat_messages": "message-circle",
    "accounting_accounts": "landmark",
    "journal_entries": "book-open-check",
    "report_schedules": "calendar-clock",
    "generated_reports": "file-chart-column",
})
TABLE_LABELS.update({
    "managed_files": "managed file",
    "chat_conversations": "chat conversation",
    "chat_participants": "chat participant",
    "chat_messages": "chat message",
    "chat_message_attachments": "chat attachment",
    "accounting_accounts": "accounting account",
    "journal_entries": "journal entry",
    "journal_lines": "journal line",
    "report_schedules": "report schedule",
    "generated_reports": "generated report",
})


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (UUID, Decimal, datetime, date)):
        return str(value)
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item) for item in value]
    return str(value)


def _snapshot(target: Any) -> dict[str, Any]:
    state = inspect(target)
    result: dict[str, Any] = {}

    for column_attribute in state.mapper.column_attrs:
        name = column_attribute.key
        if name in SENSITIVE_FIELDS or any(token in name.lower() for token in ("password", "secret", "token")):
            result[name] = "[REDACTED]"
            continue
        try:
            result[name] = _safe_value(getattr(target, name))
        except Exception:
            result[name] = None

    return result


def _uuid(value: Any) -> UUID | None:
    if isinstance(value, UUID):
        return value
    if not value:
        return None
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _membership_scope(connection, user_id: UUID | None) -> tuple[UUID | None, UUID | None]:
    if not user_id:
        return None, None

    return connection.execute(
        select(CompanyStaff.company_id, CompanyStaff.branch_id)
        .where(CompanyStaff.user_id == user_id)
        .order_by(CompanyStaff.is_active.desc(), CompanyStaff.created_at.asc())
        .limit(1)
    ).one_or_none() or (None, None)


def _entity_scope(connection, target: Any, table_name: str) -> tuple[UUID | None, UUID | None]:
    company_id = _uuid(getattr(target, "company_id", None))
    branch_id = _uuid(getattr(target, "branch_id", None))

    if table_name == "loan_companies":
        company_id = _uuid(getattr(target, "id", None))

    if table_name == "users":
        company_id, branch_id = _membership_scope(
            connection,
            _uuid(getattr(target, "id", None)),
        )

    if table_name == "people":
        company_id, branch_id = _membership_scope(
            connection,
            _uuid(getattr(target, "user_id", None)),
        )

    return company_id, branch_id


def _borrower_user_id(connection, target: Any, table_name: str) -> UUID | None:
    if table_name == "users":
        role = getattr(target, "role", None)
        return (
            _uuid(getattr(target, "id", None))
            if role == UserRole.BORROWER
            else None
        )

    if table_name == "people":
        user_id = _uuid(getattr(target, "user_id", None))
        if not user_id:
            return None
        role = connection.execute(
            select(User.role).where(User.id == user_id)
        ).scalar_one_or_none()
        return user_id if role == UserRole.BORROWER else None

    borrower_id = _uuid(getattr(target, "borrower_id", None))

    if table_name == "borrowers":
        return _uuid(getattr(target, "user_id", None))

    if table_name == "borrower_documents":
        borrower_id = _uuid(getattr(target, "borrower_id", None))

    if table_name == "loan_request_documents":
        request_id = _uuid(getattr(target, "loan_request_id", None))
        if request_id:
            borrower_id = connection.execute(
                select(LoanRequest.borrower_id).where(LoanRequest.id == request_id)
            ).scalar_one_or_none()

    if table_name == "loan_offers":
        request_id = _uuid(getattr(target, "loan_request_id", None))
        if request_id:
            borrower_id = connection.execute(
                select(LoanRequest.borrower_id).where(LoanRequest.id == request_id)
            ).scalar_one_or_none()

    if table_name == "repayment_installments":
        loan_id = _uuid(getattr(target, "loan_id", None))
        if loan_id:
            borrower_id = connection.execute(
                select(ClientCompanyLoan.borrower_id).where(
                    ClientCompanyLoan.id == loan_id
                )
            ).scalar_one_or_none()

    if table_name == "payment_allocations":
        installment_id = _uuid(getattr(target, "installment_id", None))
        if installment_id:
            loan_id = connection.execute(
                select(RepaymentInstallment.loan_id).where(
                    RepaymentInstallment.id == installment_id
                )
            ).scalar_one_or_none()
            if loan_id:
                borrower_id = connection.execute(
                    select(ClientCompanyLoan.borrower_id).where(
                        ClientCompanyLoan.id == loan_id
                    )
                ).scalar_one_or_none()

    if borrower_id:
        return connection.execute(
            select(Borrower.user_id).where(Borrower.id == borrower_id)
        ).scalar_one_or_none()

    return None


def _employee_subject_user_id(
    connection,
    target: Any,
    table_name: str,
) -> UUID | None:
    if table_name == "company_staff":
        return _uuid(getattr(target, "user_id", None))

    staff_id = None
    if table_name == "employee_profiles":
        staff_id = _uuid(getattr(target, "staff_id", None))

    if table_name in {"performance_goals", "performance_reviews"}:
        employee_id = _uuid(getattr(target, "employee_id", None))
        if employee_id:
            staff_id = connection.execute(
                select(EmployeeProfile.staff_id).where(
                    EmployeeProfile.id == employee_id
                )
            ).scalar_one_or_none()

    if staff_id:
        return connection.execute(
            select(CompanyStaff.user_id).where(CompanyStaff.id == staff_id)
        ).scalar_one_or_none()

    return None


def _role_routes(role: UserRole, table_name: str, entity_id: str | None) -> str:
    suffix = f"/{entity_id}" if entity_id else ""

    if role == UserRole.SUPERADMIN:
        routes = {
            "loan_companies": f"/superadmin/companies{suffix}",
            "company_branches": "/superadmin/companies/branches",
            "company_staff": "/superadmin/company-admins",
            "employee_profiles": "/superadmin/performance",
            "performance_goals": "/superadmin/performance",
            "performance_reviews": "/superadmin/performance",
            "loan_requests": "/superadmin/loans",
            "loan_offers": "/superadmin/loans",
            "client_company_loan": "/superadmin/loans",
            "payment_transactions": "/superadmin/payments",
            "company_subscriptions": "/superadmin/plans",
            "subscription_plans": "/superadmin/plans",
            "system_error_logs": "/superadmin/system-errors",
            "managed_files": "/superadmin/files",
            "accounting_accounts": "/superadmin/accounting",
            "journal_entries": "/superadmin/accounting",
            "report_schedules": "/superadmin/reports",
            "generated_reports": "/superadmin/reports",
        }
        return routes.get(table_name, "/superadmin/activity")

    if role == UserRole.BORROWER:
        routes = {
            "loan_requests": "/borrower/requests",
            "loan_offers": "/borrower/requests",
            "client_company_loan": "/borrower/loans",
            "payment_transactions": "/borrower/payments",
            "repayment_installments": "/borrower/loans",
            "users": "/borrower/profile",
            "people": "/borrower/profile",
            "borrowers": "/borrower/profile",
            "managed_files": "/borrower/files",
        }
        return routes.get(table_name, "/borrower/notifications")

    routes = {
        "loan_companies": "/company/settings",
        "company_branches": "/company/branches",
        "company_staff": "/company/staff",
        "employee_profiles": "/company/employees",
        "performance_goals": "/company/performance",
        "performance_reviews": "/company/performance",
        "loan_products": "/company/products",
        "loan_requests": "/company/marketplace",
        "loan_offers": "/company/marketplace",
        "client_company_loan": "/company/loans",
        "payment_transactions": "/company/payments",
        "repayment_installments": "/company/loans",
        "company_subscriptions": "/company/billing",
        "marketplace_unlocks": "/company/marketplace",
        "lender_access_requests": "/company/marketplace",
        "managed_files": "/company/files",
        "accounting_accounts": "/company/accounting",
        "journal_entries": "/company/accounting",
        "report_schedules": "/company/reports",
        "generated_reports": "/company/reports",
    }
    return routes.get(table_name, "/company/activity")


def _notification_title(action: str, table_name: str) -> str:
    label = TABLE_LABELS.get(table_name, table_name.replace("_", " "))
    verb = {
        "created": "New",
        "updated": "Updated",
        "deleted": "Deleted",
    }.get(action, action.title())
    return f"{verb} {label}"


def _notification_message(action: str, table_name: str, changed_fields: list[str]) -> str:
    label = TABLE_LABELS.get(table_name, table_name.replace("_", " "))
    if action == "updated" and changed_fields:
        preview = ", ".join(changed_fields[:4])
        return f"The {label} was updated. Changed: {preview}."
    return f"A {label} was {action}. Open this notification to review the relevant record."


def _grouped_notification_title(
    action: str,
    table_name: str,
    count: int,
) -> str:
    if count <= 1:
        return _notification_title(action, table_name)

    label = TABLE_LABELS.get(table_name, table_name.replace("_", " "))
    plural = {
        "company": "companies",
        "branch": "branches",
        "person profile": "person profiles",
    }.get(label, f"{label}s")
    return f"{count} {plural} {action}"


def _grouped_notification_message(
    action: str,
    table_name: str,
    count: int,
    changed_fields: list[str],
) -> str:
    if count <= 1:
        return _notification_message(action, table_name, changed_fields)

    label = TABLE_LABELS.get(table_name, table_name.replace("_", " "))
    if action == "updated" and changed_fields:
        preview = ", ".join(changed_fields[:4])
        return (
            f"{count} {label} records were updated in one operation. "
            f"Changed fields include: {preview}."
        )
    return (
        f"{count} {label} records were {action} in one operation. "
        "Open this notification to review the related workflow."
    )


def _recipients(
    connection,
    *,
    company_id: UUID | None,
    branch_id: UUID | None,
    table_name: str,
    borrower_user_id: UUID | None,
    employee_user_id: UUID | None,
    actor_id: UUID | None,
    target: Any,
) -> list[tuple[UUID, UserRole]]:
    result: dict[UUID, UserRole] = {}

    for user_id, role in connection.execute(
        select(User.id, User.role).where(
            User.role == UserRole.SUPERADMIN,
            User.is_active.is_(True),
        )
    ):
        result[user_id] = role

    if table_name == "loan_requests":
        request_status = getattr(target, "status", None)
        is_marketplace_event = bool(
            getattr(target, "visible_to_lenders", False)
        ) or request_status in {
            LoanRequestStatus.SUBMITTED,
            LoanRequestStatus.OPEN,
            LoanRequestStatus.UNDER_REVIEW,
            LoanRequestStatus.OFFERED,
            LoanRequestStatus.ACCEPTED,
            LoanRequestStatus.CANCELLED,
            LoanRequestStatus.EXPIRED,
        }

        if is_marketplace_event:
            # A broadcast request is a platform-wide marketplace event. Lenders
            # receive a redacted card; identity remains protected by unlock rules.
            statement = (
                select(CompanyStaff.user_id, CompanyStaff.role)
                .join(LoanCompany, LoanCompany.id == CompanyStaff.company_id)
                .where(
                    CompanyStaff.is_active.is_(True),
                    CompanyStaff.role.in_(LENDING_ROLES),
                    LoanCompany.is_active.is_(True),
                )
            )
            for user_id, role in connection.execute(statement):
                result[user_id] = role

    elif table_name == "subscription_plans":
        # Plan changes affect every active company owner and administrator.
        statement = select(CompanyStaff.user_id, CompanyStaff.role).where(
            CompanyStaff.is_active.is_(True),
            CompanyStaff.role.in_(MANAGEMENT_ROLES),
        )
        for user_id, role in connection.execute(statement):
            result[user_id] = role

    elif company_id:
        allowed_roles = TABLE_ROLE_POLICY.get(
            table_name,
            MANAGEMENT_ROLES | {UserRole.AUDITOR},
        )
        if allowed_roles:
            statement = select(
                CompanyStaff.user_id,
                CompanyStaff.role,
                CompanyStaff.branch_id,
            ).where(
                CompanyStaff.company_id == company_id,
                CompanyStaff.is_active.is_(True),
                CompanyStaff.role.in_(allowed_roles),
            )
            for user_id, role, staff_branch_id in connection.execute(statement):
                if (
                    branch_id
                    and role not in MANAGEMENT_ROLES
                    and staff_branch_id
                    and staff_branch_id != branch_id
                ):
                    continue
                result[user_id] = role

    if borrower_user_id:
        result[borrower_user_id] = UserRole.BORROWER

    if employee_user_id:
        employee_role = connection.execute(
            select(User.role).where(
                User.id == employee_user_id,
                User.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if employee_role:
            result[employee_user_id] = employee_role

    if actor_id:
        result.pop(actor_id, None)

    return list(result.items())


async def _send_payloads(payloads: list[dict[str, Any]]) -> None:
    for payload in payloads:
        await manager.send_to_user(payload["user_id"], payload)


def _dispatch_after_commit(payloads: list[dict[str, Any]]) -> None:
    if not payloads:
        return

    try:
        import anyio
        anyio.from_thread.run(_send_payloads, payloads)
        return
    except Exception:
        pass

    def runner() -> None:
        asyncio.run(_send_payloads(payloads))

    threading.Thread(target=runner, daemon=True).start()


@event.listens_for(Session, "before_flush")
def capture_crud_changes(session: Session, flush_context, instances) -> None:
    captured = session.info.setdefault("loanhub_crud_events", [])

    for target in list(session.new):
        table_name = getattr(getattr(target, "__table__", None), "name", None)
        if not table_name or table_name in EXCLUDED_TABLES:
            continue
        captured.append({
            "target": target,
            "table_name": table_name,
            "action": "created",
            "before": {},
            "changed_fields": [],
        })

    for target in list(session.dirty):
        table_name = getattr(getattr(target, "__table__", None), "name", None)
        if not table_name or table_name in EXCLUDED_TABLES or not session.is_modified(target, include_collections=False):
            continue

        state = inspect(target)
        before: dict[str, Any] = {}
        changed_fields: list[str] = []
        for column_attribute in state.mapper.column_attrs:
            name = column_attribute.key
            history = state.attrs[name].history
            if not history.has_changes():
                continue
            changed_fields.append(name)
            old_value = history.deleted[0] if history.deleted else None
            before[name] = "[REDACTED]" if name in SENSITIVE_FIELDS else _safe_value(old_value)

        ignored_fields = NON_ACTIONABLE_UPDATE_FIELDS.get(
            table_name,
            set(),
        )
        if changed_fields and set(changed_fields).issubset(ignored_fields):
            continue

        captured.append({
            "target": target,
            "table_name": table_name,
            "action": "updated",
            "before": before,
            "changed_fields": changed_fields,
        })

    for target in list(session.deleted):
        table_name = getattr(getattr(target, "__table__", None), "name", None)
        if not table_name or table_name in EXCLUDED_TABLES:
            continue
        captured.append({
            "target": target,
            "table_name": table_name,
            "action": "deleted",
            "before": _snapshot(target),
            "changed_fields": [],
        })


@event.listens_for(Session, "after_flush_postexec")
def persist_transparency_events(session: Session, flush_context) -> None:
    captured = session.info.pop("loanhub_crud_events", [])
    if not captured:
        return

    connection = session.connection()
    actor_id = _uuid(current_user_id.get())
    actor_role = None
    if actor_id:
        role_value = connection.execute(
            select(User.role).where(User.id == actor_id)
        ).scalar_one_or_none()
        actor_role = role_value.value if role_value else None

    realtime_payloads = session.info.setdefault("loanhub_realtime_payloads", [])
    now = datetime.utcnow()
    notification_groups: dict[tuple[Any, ...], dict[str, Any]] = {}

    for event_item in captured:
        target = event_item["target"]
        table_name = event_item["table_name"]
        action = event_item["action"]
        entity_id_value = getattr(target, "id", None)
        entity_uuid = _uuid(entity_id_value)
        entity_id = str(entity_id_value) if entity_id_value else None
        company_id, branch_id = _entity_scope(connection, target, table_name)
        after_data = {} if action == "deleted" else _snapshot(target)
        before_data = event_item["before"]
        changed_fields = event_item["changed_fields"]
        borrower_user_id = _borrower_user_id(connection, target, table_name)
        employee_user_id = _employee_subject_user_id(connection, target, table_name)

        audit_id = uuid.uuid4()
        connection.execute(
            AuditLog.__table__.insert().values(
                id=audit_id,
                user_id=actor_id,
                company_id=company_id,
                branch_id=branch_id,
                action=action,
                table_name=table_name,
                entity_type=table_name,
                record_id=entity_uuid,
                description=_notification_message(action, table_name, changed_fields),
                actor_role=actor_role,
                severity="warning" if action == "deleted" else "info",
                status="success",
                before_data=before_data,
                after_data=after_data,
                changed_fields=changed_fields,
                event_data={"automatic": True, "impersonated_by": current_impersonator_id.get()},
                request_id=current_request_id.get(),
                ip_address=current_ip_address.get(),
                user_agent=current_user_agent.get(),
                created_at=now,
                updated_at=now,
            )
        )

        recipients = _recipients(
            connection,
            company_id=company_id,
            branch_id=branch_id,
            table_name=table_name,
            borrower_user_id=borrower_user_id,
            employee_user_id=employee_user_id,
            actor_id=actor_id,
            target=target,
        )

        for recipient_user_id, recipient_role in recipients:
            action_url = _role_routes(recipient_role, table_name, entity_id)
            notification_type = TABLE_NOTIFICATION_TYPE.get(
                table_name,
                NotificationType.SYSTEM,
            )
            priority = (
                "high"
                if table_name
                in {
                    "loan_companies",
                    "payment_transactions",
                    "client_company_loan",
                }
                or action == "deleted"
                else "normal"
            )
            group_key = (
                recipient_user_id,
                recipient_role,
                table_name,
                action,
                company_id,
                branch_id,
                action_url,
                notification_type,
                priority,
            )
            group = notification_groups.setdefault(
                group_key,
                {
                    "recipient_user_id": recipient_user_id,
                    "recipient_role": recipient_role,
                    "table_name": table_name,
                    "action": action,
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "action_url": action_url,
                    "notification_type": notification_type,
                    "priority": priority,
                    "entity_ids": [],
                    "audit_ids": [],
                    "changed_fields": set(),
                },
            )
            if entity_id:
                group["entity_ids"].append(entity_id)
            group["audit_ids"].append(str(audit_id))
            group["changed_fields"].update(changed_fields)

    for group in notification_groups.values():
        count = len(group["audit_ids"])
        entity_ids = list(dict.fromkeys(group["entity_ids"]))
        changed_fields = sorted(group["changed_fields"])
        entity_id = entity_ids[0] if len(entity_ids) == 1 else None
        notification_id = uuid.uuid4()
        event_type = f'{group["table_name"]}.{group["action"]}'
        dedup_source = (
            f'{group["recipient_user_id"]}:{event_type}:'
            f'{",".join(entity_ids[:50])}:{now.isoformat()}'
        )
        deduplication_key = hashlib.sha256(dedup_source.encode()).hexdigest()

        values = dict(
            id=notification_id,
            user_id=group["recipient_user_id"],
            actor_user_id=actor_id,
            company_id=group["company_id"],
            branch_id=group["branch_id"],
            title=_grouped_notification_title(
                group["action"],
                group["table_name"],
                count,
            ),
            message=_grouped_notification_message(
                group["action"],
                group["table_name"],
                count,
                changed_fields,
            ),
            notification_type=group["notification_type"],
            event_type=event_type,
            action=group["action"],
            entity_type=group["table_name"],
            entity_id=entity_id,
            action_url=group["action_url"],
            icon=TABLE_ICON.get(group["table_name"], "bell"),
            priority=group["priority"],
            data={
                "event_count": count,
                "entity_ids": entity_ids[:50],
                "changed_fields": changed_fields,
                "audit_log_ids": group["audit_ids"][:50],
            },
            deduplication_key=deduplication_key,
            is_read=False,
            is_archived=False,
            created_at=now,
            updated_at=now,
        )
        connection.execute(Notification.__table__.insert().values(**values))
        realtime_payloads.append(
            {
                "type": "NOTIFICATION_CREATED",
                "user_id": str(group["recipient_user_id"]),
                **{key: _safe_value(value) for key, value in values.items()},
            }
        )


@event.listens_for(Session, "after_commit")
def deliver_realtime_notifications(session: Session) -> None:
    payloads = session.info.pop("loanhub_realtime_payloads", [])
    _dispatch_after_commit(payloads)


@event.listens_for(Session, "after_rollback")
def discard_realtime_notifications(session: Session) -> None:
    session.info.pop("loanhub_realtime_payloads", None)
    session.info.pop("loanhub_crud_events", None)
