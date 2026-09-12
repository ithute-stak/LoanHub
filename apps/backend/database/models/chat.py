from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class ChatConversation(Base):
    __tablename__ = 'chat_conversations'

    reference = Column(String(40), nullable=False, unique=True, index=True)
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey('loan_companies.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey('company_branches.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    title = Column(String(200), nullable=True)
    conversation_type = Column(String(40), nullable=False, default='direct', index=True)
    context_type = Column(String(80), nullable=True, index=True)
    context_id = Column(String(120), nullable=True, index=True)
    is_group = Column(Boolean, nullable=False, default=False)
    is_archived = Column(Boolean, nullable=False, default=False, index=True)
    last_message_at = Column(DateTime, nullable=True, index=True)

    created_by_user = relationship('User', foreign_keys=[created_by_user_id])
    participants = relationship(
        'ChatParticipant',
        back_populates='conversation',
        cascade='all, delete-orphan',
    )
    messages = relationship(
        'ChatMessage',
        back_populates='conversation',
        cascade='all, delete-orphan',
        order_by='ChatMessage.created_at',
    )


class ChatParticipant(Base):
    __tablename__ = 'chat_participants'
    __table_args__ = (
        UniqueConstraint(
            'conversation_id',
            'user_id',
            name='uq_chat_participant_conversation_user',
        ),
    )

    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey('chat_conversations.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    participant_role = Column(String(80), nullable=True)
    is_admin = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    joined_at = Column(DateTime, nullable=False)
    last_read_at = Column(DateTime, nullable=True)
    muted_until = Column(DateTime, nullable=True)

    conversation = relationship('ChatConversation', back_populates='participants')
    user = relationship('User')


class ChatMessage(Base):
    __tablename__ = 'chat_messages'
    __table_args__ = (
        UniqueConstraint(
            'sender_user_id',
            'client_message_id',
            name='uq_chat_message_sender_client_id',
        ),
    )

    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey('chat_conversations.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    sender_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey('loan_companies.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey('company_branches.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    reply_to_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey('chat_messages.id', ondelete='SET NULL'),
        nullable=True,
    )

    message_type = Column(String(30), nullable=False, default='text', index=True)
    # Legacy plaintext is retained for migration compatibility. New and edited
    # messages are written only to the authenticated-encryption columns.
    body = Column(Text, nullable=True)
    body_ciphertext = Column(Text, nullable=True)
    body_nonce = Column(String(64), nullable=True)
    encryption_version = Column(String(20), nullable=True)
    client_message_id = Column(String(100), nullable=False)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    edited_at = Column(DateTime, nullable=True)
    deleted_at = Column(DateTime, nullable=True, index=True)

    conversation = relationship('ChatConversation', back_populates='messages')
    sender = relationship('User', foreign_keys=[sender_user_id])
    reply_to = relationship('ChatMessage', remote_side='ChatMessage.id')
    attachments = relationship(
        'ChatMessageAttachment',
        back_populates='message',
        cascade='all, delete-orphan',
    )


class ChatMessageAttachment(Base):
    __tablename__ = 'chat_message_attachments'
    __table_args__ = (
        UniqueConstraint(
            'message_id',
            'file_id',
            name='uq_chat_message_file',
        ),
    )

    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey('chat_messages.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    file_id = Column(
        UUID(as_uuid=True),
        ForeignKey('managed_files.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    caption = Column(String(500), nullable=True)

    message = relationship('ChatMessage', back_populates='attachments')
    file = relationship('ManagedFile')
