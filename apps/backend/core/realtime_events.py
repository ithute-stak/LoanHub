from typing import Optional
from uuid import UUID

from core.websocket_manager import manager


async def broadcast_db_event(
    *,
    action: str,
    entity: str,
    entity_id: UUID | str,
    title: str,
    message: str,
    actor_id: Optional[UUID | str] = None,
    company_id: Optional[UUID | str] = None,
    branch_id: Optional[UUID | str] = None,
    borrower_user_id: Optional[UUID | str] = None,
    loan_officer_user_id: Optional[UUID | str] = None,
    extra: Optional[dict] = None,
):
    payload = {
        "type": "DB_EVENT",
        "action": action,
        "entity": entity,
        "entity_id": str(entity_id),
        "title": title,
        "message": message,
        "actor_id": str(actor_id) if actor_id else None,
        "company_id": str(company_id) if company_id else None,
        "branch_id": str(branch_id) if branch_id else None,
        "borrower_user_id": str(borrower_user_id)
        if borrower_user_id
        else None,
        "loan_officer_user_id": str(loan_officer_user_id)
        if loan_officer_user_id
        else None,
        "extra": extra or {},
    }

    # SuperAdmin sees everything
    await manager.send_to_channel(
        "superadmin",
        payload,
    )

    # Company staff see company events
    if company_id:
        await manager.send_to_channel(
            f"company-{company_id}",
            payload,
        )

    # Branch managers see branch events
    if branch_id:
        await manager.send_to_channel(
            f"branch-{branch_id}",
            payload,
        )

    # Borrower sees personal events
    if borrower_user_id:
        await manager.send_to_channel(
            f"borrower-{borrower_user_id}",
            payload,
        )

    # Loan officer sees assigned events
    if loan_officer_user_id:
        await manager.send_to_channel(
            f"loan-officer-{loan_officer_user_id}",
            payload,
        )