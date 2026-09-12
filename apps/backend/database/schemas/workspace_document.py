from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


DocumentVisibility = Literal["private", "company", "platform"]
DocumentStatus = Literal["draft", "final", "archived"]
CollaboratorPermission = Literal["view", "edit"]
ExportFormat = Literal["pdf", "docx"]
DocumentAssetKind = Literal["logo", "signature"]
DocumentSignatureMethod = Literal["stored_signature", "electronic"]
DocumentStyleKey = Literal[
    "modern_blue",
    "classic_word",
    "executive_navy",
    "elegant_green",
    "legal_monochrome",
    "warm_professional",
    "minimal_clean",
]


class DocumentAddressBlock(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    label: str = Field(default="Address", max_length=80)
    content: str = Field(default="", max_length=3000)
    x_mm: float = Field(default=22, ge=0, le=330)
    y_mm: float = Field(default=48, ge=0, le=450)
    width_mm: float = Field(default=70, ge=25, le=220)
    font_size_pt: int = Field(default=9, ge=7, le=18)
    alignment: Literal["left", "center", "right"] = "left"
    show_label: bool = True
    first_page_only: bool = True


class DocumentCoverPage(BaseModel):
    title: str = Field(default="", max_length=300)
    subtitle: str = Field(default="", max_length=500)
    prepared_for: str = Field(default="", max_length=300)
    prepared_by: str = Field(default="", max_length=300)
    document_date: str = Field(default="", max_length=120)
    version_label: str = Field(default="", max_length=120)
    confidentiality_note: str = Field(default="", max_length=300)
    show_logo: bool = True
    show_reference: bool = True


class WorkspaceDocumentCreate(BaseModel):
    title: str = Field(default="Untitled document", min_length=1, max_length=255)
    template_key: str = Field(default="formal_letter", max_length=60)
    content_json: dict[str, Any] | None = None
    content_html: str | None = Field(default=None, max_length=2_500_000)
    visibility: DocumentVisibility = "private"
    is_confidential: bool = False
    include_brand_header: bool = True
    include_footer: bool = True
    style_key: DocumentStyleKey = "modern_blue"
    default_font_family: str = Field(default="Arial", min_length=1, max_length=80)
    default_font_size_pt: int = Field(default=11, ge=8, le=36)
    default_line_height_percent: int = Field(default=115, ge=90, le=250)
    cover_page_enabled: bool = False
    cover_page: DocumentCoverPage = Field(default_factory=DocumentCoverPage)
    address_blocks: list[DocumentAddressBlock] = Field(default_factory=list, max_length=24)
    brand_logo_asset_id: UUID | None = None
    company_client_id: UUID | None = None
    loan_id: UUID | None = None
    signer_name: str | None = Field(default=None, max_length=255)
    signer_title: str | None = Field(default=None, max_length=160)
    company_bank_accounts: str | None = Field(default=None, max_length=5000)

    @field_validator("title", "default_font_family")
    @classmethod
    def clean_text(cls, value: str) -> str:
        return value.strip() or "Untitled document"


class WorkspaceDocumentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    content_json: dict[str, Any] | None = None
    content_html: str | None = Field(default=None, max_length=2_500_000)
    visibility: DocumentVisibility | None = None
    status: DocumentStatus | None = None
    expected_version: int | None = Field(default=None, ge=1)
    create_revision: bool = False
    page_size: Literal["A4", "LETTER"] | None = None
    orientation: Literal["portrait", "landscape"] | None = None
    margin_top_mm: int | None = Field(default=None, ge=8, le=60)
    margin_right_mm: int | None = Field(default=None, ge=8, le=60)
    margin_bottom_mm: int | None = Field(default=None, ge=8, le=60)
    margin_left_mm: int | None = Field(default=None, ge=8, le=60)
    style_key: DocumentStyleKey | None = None
    default_font_family: str | None = Field(default=None, min_length=1, max_length=80)
    default_font_size_pt: int | None = Field(default=None, ge=8, le=36)
    default_line_height_percent: int | None = Field(default=None, ge=90, le=250)
    include_brand_header: bool | None = None
    include_footer: bool | None = None
    is_confidential: bool | None = None
    cover_page_enabled: bool | None = None
    cover_page: DocumentCoverPage | None = None
    address_blocks: list[DocumentAddressBlock] | None = Field(default=None, max_length=24)
    brand_logo_asset_id: UUID | None = None
    clear_brand_logo_asset: bool = False


class WorkspaceDocumentCollaboratorCreate(BaseModel):
    user_id: UUID
    permission: CollaboratorPermission = "view"


class WorkspaceDocumentCollaboratorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    display_name: str
    email: str | None = None
    phone: str | None = None
    permission: CollaboratorPermission
    created_at: datetime


class WorkspaceDocumentRevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    title: str
    created_by_user_id: UUID | None = None
    created_at: datetime


class WorkspaceDocumentAssetRead(BaseModel):
    id: UUID
    kind: DocumentAssetKind
    label: str
    original_filename: str | None = None
    mime_type: str
    width_px: int
    height_px: int
    is_default: bool
    created_at: datetime
    updated_at: datetime


class WorkspaceDocumentSignatureCreate(BaseModel):
    field_id: str = Field(min_length=1, max_length=80)
    method: DocumentSignatureMethod
    asset_id: UUID | None = None
    consent_text: str = Field(
        default="I confirm that I intend this electronic action to serve as my signature on this document.",
        min_length=10,
        max_length=1200,
    )


class WorkspaceDocumentSignatureRead(BaseModel):
    id: UUID
    field_id: str
    field_type: str
    signer_user_id: UUID | None = None
    signer_name: str
    method: DocumentSignatureMethod
    asset_id: UUID | None = None
    signed_at: datetime
    document_version: int
    document_hash: str
    verification_code: str
    revoked_at: datetime | None = None


class WorkspaceDocumentCompanyHeader(BaseModel):
    name: str
    registration_number: str | None = None
    license_number: str | None = None
    phone: str | None = None
    email: str | None = None
    website: str | None = None
    address: str | None = None
    district: str | None = None


class WorkspaceDocumentRead(BaseModel):
    id: UUID
    reference: str
    owner_user_id: UUID
    owner_display_name: str
    company_id: UUID | None = None
    branch_id: UUID | None = None
    company_header: WorkspaceDocumentCompanyHeader
    title: str
    template_key: str
    content_json: dict[str, Any]
    content_html: str
    plain_text: str
    visibility: DocumentVisibility
    status: DocumentStatus
    version: int
    page_size: str
    orientation: str
    margin_top_mm: int
    margin_right_mm: int
    margin_bottom_mm: int
    margin_left_mm: int
    style_key: DocumentStyleKey
    default_font_family: str
    default_font_size_pt: int
    default_line_height_percent: int
    include_brand_header: bool
    include_footer: bool
    is_confidential: bool
    brand_logo_asset_id: UUID | None = None
    cover_page_enabled: bool
    cover_page: DocumentCoverPage
    address_blocks: list[DocumentAddressBlock]
    can_edit: bool
    can_manage: bool
    collaborator_count: int
    signature_field_count: int
    applied_signature_count: int
    finalized_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WorkspaceDocumentListRead(BaseModel):
    items: list[WorkspaceDocumentRead]
    total: int


class WorkspaceDocumentPublish(BaseModel):
    format: ExportFormat = "pdf"
    visibility: Literal["private", "company", "platform"] | None = None
    file_name: str | None = Field(default=None, max_length=255)
    is_confidential: bool | None = None
