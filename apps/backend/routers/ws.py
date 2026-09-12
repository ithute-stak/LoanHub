from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
from urllib.parse import urlsplit
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session, selectinload

from core.websocket_manager import manager
from database.config.config import settings
from database.models.enums import UserRole
from database.models.chat import ChatParticipant
from database.models.user import User
from database.session import SessionLocal, get_db
from utils.decode_encode_token import decode_token


WS_SESSION_COOKIE = "loanhub_ws_session"
logger = logging.getLogger(__name__)


router = APIRouter(prefix='/ws', tags=['WebSockets'])


def _uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


def _chat_contact_ids(db: Session, user_id: UUID) -> list[UUID]:
    conversation_ids = [
        item[0]
        for item in db.query(ChatParticipant.conversation_id).filter(
            ChatParticipant.user_id == user_id,
            ChatParticipant.is_active.is_(True),
        ).all()
    ]
    if not conversation_ids:
        return []
    return [
        item[0]
        for item in db.query(ChatParticipant.user_id).filter(
            ChatParticipant.conversation_id.in_(conversation_ids),
            ChatParticipant.user_id != user_id,
            ChatParticipant.is_active.is_(True),
        ).distinct().all()
    ]


async def _broadcast_presence(db: Session, user_id: UUID, online: bool, at: datetime) -> None:
    payload = {
        'type': 'PRESENCE_CHANGED',
        'user_id': str(user_id),
        'is_online': online,
        'last_seen_at': at.isoformat(),
    }
    for recipient_id in _chat_contact_ids(db, user_id):
        await manager.send_to_user(str(recipient_id), payload)


def _websocket_token(
    websocket: WebSocket,
) -> tuple[str | None, str | None, str | None]:
    """Resolve WebSocket credentials without placing access tokens in URLs.

    A freshly issued short-lived subprotocol token is preferred over cookies.
    This keeps realtime authentication reliable when the UI and API are on
    different origins or a browser blocks third-party cookies. The HttpOnly
    cookie remains a same-origin fallback and the query token is retained only
    for legacy clients.
    """
    requested_protocols = list(
        websocket.scope.get("subprotocols") or []
    )
    if not requested_protocols:
        protocol_header = websocket.headers.get(
            "sec-websocket-protocol",
            "",
        )
        requested_protocols = [
            item.strip()
            for item in protocol_header.split(",")
            if item.strip()
        ]

    protocol_token = next(
        (
            item.removeprefix("loanhub.jwt.")
            for item in requested_protocols
            if item.startswith("loanhub.jwt.")
        ),
        None,
    )
    accepted_protocol = (
        "loanhub.v1"
        if "loanhub.v1" in requested_protocols
        else None
    )

    cookie_token = websocket.cookies.get(WS_SESSION_COOKIE)
    query_token = websocket.query_params.get("token")

    if protocol_token:
        return protocol_token, accepted_protocol, "subprotocol"
    if cookie_token:
        return cookie_token, accepted_protocol, "cookie"
    if query_token:
        return query_token, accepted_protocol, "legacy-query"
    return None, accepted_protocol, None


def _origin_allowed(websocket: WebSocket) -> bool:
    origin = (websocket.headers.get("origin") or "").strip().rstrip("/")
    if not origin:
        # Non-browser clients may omit Origin. Authentication is still required.
        return True

    request_host = (
        websocket.headers.get("x-forwarded-host")
        or websocket.headers.get("host")
        or ""
    ).split(",", maxsplit=1)[0].strip().lower()
    origin_host = urlsplit(origin).netloc.lower()
    if request_host and origin_host == request_host:
        return True

    allowed = {
        item.strip().rstrip("/")
        for item in settings.cors_origins
        if item.strip()
    }
    return "*" in allowed or origin in allowed


async def _reject(websocket: WebSocket, reason: str) -> None:
    logger.warning(
        "WebSocket rejected: reason=%s client_id=%s origin=%s",
        reason,
        (websocket.query_params.get("client_id") or "-")[:128],
        websocket.headers.get("origin") or "-",
    )
    await websocket.close(code=1008, reason=reason)


def _client_id(websocket: WebSocket, user_id: UUID) -> str:
    supplied = (websocket.query_params.get("client_id") or "").strip()
    if supplied and len(supplied) <= 128:
        return supplied
    return f"legacy-{user_id}"


@router.websocket('')
async def websocket_auth_endpoint(
    websocket: WebSocket,
    db: Session = Depends(get_db),
) -> None:
    token, accepted_protocol, auth_transport = _websocket_token(websocket)
    query_company_id = _uuid(websocket.query_params.get('company_id'))

    if not _origin_allowed(websocket):
        await _reject(websocket, 'Origin not allowed')
        return
    if not token:
        await _reject(websocket, 'Missing WebSocket token')
        return
    try:
        payload = decode_token(token)
    except HTTPException:
        await _reject(websocket, 'Invalid or expired WebSocket token')
        return
    token_type = payload.get('token_type')
    if token_type not in {'access', 'websocket'}:
        await _reject(websocket, 'WebSocket authentication required')
        return

    payload_company_id = _uuid(str(payload.get('company_id') or ''))
    if (
        query_company_id
        and payload_company_id
        and query_company_id != payload_company_id
    ):
        await _reject(websocket, 'Company scope mismatch')
        return
    selected_company_id = query_company_id or payload_company_id

    user_id = _uuid(str(payload.get('user_id') or ''))
    if not user_id:
        await _reject(websocket, 'Invalid user')
        return

    client_id = _client_id(websocket, user_id)
    bound_client_id = str(payload.get('client_id') or '').strip()
    if bound_client_id and bound_client_id != client_id:
        await _reject(websocket, 'WebSocket client mismatch')
        return

    user = (
        db.query(User)
        .options(selectinload(User.company_staff))
        .filter(User.id == user_id)
        .first()
    )
    if not user or not user.is_active:
        await _reject(websocket, 'Account unavailable')
        return

    memberships = [item for item in user.company_staff if item.is_active]
    if selected_company_id:
        memberships = [item for item in memberships if item.company_id == selected_company_id]
        if not memberships and user.role != UserRole.SUPERADMIN:
            await _reject(websocket, 'Company access denied')
            return

    channels: set[str] = {f'user-{user.id}'}
    if user.role == UserRole.SUPERADMIN:
        channels.add('superadmin')
    elif user.role == UserRole.BORROWER:
        channels.add(f'borrower-{user.id}')
    for membership in memberships:
        channels.add(f'company-{membership.company_id}')
        if membership.branch_id:
            channels.add(f'branch-{membership.branch_id}')
        if membership.role == UserRole.LOAN_OFFICER:
            channels.add(f'loan-officer-{user.id}')

    await websocket.accept(subprotocol=accepted_protocol)
    await manager.register_client(str(user.id), client_id, websocket)

    for channel in channels:
        manager.subscribe(channel, websocket)

    connected_at = datetime.now(timezone.utc)
    first_connection = manager.user_connected(str(user.id))
    if first_connection:
        user.last_seen_at = connected_at
        db.commit()
        await _broadcast_presence(db, user.id, True, connected_at)

    try:
        await websocket.send_json({
            'type': 'SOCKET_CONNECTED',
            'user_id': str(user.id),
            'role': user.role.value,
            'channels': sorted(channels),
            'impersonated_by': payload.get('impersonated_by'),
            'auth_transport': auth_transport,
        })

        while True:
            message = await websocket.receive_text()
            if message.strip().lower() == 'ping':
                await websocket.send_text('pong')
                continue
            try:
                event_data = json.loads(message)
            except json.JSONDecodeError:
                continue

            if event_data.get('type') == 'CHAT_TYPING':
                conversation_id = _uuid(str(event_data.get('conversation_id') or ''))
                if not conversation_id:
                    continue
                membership = db.query(ChatParticipant).filter(
                    ChatParticipant.conversation_id == conversation_id,
                    ChatParticipant.user_id == user.id,
                    ChatParticipant.is_active.is_(True),
                ).first()
                if not membership:
                    continue
                recipient_ids = [item[0] for item in db.query(ChatParticipant.user_id).filter(
                    ChatParticipant.conversation_id == conversation_id,
                    ChatParticipant.user_id != user.id,
                    ChatParticipant.is_active.is_(True),
                ).all()]
                typing_payload = {
                    'type': 'CHAT_TYPING',
                    'conversation_id': str(conversation_id),
                    'user_id': str(user.id),
                    'is_typing': bool(event_data.get('is_typing')),
                }
                for recipient_id in recipient_ids:
                    await manager.send_to_user(str(recipient_id), typing_payload)
    except WebSocketDisconnect:
        pass
    finally:
        manager.unregister_client(str(user.id), client_id, websocket)
        manager.disconnect_all(websocket)
        became_offline = manager.user_disconnected(str(user.id))
        if became_offline:
            seen_at = datetime.now(timezone.utc)
            update_db = SessionLocal()
            try:
                stored_user = update_db.query(User).filter(User.id == user.id).first()
                if stored_user:
                    stored_user.last_seen_at = seen_at
                    update_db.commit()
                await _broadcast_presence(update_db, user.id, False, seen_at)
            finally:
                update_db.close()
