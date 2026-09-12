from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID
import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session, selectinload

from core.websocket_manager import manager
from database.models.enums import UserRole
from database.models.chat import ChatParticipant
from database.models.user import User
from database.session import SessionLocal, get_db
from utils.decode_encode_token import decode_token


WS_SESSION_COOKIE = "loanhub_ws_session"


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


def _websocket_token(websocket: WebSocket) -> tuple[str | None, str | None]:
    # ASGI exposes parsed subprotocols directly. Keep the raw-header fallback
    # for older servers and retain the legacy query token temporarily.
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

    return (
        cookie_token or protocol_token or query_token,
        accepted_protocol,
    )


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
    token, accepted_protocol = _websocket_token(websocket)
    query_company_id = _uuid(websocket.query_params.get('company_id'))

    if not token:
        await websocket.close(code=1008, reason='Missing access token')
        return
    try:
        payload = decode_token(token)
    except HTTPException:
        await websocket.close(code=1008, reason='Invalid access token')
        return
    token_type = payload.get('token_type')
    if token_type not in {'access', 'websocket'}:
        await websocket.close(code=1008, reason='WebSocket authentication required')
        return

    payload_company_id = _uuid(str(payload.get('company_id') or ''))
    if (
        query_company_id
        and payload_company_id
        and query_company_id != payload_company_id
    ):
        await websocket.close(code=1008, reason='Company scope mismatch')
        return
    selected_company_id = query_company_id or payload_company_id

    user_id = _uuid(str(payload.get('user_id') or ''))
    if not user_id:
        await websocket.close(code=1008, reason='Invalid user')
        return

    user = (
        db.query(User)
        .options(selectinload(User.company_staff))
        .filter(User.id == user_id)
        .first()
    )
    if not user or not user.is_active:
        await websocket.close(code=1008, reason='Account unavailable')
        return

    memberships = [item for item in user.company_staff if item.is_active]
    if selected_company_id:
        memberships = [item for item in memberships if item.company_id == selected_company_id]
        if not memberships and user.role != UserRole.SUPERADMIN:
            await websocket.close(code=1008, reason='Company access denied')
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

    client_id = _client_id(websocket, user.id)

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
