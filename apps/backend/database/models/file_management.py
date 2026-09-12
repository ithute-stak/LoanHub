from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class ManagedFile(Base):
    __tablename__ = 'managed_files'

    owner_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey('users.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey('loan_companies.id', ondelete='CASCADE'),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey('company_branches.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )

    reference = Column(String(40), nullable=False, unique=True, index=True)
    original_name = Column(String(255), nullable=False)
    stored_name = Column(String(255), nullable=False)
    storage_key = Column(String(700), nullable=False, unique=True)
    storage_provider = Column(String(30), nullable=False, default='local')
    mime_type = Column(String(150), nullable=False)
    detected_mime_type = Column(String(150), nullable=True)
    extension = Column(String(30), nullable=True)
    size_bytes = Column(BigInteger, nullable=False)
    checksum_sha256 = Column(String(64), nullable=False, index=True)

    is_encrypted = Column(Boolean, nullable=False, default=False)
    encryption_nonce = Column(String(64), nullable=True)
    encryption_version = Column(String(20), nullable=True)
    scan_status = Column(String(30), nullable=False, default='validated', index=True)
    quarantined_reason = Column(Text, nullable=True)

    category = Column(String(80), nullable=False, default='general', index=True)
    visibility = Column(String(40), nullable=False, default='private', index=True)
    description = Column(Text, nullable=True)
    linked_entity_type = Column(String(100), nullable=True, index=True)
    linked_entity_id = Column(String(120), nullable=True, index=True)
    is_confidential = Column(Boolean, nullable=False, default=False)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    owner = relationship('User')
    company = relationship('LoanCompany')
    branch = relationship('CompanyBranch')
