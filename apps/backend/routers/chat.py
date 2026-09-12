from __future__ import annotations

import uuid
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from core.access_control import TenantContext, get_user_context
from core.websocket_manager import manager
from database.models.borrower import Borrower
from database.models.chat import ChatConversation, ChatMessage, ChatMessageAttachment, ChatParticipant
from database.models.client_loan_company import ClientCompanyLoan
from database.models.company_staff import CompanyStaff
from database.models.enums import UserRole
from database.models.file_management import ManagedFile
from database.models.person import Person
from database.models.user import User
from database.schemas.chat import (
    ChatConversationCreate,
    ChatConversationRead,
    ChatExistingFileShareCreate,
    ChatMessageCreate,
    ChatMessageRead,
    ChatMessageUpdate,
    ChatParticipantRead,
    ChatUnreadCountRead,
    ChatUserRead,
)
from database.schemas.file_management import ManagedFileRead
from database.session import get_db
from services.crypto_service import decrypt_chat_text, encrypt_chat_text
from services.file_service import can_access_file, save_upload


router = APIRouter(prefix='/chat', tags=['Platform Chat'])


def user_query(db: Session):
    return db.query(User).options(joinedload(User.person))


def display_name(user: User) -> str:
    if user.person and user.person.full_name:
        return user.person.full_name
    return user.email or user.phone or 'LoanHub user'


def membership_for(db: Session, user_id: UUID, company_id: UUID | None = None):
    query = db.query(CompanyStaff).options(
        joinedload(CompanyStaff.company),
        joinedload(CompanyStaff.branch),
    ).filter(
        CompanyStaff.user_id == user_id,
        CompanyStaff.is_active.is_(True),
    )
    if company_id:
        query = query.filter(CompanyStaff.company_id == company_id)
    return query.first()


def user_read(db: Session, user: User, preferred_company_id=None) -> ChatUserRead:
    membership = membership_for(db, user.id, preferred_company_id)
    return ChatUserRead(
        id=user.id,
        display_name=display_name(user),
        email=user.email,
        phone=user.phone,
        role=(membership.role.value if membership else user.role.value),
        company_name=(membership.company.name if membership and membership.company else None),
        branch_name=(membership.branch.name if membership and membership.branch else None),
        is_online=manager.is_user_online(str(user.id)),
        last_seen_at=user.last_seen_at,
    )


def allowed_directory_ids(db: Session, context: TenantContext) -> set[UUID]:
    ids: set[UUID] = {context.user.id}
    if context.is_platform_admin:
        ids.update(item[0] for item in db.query(User.id).filter(User.is_active.is_(True)).all())
        return ids

    ids.update(item[0] for item in db.query(User.id).filter(
        User.role == UserRole.SUPERADMIN,
        User.is_active.is_(True),
    ).all())

    if context.company_id:
        ids.update(item[0] for item in db.query(CompanyStaff.user_id).filter(
            CompanyStaff.company_id == context.company_id,
            CompanyStaff.is_active.is_(True),
        ).all())
        borrower_user_ids = (
            db.query(Borrower.user_id)
            .join(ClientCompanyLoan, ClientCompanyLoan.borrower_id == Borrower.id)
            .filter(ClientCompanyLoan.company_id == context.company_id)
            .distinct()
            .all()
        )
        ids.update(item[0] for item in borrower_user_ids)
        return ids

    borrower = db.query(Borrower).filter(Borrower.user_id == context.user.id).first()
    if borrower:
        company_ids = [item[0] for item in db.query(ClientCompanyLoan.company_id).filter(
            ClientCompanyLoan.borrower_id == borrower.id
        ).distinct().all()]
        if company_ids:
            ids.update(item[0] for item in db.query(CompanyStaff.user_id).filter(
                CompanyStaff.company_id.in_(company_ids),
                CompanyStaff.is_active.is_(True),
                CompanyStaff.role.in_({
                    UserRole.COMPANY_OWNER,
                    UserRole.COMPANY_ADMIN,
                    UserRole.BRANCH_MANAGER,
                    UserRole.LOAN_OFFICER,
                    UserRole.FINANCE_OFFICER,
                    UserRole.COLLECTIONS_OFFICER,
                    UserRole.CUSTOMER_SUPPORT,
                }),
            ).all())
    return ids


def participant_or_403(db: Session, conversation_id: UUID, user_id: UUID) -> ChatParticipant:
    participant = db.query(ChatParticipant).filter(
        ChatParticipant.conversation_id == conversation_id,
        ChatParticipant.user_id == user_id,
        ChatParticipant.is_active.is_(True),
    ).first()
    if not participant:
        raise HTTPException(status_code=403, detail='You are not a participant in this conversation')
    return participant


def conversation_or_404(db: Session, conversation_id: UUID, user_id: UUID) -> ChatConversation:
    participant_or_403(db, conversation_id, user_id)
    conversation = db.query(ChatConversation).options(
        joinedload(ChatConversation.participants)
        .joinedload(ChatParticipant.user)
        .joinedload(User.person)
    ).filter(ChatConversation.id == conversation_id).first()
    if not conversation:
        raise HTTPException(status_code=404, detail='Conversation not found')
    return conversation


def attachment_read(item: ChatMessageAttachment) -> ManagedFileRead:
    return ManagedFileRead.model_validate(item.file)


def _message_body(message: ChatMessage) -> str | None:
    if message.deleted_at:
        return None
    if message.body_ciphertext:
        try:
            return decrypt_chat_text(
                message.body_ciphertext,
                message.body_nonce,
                message.encryption_version,
            )
        except ValueError:
            return '[Encrypted message unavailable - contact the platform owner with the message reference]'
    return message.body


def _set_encrypted_body(message: ChatMessage, value: str | None) -> None:
    if not value:
        message.body = None
        message.body_ciphertext = None
        message.body_nonce = None
        message.encryption_version = None
        return
    ciphertext, nonce, version = encrypt_chat_text(value.strip())
    message.body = None
    message.body_ciphertext = ciphertext
    message.body_nonce = nonce
    message.encryption_version = version


def message_read(db: Session, message: ChatMessage) -> ChatMessageRead:
    sender = user_read(db, message.sender, message.company_id) if message.sender else None
    return ChatMessageRead(
        id=message.id,
        conversation_id=message.conversation_id,
        sender=sender,
        message_type=message.message_type,
        body=_message_body(message),
        reply_to_message_id=message.reply_to_message_id,
        client_message_id=message.client_message_id,
        attachments=[
            attachment_read(item)
            for item in message.attachments
            if not item.file.is_deleted and item.file.scan_status != 'quarantined'
        ],
        edited_at=message.edited_at,
        deleted_at=message.deleted_at,
        created_at=message.created_at,
    )


def conversation_read(db: Session, conversation: ChatConversation, user_id: UUID) -> ChatConversationRead:
    participant = next((item for item in conversation.participants if item.user_id == user_id), None)
    last_message = db.query(ChatMessage).options(
        joinedload(ChatMessage.sender).joinedload(User.person),
        joinedload(ChatMessage.attachments).joinedload(ChatMessageAttachment.file),
    ).filter(ChatMessage.conversation_id == conversation.id).order_by(ChatMessage.created_at.desc()).first()
    unread_query = db.query(func.count(ChatMessage.id)).filter(
        ChatMessage.conversation_id == conversation.id,
        ChatMessage.sender_user_id != user_id,
        ChatMessage.deleted_at.is_(None),
    )
    if participant and participant.last_read_at:
        unread_query = unread_query.filter(ChatMessage.created_at > participant.last_read_at)

    participants = [
        ChatParticipantRead(
            user=user_read(db, item.user, conversation.company_id),
            is_admin=item.is_admin,
            last_read_at=item.last_read_at,
        )
        for item in conversation.participants
        if item.is_active
    ]
    title = conversation.title
    if not title:
        other_names = [item.user.display_name for item in participants if item.user.id != user_id]
        title = ', '.join(other_names[:3]) or 'Personal notes'
    return ChatConversationRead(
        id=conversation.id,
        reference=conversation.reference,
        title=title,
        conversation_type=conversation.conversation_type,
        is_group=conversation.is_group,
        company_id=conversation.company_id,
        branch_id=conversation.branch_id,
        context_type=conversation.context_type,
        context_id=conversation.context_id,
        participants=participants,
        last_message=message_read(db, last_message) if last_message else None,
        unread_count=int(unread_query.scalar() or 0),
        last_message_at=conversation.last_message_at,
        created_at=conversation.created_at,
    )


async def broadcast_chat_event(conversation: ChatConversation, payload: dict) -> None:
    for participant in conversation.participants:
        if participant.is_active:
            await manager.send_to_user(str(participant.user_id), payload)


async def broadcast_message(db: Session, conversation: ChatConversation, message: ChatMessage) -> None:
    await broadcast_chat_event(
        conversation,
        {
            'type': 'CHAT_MESSAGE_CREATED',
            'conversation_id': str(conversation.id),
            'message': message_read(db, message).model_dump(mode='json'),
        },
    )


@router.get('/directory', response_model=list[ChatUserRead])
def chat_directory(
    search: str | None = None,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    ids = allowed_directory_ids(db, context)
    query = user_query(db).filter(User.id.in_(ids), User.is_active.is_(True))
    if search:
        token = f'%{search.strip()}%'
        query = query.outerjoin(Person, Person.user_id == User.id).filter(or_(
            User.email.ilike(token),
            User.phone.ilike(token),
            Person.first_name.ilike(token),
            Person.last_name.ilike(token),
        ))
    users = query.order_by(User.created_at.desc()).limit(200).all()
    return [user_read(db, user, context.company_id) for user in users if user.id != context.user.id]


@router.get('/conversations', response_model=list[ChatConversationRead])
def list_conversations(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    conversations = db.query(ChatConversation).join(ChatParticipant).options(
        joinedload(ChatConversation.participants)
        .joinedload(ChatParticipant.user)
        .joinedload(User.person)
    ).filter(
        ChatParticipant.user_id == context.user.id,
        ChatParticipant.is_active.is_(True),
        ChatConversation.is_archived.is_(False),
    ).order_by(
        ChatConversation.last_message_at.desc().nullslast(),
        ChatConversation.created_at.desc(),
    ).all()
    return [conversation_read(db, item, context.user.id) for item in conversations]


@router.get('/unread-count', response_model=ChatUnreadCountRead)
def unread_count(
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    participants = db.query(ChatParticipant).filter(
        ChatParticipant.user_id == context.user.id,
        ChatParticipant.is_active.is_(True),
    ).all()
    count = 0
    for participant in participants:
        query = db.query(func.count(ChatMessage.id)).filter(
            ChatMessage.conversation_id == participant.conversation_id,
            ChatMessage.sender_user_id != context.user.id,
            ChatMessage.deleted_at.is_(None),
        )
        if participant.last_read_at:
            query = query.filter(ChatMessage.created_at > participant.last_read_at)
        count += int(query.scalar() or 0)
    return ChatUnreadCountRead(unread_count=count)


@router.post('/conversations', response_model=ChatConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ChatConversationCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    allowed = allowed_directory_ids(db, context)
    requested = set(payload.participant_ids)
    if not requested.issubset(allowed):
        raise HTTPException(status_code=403, detail='One or more participants are outside your communication scope')

    participant_ids = list(dict.fromkeys([context.user.id, *payload.participant_ids]))
    is_group = len(participant_ids) > 2 or payload.conversation_type in {'group', 'support', 'loan'}

    if not is_group and len(participant_ids) == 2:
        candidates = (
            db.query(ChatConversation)
            .join(ChatParticipant)
            .options(
                joinedload(ChatConversation.participants)
                .joinedload(ChatParticipant.user)
                .joinedload(User.person)
            )
            .filter(
                ChatParticipant.user_id == context.user.id,
                ChatParticipant.is_active.is_(True),
                ChatConversation.is_group.is_(False),
                ChatConversation.is_archived.is_(False),
            )
            .all()
        )
        requested_ids = set(participant_ids)
        for candidate in candidates:
            active_ids = {item.user_id for item in candidate.participants if item.is_active}
            if active_ids == requested_ids:
                return conversation_read(db, candidate, context.user.id)

    conversation = ChatConversation(
        reference=f'CHAT-{uuid.uuid4().hex[:10].upper()}',
        company_id=context.company_id,
        branch_id=context.branch_id,
        created_by_user_id=context.user.id,
        title=payload.title.strip() if payload.title else None,
        conversation_type=payload.conversation_type,
        context_type=payload.context_type,
        context_id=payload.context_id,
        is_group=is_group,
    )
    db.add(conversation)
    db.flush()
    now = datetime.now(timezone.utc)
    roles = dict(db.query(User.id, User.role).filter(User.id.in_(participant_ids)).all())
    for user_id in participant_ids:
        db.add(ChatParticipant(
            conversation_id=conversation.id,
            user_id=user_id,
            participant_role=roles[user_id].value if user_id in roles else None,
            is_admin=user_id == context.user.id,
            joined_at=now,
            last_read_at=now if user_id == context.user.id else None,
        ))
    db.commit()
    conversation = conversation_or_404(db, conversation.id, context.user.id)
    return conversation_read(db, conversation, context.user.id)


@router.get('/conversations/{conversation_id}/messages', response_model=list[ChatMessageRead])
def list_messages(
    conversation_id: UUID,
    before: datetime | None = None,
    limit: int = Query(60, ge=1, le=200),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    conversation_or_404(db, conversation_id, context.user.id)
    query = db.query(ChatMessage).options(
        joinedload(ChatMessage.sender).joinedload(User.person),
        joinedload(ChatMessage.attachments).joinedload(ChatMessageAttachment.file),
    ).filter(ChatMessage.conversation_id == conversation_id)
    if before:
        query = query.filter(ChatMessage.created_at < before)
    items = query.order_by(ChatMessage.created_at.desc()).limit(limit).all()
    return [message_read(db, item) for item in reversed(items)]


@router.post('/conversations/{conversation_id}/messages', response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: UUID,
    payload: ChatMessageCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    conversation = conversation_or_404(db, conversation_id, context.user.id)
    existing = db.query(ChatMessage).filter(
        ChatMessage.sender_user_id == context.user.id,
        ChatMessage.client_message_id == payload.client_message_id,
    ).first()
    if existing:
        return message_read(db, existing)

    message = ChatMessage(
        conversation_id=conversation.id,
        sender_user_id=context.user.id,
        company_id=conversation.company_id,
        branch_id=conversation.branch_id,
        message_type='text',
        client_message_id=payload.client_message_id,
        reply_to_message_id=payload.reply_to_message_id,
    )
    _set_encrypted_body(message, payload.body)
    db.add(message)
    conversation.last_message_at = datetime.now(timezone.utc)
    participant_or_403(db, conversation.id, context.user.id).last_read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(message)
    conversation = conversation_or_404(db, conversation.id, context.user.id)
    await broadcast_message(db, conversation, message)
    return message_read(db, message)


@router.post('/conversations/{conversation_id}/files', response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
async def send_file_message(
    conversation_id: UUID,
    file: UploadFile | None = File(None),
    body: str | None = Form(None),
    client_message_id: str | None = Form(None),
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    if file is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Upload must use multipart/form-data with a file field named 'file'.",
        )

    # Older clients did not always provide an idempotency key. Keep uploads
    # functional while still generating a stable ID for the persisted message.
    client_message_id = (client_message_id or str(uuid.uuid4())).strip()
    if not client_message_id:
        client_message_id = str(uuid.uuid4())

    conversation = conversation_or_404(db, conversation_id, context.user.id)
    existing = db.query(ChatMessage).options(
        joinedload(ChatMessage.sender).joinedload(User.person),
        joinedload(ChatMessage.attachments).joinedload(ChatMessageAttachment.file),
    ).filter(
        ChatMessage.sender_user_id == context.user.id,
        ChatMessage.client_message_id == client_message_id,
    ).first()
    if existing:
        await file.close()
        return message_read(db, existing)

    declared_mime = (file.content_type or '').lower()
    message = ChatMessage(
        conversation_id=conversation.id,
        sender_user_id=context.user.id,
        company_id=conversation.company_id,
        branch_id=conversation.branch_id,
        message_type='voice' if declared_mime.startswith('audio/') else 'file',
        client_message_id=client_message_id,
    )
    _set_encrypted_body(message, body.strip() if body else None)
    db.add(message)
    db.flush()

    stored = await save_upload(
        db,
        file,
        context,
        category='voice_notes' if declared_mime.startswith('audio/') else 'chat',
        visibility='conversation',
        description=body,
        linked_entity_type='chat_message',
        linked_entity_id=str(message.id),
        company_id=conversation.company_id,
        branch_id=conversation.branch_id,
    )
    if stored.mime_type.startswith('audio/'):
        message.message_type = 'voice'
    db.add(ChatMessageAttachment(message_id=message.id, file_id=stored.id))
    conversation.last_message_at = datetime.now(timezone.utc)
    participant_or_403(db, conversation.id, context.user.id).last_read_at = datetime.now(timezone.utc)
    db.commit()

    message = db.query(ChatMessage).options(
        joinedload(ChatMessage.sender).joinedload(User.person),
        joinedload(ChatMessage.attachments).joinedload(ChatMessageAttachment.file),
    ).filter(ChatMessage.id == message.id).first()
    conversation = conversation_or_404(db, conversation.id, context.user.id)
    await broadcast_message(db, conversation, message)
    return message_read(db, message)


@router.post('/conversations/{conversation_id}/share-file/{file_id}', response_model=ChatMessageRead, status_code=status.HTTP_201_CREATED)
async def share_existing_file_message(
    conversation_id: UUID,
    file_id: UUID,
    payload: ChatExistingFileShareCreate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    conversation = conversation_or_404(db, conversation_id, context.user.id)
    record = db.query(ManagedFile).filter(
        ManagedFile.id == file_id,
        ManagedFile.is_deleted.is_(False),
    ).first()
    if not record or not can_access_file(db, context, record):
        raise HTTPException(status_code=404, detail='File not found')
    if record.scan_status == 'quarantined':
        raise HTTPException(status_code=409, detail='Quarantined files cannot be shared')

    existing = db.query(ChatMessage).options(
        joinedload(ChatMessage.sender).joinedload(User.person),
        joinedload(ChatMessage.attachments).joinedload(ChatMessageAttachment.file),
    ).filter(
        ChatMessage.sender_user_id == context.user.id,
        ChatMessage.client_message_id == payload.client_message_id,
    ).first()
    if existing:
        return message_read(db, existing)

    message = ChatMessage(
        conversation_id=conversation.id,
        sender_user_id=context.user.id,
        company_id=conversation.company_id,
        branch_id=conversation.branch_id,
        message_type='file',
        client_message_id=payload.client_message_id,
        metadata_json={
            'shared_existing_file': True,
            'file_reference': record.reference,
        },
    )
    _set_encrypted_body(
        message,
        payload.body or f'Shared document: {record.original_name}',
    )
    db.add(message)
    db.flush()
    db.add(ChatMessageAttachment(message_id=message.id, file_id=record.id))
    conversation.last_message_at = datetime.now(timezone.utc)
    participant_or_403(db, conversation.id, context.user.id).last_read_at = datetime.now(timezone.utc)
    db.commit()

    message = db.query(ChatMessage).options(
        joinedload(ChatMessage.sender).joinedload(User.person),
        joinedload(ChatMessage.attachments).joinedload(ChatMessageAttachment.file),
    ).filter(ChatMessage.id == message.id).first()
    conversation = conversation_or_404(db, conversation.id, context.user.id)
    await broadcast_message(db, conversation, message)
    return message_read(db, message)


@router.patch('/conversations/{conversation_id}/read', status_code=status.HTTP_204_NO_CONTENT)
async def mark_conversation_read(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    conversation = conversation_or_404(db, conversation_id, context.user.id)
    participant = participant_or_403(db, conversation_id, context.user.id)
    participant.last_read_at = datetime.now(timezone.utc)
    db.commit()
    await broadcast_chat_event(
        conversation,
        {
            'type': 'CHAT_CONVERSATION_READ',
            'conversation_id': str(conversation_id),
            'user_id': str(context.user.id),
            'read_at': participant.last_read_at.isoformat(),
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch('/messages/{message_id}', response_model=ChatMessageRead)
async def update_message(
    message_id: UUID,
    payload: ChatMessageUpdate,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    message = db.query(ChatMessage).options(
        joinedload(ChatMessage.sender).joinedload(User.person),
        joinedload(ChatMessage.attachments).joinedload(ChatMessageAttachment.file),
    ).filter(ChatMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail='Message not found')
    participant_or_403(db, message.conversation_id, context.user.id)
    if message.sender_user_id != context.user.id:
        raise HTTPException(status_code=403, detail='You can only edit your own messages')
    if message.deleted_at:
        raise HTTPException(status_code=409, detail='Deleted messages cannot be edited')

    _set_encrypted_body(message, payload.body)
    message.edited_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(message)
    conversation = conversation_or_404(db, message.conversation_id, context.user.id)
    serialized = message_read(db, message)
    await broadcast_chat_event(
        conversation,
        {
            'type': 'CHAT_MESSAGE_UPDATED',
            'conversation_id': str(message.conversation_id),
            'message': serialized.model_dump(mode='json'),
        },
    )
    return serialized


@router.delete('/messages/{message_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: UUID,
    db: Session = Depends(get_db),
    context: TenantContext = Depends(get_user_context),
):
    message = db.query(ChatMessage).options(
        joinedload(ChatMessage.sender).joinedload(User.person),
        joinedload(ChatMessage.attachments).joinedload(ChatMessageAttachment.file),
    ).filter(ChatMessage.id == message_id).first()
    if not message:
        raise HTTPException(status_code=404, detail='Message not found')
    participant_or_403(db, message.conversation_id, context.user.id)
    if message.sender_user_id != context.user.id and not context.is_platform_admin:
        raise HTTPException(status_code=403, detail='You can only delete your own messages')

    _set_encrypted_body(message, None)
    message.deleted_at = datetime.now(timezone.utc)
    db.commit()
    conversation = conversation_or_404(db, message.conversation_id, context.user.id)
    await broadcast_chat_event(
        conversation,
        {
            'type': 'CHAT_MESSAGE_DELETED',
            'conversation_id': str(message.conversation_id),
            'message': message_read(db, message).model_dump(mode='json'),
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
