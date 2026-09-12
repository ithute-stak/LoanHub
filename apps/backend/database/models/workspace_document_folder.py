from sqlalchemy import Boolean, Column, ForeignKey, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from database.base import Base


class WorkspaceDocumentFolder(Base):
    """User-owned folder for organising Document Studio work.

    Folders are intentionally separate from document visibility. A document can
    remain private/company/platform-visible while its owner organises it in a
    personal folder tree.
    """

    __tablename__ = "workspace_document_folders"
    __table_args__ = (
        # PostgreSQL treats NULL values as distinct in a normal unique
        # constraint. Partial indexes make root-folder names unique too, while
        # allowing a user to recreate a name after a folder is soft-deleted.
        Index(
            "uq_workspace_document_folder_root_name",
            "owner_user_id",
            "normalized_name",
            unique=True,
            postgresql_where=text("parent_id IS NULL AND is_deleted = false"),
        ),
        Index(
            "uq_workspace_document_folder_child_name",
            "owner_user_id",
            "parent_id",
            "normalized_name",
            unique=True,
            postgresql_where=text("parent_id IS NOT NULL AND is_deleted = false"),
        ),
    )

    owner_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_document_folders.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(120), nullable=False)
    normalized_name = Column(String(120), nullable=False)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)

    owner = relationship("User", foreign_keys=[owner_user_id])
    company = relationship("LoanCompany")
    parent = relationship("WorkspaceDocumentFolder", remote_side="WorkspaceDocumentFolder.id")
    items = relationship(
        "WorkspaceDocumentFolderItem",
        back_populates="folder",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class WorkspaceDocumentFolderItem(Base):
    """One folder assignment per Document Studio document."""

    __tablename__ = "workspace_document_folder_items"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_workspace_document_folder_item_document"),
    )

    folder_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_document_folders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    folder = relationship("WorkspaceDocumentFolder", back_populates="items")
    document = relationship("WorkspaceDocument")
