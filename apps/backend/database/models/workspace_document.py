from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from database.base import Base


class WorkspaceDocument(Base):
    """Editable, versioned document owned by a LoanHub user.

    The rich document body is stored both as Tiptap JSON (lossless editor state)
    and sanitised HTML (portable export state). Signature fields are Tiptap
    block nodes embedded in those two representations, so they travel with
    revisions, collaboration, Word/PDF exports and printed copies.
    """

    __tablename__ = "workspace_documents"

    owner_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("loan_companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    branch_id = Column(
        UUID(as_uuid=True),
        ForeignKey("company_branches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_edited_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    reference = Column(String(40), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    template_key = Column(String(60), nullable=False, default="formal_letter")
    content_json = Column(JSONB, nullable=False, default=dict)
    content_html = Column(Text, nullable=False, default="")
    plain_text = Column(Text, nullable=False, default="")

    visibility = Column(String(30), nullable=False, default="private", index=True)
    status = Column(String(30), nullable=False, default="draft", index=True)
    version = Column(Integer, nullable=False, default=1)

    page_size = Column(String(20), nullable=False, default="A4")
    orientation = Column(String(20), nullable=False, default="portrait")
    margin_top_mm = Column(Integer, nullable=False, default=28)
    margin_right_mm = Column(Integer, nullable=False, default=22)
    margin_bottom_mm = Column(Integer, nullable=False, default=24)
    margin_left_mm = Column(Integer, nullable=False, default=22)

    # Word-like document design defaults. Individual runs/paragraphs can still
    # override these values through Tiptap formatting.
    style_key = Column(String(40), nullable=False, default="modern_blue")
    default_font_family = Column(String(80), nullable=False, default="Arial")
    default_font_size_pt = Column(Integer, nullable=False, default=11)
    default_line_height_percent = Column(Integer, nullable=False, default=115)

    include_brand_header = Column(Boolean, nullable=False, default=True)
    include_footer = Column(Boolean, nullable=False, default=True)
    is_confidential = Column(Boolean, nullable=False, default=False)

    # Advanced document composition. A null brand_logo_asset_id means the
    # writer's current default logo is resolved dynamically, so changing the
    # default updates every document that has not explicitly chosen a logo.
    brand_logo_asset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_document_assets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    cover_page_enabled = Column(Boolean, nullable=False, default=False)
    cover_page = Column(JSONB, nullable=False, default=dict)
    address_blocks = Column(JSONB, nullable=False, default=list)
    finalized_at = Column(DateTime, nullable=True)
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)
    deleted_at = Column(DateTime, nullable=True)

    owner = relationship("User", foreign_keys=[owner_user_id])
    last_editor = relationship("User", foreign_keys=[last_edited_by_user_id])
    company = relationship("LoanCompany")
    branch = relationship("CompanyBranch")
    collaborators = relationship(
        "WorkspaceDocumentCollaborator",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    revisions = relationship(
        "WorkspaceDocumentRevision",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    brand_logo_asset = relationship(
        "WorkspaceDocumentAsset",
        foreign_keys=[brand_logo_asset_id],
    )
    signatures = relationship(
        "WorkspaceDocumentSignature",
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class WorkspaceDocumentCollaborator(Base):
    __tablename__ = "workspace_document_collaborators"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "user_id",
            name="uq_workspace_document_collaborator",
        ),
    )

    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invited_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    permission = Column(String(20), nullable=False, default="view")

    document = relationship("WorkspaceDocument", back_populates="collaborators")
    user = relationship("User", foreign_keys=[user_id])
    invited_by_user = relationship("User", foreign_keys=[invited_by_user_id])


class WorkspaceDocumentRevision(Base):
    __tablename__ = "workspace_document_revisions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version",
            name="uq_workspace_document_revision_version",
        ),
    )

    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    content_json = Column(JSONB, nullable=False, default=dict)
    content_html = Column(Text, nullable=False, default="")
    plain_text = Column(Text, nullable=False, default="")
    created_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    document = relationship("WorkspaceDocument", back_populates="revisions")
    created_by_user = relationship("User", foreign_keys=[created_by_user_id])


class WorkspaceDocumentAsset(Base):
    """Reusable private visual asset owned by a LoanHub user.

    Logos are normalised to PNG. Signature uploads are background-stripped and
    cropped, but are never used for biometric identity matching.
    """

    __tablename__ = "workspace_document_assets"

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
    kind = Column(String(20), nullable=False, index=True)  # logo | signature
    label = Column(String(120), nullable=False)
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(80), nullable=False, default="image/png")
    image_data = Column(LargeBinary, nullable=False)
    is_encrypted = Column(Boolean, nullable=False, default=False)
    encryption_nonce = Column(String(255), nullable=True)
    encryption_version = Column(String(20), nullable=True)
    width_px = Column(Integer, nullable=False)
    height_px = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    is_default = Column(Boolean, nullable=False, default=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    processing_metadata = Column(JSONB, nullable=False, default=dict)

    owner = relationship("User", foreign_keys=[owner_user_id])
    company = relationship("LoanCompany")


class WorkspaceDocumentSignature(Base):
    """Audited application of a stored or electronic signature to a field."""

    __tablename__ = "workspace_document_signatures"

    document_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_id = Column(String(80), nullable=False, index=True)
    field_type = Column(String(30), nullable=False, default="signature")
    signer_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    signer_name = Column(String(255), nullable=False)
    method = Column(String(30), nullable=False)  # stored_signature | electronic
    asset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspace_document_assets.id", ondelete="SET NULL"),
        nullable=True,
    )
    consent_text = Column(Text, nullable=False)
    signed_at = Column(DateTime, nullable=False)
    document_version = Column(Integer, nullable=False)
    document_hash = Column(String(64), nullable=False, index=True)
    verification_code = Column(String(32), nullable=False, unique=True, index=True)
    ip_hash = Column(String(64), nullable=True)
    user_agent_hash = Column(String(64), nullable=True)
    revoked_at = Column(DateTime, nullable=True, index=True)
    revoked_by_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    document = relationship("WorkspaceDocument", back_populates="signatures")
    signer = relationship("User", foreign_keys=[signer_user_id])
    asset = relationship("WorkspaceDocumentAsset", foreign_keys=[asset_id])
    revoked_by_user = relationship("User", foreign_keys=[revoked_by_user_id])
