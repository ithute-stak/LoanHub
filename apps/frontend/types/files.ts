export type ManagedFile = {
    id: string;
    reference: string;
    owner_user_id: string | null;
    company_id: string | null;
    branch_id: string | null;
    original_name: string;
    mime_type: string;
    detected_mime_type?: string | null;
    extension: string | null;
    size_bytes: number;
    checksum_sha256: string;
    is_encrypted?: boolean;
    encryption_version?: string | null;
    scan_status?: "pending" | "clean" | "quarantined" | "failed" | string;
    quarantine_reason?: string | null;
    category: string;
    visibility: string;
    description: string | null;
    linked_entity_type: string | null;
    linked_entity_id: string | null;
    is_confidential: boolean;
    created_at: string;
    updated_at: string;
};

export type ManagedFileList = {
    items: ManagedFile[];
    total: number;
};


export type ExternalFileShare = {
    id: string;
    file_id: string;
    company_id: string | null;
    created_by_user_id: string | null;
    label: string | null;
    share_url: string | null;
    expires_at: string;
    revoked_at: string | null;
    access_count: number;
    allow_download: boolean;
    created_at: string;
};

export type CompanySocialShareSettings = {
    id: string;
    company_id: string;
    external_sharing_enabled: boolean;
    default_expiry_hours: number;
    default_message: string | null;
    enabled_channels: string[];
    whatsapp_number: string | null;
    facebook_url: string | null;
    instagram_url: string | null;
    linkedin_url: string | null;
    x_handle: string | null;
    telegram_username: string | null;
    youtube_url: string | null;
    configured_by_user_id: string | null;
    created_at: string;
    updated_at: string;
};
