import type { ManagedFile } from "@/types/files";

export type DocumentVisibility = "private" | "company" | "platform";
export type DocumentStatus = "draft" | "final" | "archived";
export type DocumentPermission = "view" | "edit";
export type DocumentExportFormat = "pdf" | "docx";
export type DocumentPageSize = "A4" | "LETTER";
export type DocumentOrientation = "portrait" | "landscape";
export type DocumentStyleKey =
    | "modern_blue"
    | "classic_word"
    | "executive_navy"
    | "elegant_green"
    | "legal_monochrome"
    | "warm_professional"
    | "minimal_clean";

export type SignatureFieldType =
    | "signature"
    | "initials"
    | "date"
    | "name"
    | "title"
    | "text"
    | "checkbox";

export type DocumentAddressBlock = {
    id: string;
    label: string;
    content: string;
    x_mm: number;
    y_mm: number;
    width_mm: number;
    font_size_pt: number;
    alignment: "left" | "center" | "right";
    show_label: boolean;
    first_page_only: boolean;
};

export type DocumentCoverPage = {
    title: string;
    subtitle: string;
    prepared_for: string;
    prepared_by: string;
    document_date: string;
    version_label: string;
    confidentiality_note: string;
    show_logo: boolean;
    show_reference: boolean;
};

export type DocumentAssetKind = "logo" | "signature";

export type WorkspaceDocumentAsset = {
    id: string;
    kind: DocumentAssetKind;
    label: string;
    original_filename: string | null;
    mime_type: string;
    width_px: number;
    height_px: number;
    is_default: boolean;
    created_at: string;
    updated_at: string;
};

export type DocumentSignatureMethod = "stored_signature" | "electronic";

export type WorkspaceDocumentSignature = {
    id: string;
    field_id: string;
    field_type: string;
    signer_user_id: string | null;
    signer_name: string;
    method: DocumentSignatureMethod;
    asset_id: string | null;
    signed_at: string;
    document_version: number;
    document_hash: string;
    verification_code: string;
    revoked_at: string | null;
};

export type WorkspaceDocumentCompanyHeader = {
    name: string;
    registration_number: string | null;
    license_number: string | null;
    phone: string | null;
    email: string | null;
    website: string | null;
    address: string | null;
    district: string | null;
};

export type WorkspaceDocument = {
    id: string;
    reference: string;
    owner_user_id: string;
    owner_display_name: string;
    company_id: string | null;
    branch_id: string | null;
    company_header: WorkspaceDocumentCompanyHeader;
    title: string;
    template_key: string;
    content_json: Record<string, unknown>;
    content_html: string;
    plain_text: string;
    visibility: DocumentVisibility;
    status: DocumentStatus;
    version: number;
    page_size: DocumentPageSize;
    orientation: DocumentOrientation;
    margin_top_mm: number;
    margin_right_mm: number;
    margin_bottom_mm: number;
    margin_left_mm: number;
    style_key: DocumentStyleKey;
    default_font_family: string;
    default_font_size_pt: number;
    default_line_height_percent: number;
    include_brand_header: boolean;
    include_footer: boolean;
    is_confidential: boolean;
    brand_logo_asset_id: string | null;
    cover_page_enabled: boolean;
    cover_page: DocumentCoverPage;
    address_blocks: DocumentAddressBlock[];
    can_edit: boolean;
    can_manage: boolean;
    collaborator_count: number;
    signature_field_count: number;
    applied_signature_count: number;
    finalized_at: string | null;
    created_at: string;
    updated_at: string;
};

export type WorkspaceDocumentList = {
    items: WorkspaceDocument[];
    total: number;
};

export type WorkspaceDocumentCollaborator = {
    id: string;
    user_id: string;
    display_name: string;
    email: string | null;
    phone: string | null;
    permission: DocumentPermission;
    created_at: string;
};

export type WorkspaceDocumentRevision = {
    id: string;
    version: number;
    title: string;
    created_by_user_id: string | null;
    created_at: string;
};

export type CreateWorkspaceDocumentPayload = {
    title: string;
    template_key: string;
    visibility: DocumentVisibility;
    is_confidential?: boolean;
    include_brand_header?: boolean;
    include_footer?: boolean;
    style_key?: DocumentStyleKey;
    default_font_family?: string;
    default_font_size_pt?: number;
    default_line_height_percent?: number;
    cover_page_enabled?: boolean;
    cover_page?: Partial<DocumentCoverPage>;
    address_blocks?: DocumentAddressBlock[];
    brand_logo_asset_id?: string | null;
    company_client_id?: string | null;
    loan_id?: string | null;
    signer_name?: string | null;
    signer_title?: string | null;
    company_bank_accounts?: string | null;
};

export type UpdateWorkspaceDocumentPayload = {
    title?: string;
    content_json?: Record<string, unknown>;
    content_html?: string;
    visibility?: DocumentVisibility;
    status?: DocumentStatus;
    expected_version?: number;
    create_revision?: boolean;
    page_size?: DocumentPageSize;
    orientation?: DocumentOrientation;
    margin_top_mm?: number;
    margin_right_mm?: number;
    margin_bottom_mm?: number;
    margin_left_mm?: number;
    style_key?: DocumentStyleKey;
    default_font_family?: string;
    default_font_size_pt?: number;
    default_line_height_percent?: number;
    include_brand_header?: boolean;
    include_footer?: boolean;
    is_confidential?: boolean;
    brand_logo_asset_id?: string | null;
    clear_brand_logo_asset?: boolean;
    cover_page_enabled?: boolean;
    cover_page?: DocumentCoverPage;
    address_blocks?: DocumentAddressBlock[];
};

export type PublishedWorkspaceDocument = ManagedFile;
