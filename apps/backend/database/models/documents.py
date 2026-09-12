# database/models/documents.py
from sqlalchemy import Column, String, Enum, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base
from database.models.enums import DocumentType


class BorrowerDocument(Base):
    __tablename__ = "borrower_documents"

    borrower_id = Column(UUID(as_uuid=True), ForeignKey("borrowers.id"), nullable=False)

    document_type = Column(Enum(DocumentType), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)

    is_verified = Column(Boolean, default=False)

    borrower = relationship("Borrower", back_populates="documents")


class LoanRequestDocument(Base):
    __tablename__ = "loan_request_documents"

    loan_request_id = Column(UUID(as_uuid=True), ForeignKey("loan_requests.id"), nullable=False)

    document_type = Column(Enum(DocumentType), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_url = Column(String(500), nullable=False)

    loan_request = relationship("LoanRequest", back_populates="documents")