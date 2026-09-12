from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from database.models.mobile_push import MobilePushDevice
from database.session import SessionLocal

logger = logging.getLogger(__name__)
_push_tasks: set[asyncio.Task] = set()


def _firebase_messaging():
    """Return firebase_admin.messaging when server push is configured.

    Firebase is only the background wake transport. LoanHub owns the event
    contract, permission rules, channels and in-app/local notification UX.
    """

    project_id = (os.getenv("FIREBASE_PROJECT_ID") or "").strip()
    if not project_id:
        return None
    try:
        import firebase_admin
        from firebase_admin import messaging

        try:
            firebase_admin.get_app()
        except ValueError:
            firebase_admin.initialize_app(options={"projectId": project_id})
        return messaging
    except Exception as exc:  # pragma: no cover - deployment credentials
        logger.warning("LoanHub push transport is unavailable: %s", exc)
        return None


def push_configured() -> bool:
    return bool((os.getenv("FIREBASE_PROJECT_ID") or "").strip())


def _active_tokens(db: Session, user_ids: Iterable[UUID | str]) -> list[str]:
    ids: list[UUID] = []
    for item in user_ids:
        try:
            ids.append(item if isinstance(item, UUID) else UUID(str(item)))
        except ValueError:
            continue
    if not ids:
        return []
    rows = (
        db.query(MobilePushDevice.push_token)
        .filter(
            MobilePushDevice.user_id.in_(ids),
            MobilePushDevice.is_active.is_(True),
            MobilePushDevice.revoked_at.is_(None),
        )
        .distinct()
        .all()
    )
    return [row[0] for row in rows if row[0]]


def _notification_for_recipient(event: dict, recipient_id: UUID | str) -> dict | None:
    explicit = event.get("notification")
    if explicit:
        return explicit

    event_type = str(event.get("type") or "")
    if event_type == "CHAT_MESSAGE_CREATED":
        message = event.get("message") or (event.get("data") or {}).get("message") or {}
        sender = message.get("sender") or {}
        if str(sender.get("id") or "") == str(recipient_id):
            return None
        message_type = str(message.get("message_type") or "text")
        if message_type == "voice":
            preview = "Voice message"
        elif message_type == "file":
            preview = "File"
        else:
            preview = str(message.get("body") or "New message")[:180]
        conversation_id = str(event.get("conversation_id") or message.get("conversation_id") or "")
        return {
            "category": "chat",
            "title": str(sender.get("display_name") or "New LoanHub message"),
            "body": preview,
            "route": f"chat:{conversation_id}" if conversation_id else "chats",
        }

    return None


def _send_sync(user_ids: list[UUID | str], event: dict) -> None:
    messaging = _firebase_messaging()
    if messaging is None:
        return

    with SessionLocal() as db:
        for user_id in user_ids:
            notification = _notification_for_recipient(event, user_id)
            if not notification:
                continue
            tokens = _active_tokens(db, [user_id])
            if not tokens:
                continue

            category = str(notification.get("category") or event.get("domain") or "general")
            channel_id = {
                "chat": "loanhub_messages",
                "message": "loanhub_messages",
                "money": "loanhub_money",
                "call": "loanhub_calls",
            }.get(category, "loanhub_events")
            title = str(notification.get("title") or "LoanHub")[:120]
            body = str(notification.get("body") or "You have a new LoanHub update")[:240]
            data = {
                "event_id": str(event.get("event_id") or ""),
                "type": str(event.get("type") or "LOANHUB_EVENT"),
                "domain": str(event.get("domain") or "system"),
                "entity_id": str(event.get("entity_id") or ""),
                "route": str(notification.get("route") or ""),
                "title": title,
                "body": body,
                "category": category,
            }
            android = messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id=channel_id,
                    sound="default",
                    default_vibrate_timings=True,
                ),
            )
            for start in range(0, len(tokens), 500):
                try:
                    messaging.send_each_for_multicast(
                        messaging.MulticastMessage(
                            tokens=tokens[start : start + 500],
                            data=data,
                            notification=messaging.Notification(title=title, body=body),
                            android=android,
                        )
                    )
                except Exception as exc:  # pragma: no cover - provider/network
                    logger.warning("LoanHub push delivery failed: %s", exc)


async def send_push_event(user_ids: Iterable[UUID | str], event: dict) -> None:
    ids = list(dict.fromkeys(user_ids))
    if ids:
        await asyncio.to_thread(_send_sync, ids, event)


_bridge_installed = False


def _finish_push_task(task: asyncio.Task) -> None:
    _push_tasks.discard(task)
    if task.cancelled():
        return
    try:
        task.result()
    except Exception as exc:  # pragma: no cover - provider/network path
        logger.warning("LoanHub background push task failed: %s", exc)


def install_realtime_push_bridge() -> None:
    """Attach notification enrichment and push to the WebSocket manager once."""

    global _bridge_installed
    if _bridge_installed:
        return
    from core.websocket_manager import manager

    def enrich_for_notification(user_id: str, event: dict) -> dict:
        notification = _notification_for_recipient(event, user_id)
        if not notification:
            return event
        enriched = dict(event)
        enriched["notification"] = notification
        return enriched

    def push_hook(user_id: str, event: dict) -> None:
        if not push_configured() or not event.get("notification"):
            return
        task = asyncio.create_task(send_push_event([user_id], event))
        _push_tasks.add(task)
        task.add_done_callback(_finish_push_task)

    manager.set_user_event_transformer(enrich_for_notification)
    manager.set_user_event_hook(push_hook)
    _bridge_installed = True
