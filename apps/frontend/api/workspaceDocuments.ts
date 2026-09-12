import { api } from "@/lib/api";
import type {
    CreateWorkspaceDocumentPayload,
    DocumentExportFormat,
    DocumentPermission,
    DocumentVisibility,
    PublishedWorkspaceDocument,
    UpdateWorkspaceDocumentPayload,
    WorkspaceDocument,
    WorkspaceDocumentCollaborator,
    WorkspaceDocumentList,
    WorkspaceDocumentRevision,
} from "@/types/workspaceDocuments";

export type WorkspaceItemKind = "document" | "spreadsheet" | "all";

export async function listWorkspaceDocuments(params?: {
    search?: string;
    status?: string;
    kind?: WorkspaceItemKind;
    skip?: number;
    limit?: number;
}): Promise<WorkspaceDocumentList> {
    const response = await api.get<WorkspaceDocumentList>("/workspace-documents", { params });
    return response.data;
}

async function autoFileWorkspaceItem(documentId: string): Promise<void> {
    try {
        await fileWorkspaceItemToPersonalFolder(documentId);
    } catch {
        // Filing must never turn a successfully-created document into a failed
        // creation response. The organizer repairs unassigned personal work on
        // its next load.
    }
}

export async function createWorkspaceDocument(
    payload: CreateWorkspaceDocumentPayload,
): Promise<WorkspaceDocument> {
    const response = await api.post<WorkspaceDocument>("/workspace-documents", payload);
    await autoFileWorkspaceItem(response.data.id);
    return response.data;
}

export async function getWorkspaceDocument(documentId: string): Promise<WorkspaceDocument> {
    const response = await api.get<WorkspaceDocument>(`/workspace-documents/${documentId}`);
    return response.data;
}

export async function updateWorkspaceDocument(
    documentId: string,
    payload: UpdateWorkspaceDocumentPayload,
): Promise<WorkspaceDocument> {
    const response = await api.patch<WorkspaceDocument>(`/workspace-documents/${documentId}`, payload);
    return response.data;
}

export async function deleteWorkspaceDocument(documentId: string): Promise<void> {
    await api.delete(`/workspace-documents/${documentId}`);
}

export async function listWorkspaceDocumentCollaborators(
    documentId: string,
): Promise<WorkspaceDocumentCollaborator[]> {
    const response = await api.get<WorkspaceDocumentCollaborator[]>(
        `/workspace-documents/${documentId}/collaborators`,
    );
    return response.data;
}

export async function addWorkspaceDocumentCollaborator(
    documentId: string,
    payload: { user_id: string; permission: DocumentPermission },
): Promise<WorkspaceDocumentCollaborator> {
    const response = await api.post<WorkspaceDocumentCollaborator>(
        `/workspace-documents/${documentId}/collaborators`,
        payload,
    );
    return response.data;
}

export async function removeWorkspaceDocumentCollaborator(
    documentId: string,
    userId: string,
): Promise<void> {
    await api.delete(`/workspace-documents/${documentId}/collaborators/${userId}`);
}

export async function listWorkspaceDocumentRevisions(
    documentId: string,
): Promise<WorkspaceDocumentRevision[]> {
    const response = await api.get<WorkspaceDocumentRevision[]>(
        `/workspace-documents/${documentId}/revisions`,
    );
    return response.data;
}

export async function downloadWorkspaceDocument(
    documentId: string,
    format: DocumentExportFormat,
    title: string,
): Promise<void> {
    const response = await api.get<Blob>(`/workspace-documents/${documentId}/export/${format}`, {
        responseType: "blob",
    });
    const safeTitle = title.replace(/[^a-zA-Z0-9 _-]+/g, "_").trim() || "letter";
    const url = URL.createObjectURL(response.data);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = `${safeTitle}.${format}`;
    window.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
}

export async function publishWorkspaceDocument(
    documentId: string,
    payload: {
        format: DocumentExportFormat;
        visibility?: DocumentVisibility;
        file_name?: string;
        is_confidential?: boolean;
    },
): Promise<PublishedWorkspaceDocument> {
    const response = await api.post<PublishedWorkspaceDocument>(
        `/workspace-documents/${documentId}/publish`,
        payload,
    );
    return response.data;
}

export async function listWorkspaceDocumentAssets(
    kind?: "logo" | "signature",
): Promise<import("@/types/workspaceDocuments").WorkspaceDocumentAsset[]> {
    const response = await api.get<import("@/types/workspaceDocuments").WorkspaceDocumentAsset[]>(
        "/workspace-documents/assets",
        { params: kind ? { kind } : undefined },
    );
    return response.data;
}

async function uploadWorkspaceDocumentAsset(
    kind: "logo" | "signature",
    file: File,
    label: string,
    makeDefault = true,
): Promise<import("@/types/workspaceDocuments").WorkspaceDocumentAsset> {
    const form = new FormData();
    form.append("file", file);
    form.append("label", label);
    form.append("make_default", String(makeDefault));
    const response = await api.post<import("@/types/workspaceDocuments").WorkspaceDocumentAsset>(
        `/workspace-documents/assets/${kind}`,
        form,
    );
    return response.data;
}

export function uploadWorkspaceLogo(file: File, label = "My logo", makeDefault = true) {
    return uploadWorkspaceDocumentAsset("logo", file, label, makeDefault);
}

export function uploadWorkspaceSignature(file: File, label = "My signature", makeDefault = true) {
    return uploadWorkspaceDocumentAsset("signature", file, label, makeDefault);
}

export async function deleteWorkspaceDocumentAsset(assetId: string): Promise<void> {
    await api.delete(`/workspace-documents/assets/${assetId}`);
}

export async function getWorkspaceAssetObjectUrl(assetId: string): Promise<string> {
    const response = await api.get<Blob>(`/workspace-documents/assets/${assetId}/content`, {
        responseType: "blob",
    });
    return URL.createObjectURL(response.data);
}

export async function getDocumentBrandLogoObjectUrl(documentId: string): Promise<string> {
    const response = await api.get<Blob>(`/workspace-documents/${documentId}/brand-logo/content`, {
        responseType: "blob",
    });
    return URL.createObjectURL(response.data);
}

export async function listWorkspaceDocumentSignatures(
    documentId: string,
): Promise<import("@/types/workspaceDocuments").WorkspaceDocumentSignature[]> {
    const response = await api.get<import("@/types/workspaceDocuments").WorkspaceDocumentSignature[]>(
        `/workspace-documents/${documentId}/signatures`,
    );
    return response.data;
}

export async function applyWorkspaceDocumentSignature(
    documentId: string,
    payload: {
        field_id: string;
        method: import("@/types/workspaceDocuments").DocumentSignatureMethod;
        asset_id?: string | null;
        consent_text: string;
    },
): Promise<import("@/types/workspaceDocuments").WorkspaceDocumentSignature> {
    const response = await api.post<import("@/types/workspaceDocuments").WorkspaceDocumentSignature>(
        `/workspace-documents/${documentId}/signatures`,
        payload,
    );
    return response.data;
}

export async function revokeWorkspaceDocumentSignature(
    documentId: string,
    fieldId: string,
): Promise<void> {
    await api.delete(`/workspace-documents/${documentId}/signatures/${encodeURIComponent(fieldId)}`);
}

export async function getDocumentSignatureObjectUrl(
    documentId: string,
    assetId: string,
): Promise<string> {
    const response = await api.get<Blob>(
        `/workspace-documents/${documentId}/signature-assets/${assetId}/content`,
        { responseType: "blob" },
    );
    return URL.createObjectURL(response.data);
}

export async function openWorkspaceDocumentPrintView(documentId: string): Promise<void> {
    const response = await api.get<Blob>(`/workspace-documents/${documentId}/export/pdf`, {
        responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const popup = window.open(url, "_blank", "noopener,noreferrer");
    if (!popup) {
        URL.revokeObjectURL(url);
        throw new Error("Allow pop-ups to open the print-ready PDF.");
    }
    window.setTimeout(() => URL.revokeObjectURL(url), 120_000);
}

export type WorkspaceDocumentFolder = {
    id: string;
    name: string;
    parent_id: string | null;
    owner_user_id: string;
    owner_display_name: string;
    can_manage: boolean;
    is_personal: boolean;
    document_count: number;
    child_count: number;
};

export type WorkspaceOfficeAccess = {
    is_company_owner: boolean;
    company_id: string | null;
    role: string;
};

export type WorkspaceSharingDirectoryUser = {
    user_id: string;
    display_name: string;
    email: string | null;
    phone: string | null;
    role: string;
};

export type PersonalFolderResult = {
    folder_id: string | null;
    name: string | null;
    moved_count: number;
};

export type ImportedWorkspaceDocument = {
    id: string;
    reference: string;
    title: string;
    folder_id: string | null;
    source_type: "docx" | "pdf";
    warning: string | null;
};

export async function getWorkspaceOfficeAccess(): Promise<WorkspaceOfficeAccess> {
    const response = await api.get<WorkspaceOfficeAccess>("/workspace-office/access");
    return response.data;
}

export async function listWorkspaceDocumentFolders(
    kind: WorkspaceItemKind = "document",
): Promise<WorkspaceDocumentFolder[]> {
    const response = await api.get<WorkspaceDocumentFolder[]>("/workspace-office/folders", {
        params: { kind },
    });
    return response.data;
}

export async function createWorkspaceDocumentFolder(
    name: string,
    parentId?: string | null,
): Promise<WorkspaceDocumentFolder> {
    const response = await api.post<WorkspaceDocumentFolder>("/workspace-documents/folders", {
        name,
        parent_id: parentId ?? null,
    });
    // The legacy mutation response does not include governance metadata. Reload
    // through /workspace-office/folders after creation instead of relying on it.
    return {
        ...response.data,
        owner_user_id: response.data.owner_user_id ?? "",
        owner_display_name: response.data.owner_display_name ?? "",
        can_manage: true,
        is_personal: false,
    };
}

export async function renameWorkspaceDocumentFolder(
    folderId: string,
    name: string,
): Promise<WorkspaceDocumentFolder> {
    const response = await api.patch<WorkspaceDocumentFolder>(
        `/workspace-documents/folders/${folderId}`,
        { name },
    );
    return {
        ...response.data,
        owner_user_id: response.data.owner_user_id ?? "",
        owner_display_name: response.data.owner_display_name ?? "",
        can_manage: true,
        is_personal: false,
    };
}

export async function deleteWorkspaceDocumentFolder(folderId: string): Promise<void> {
    await api.delete(`/workspace-documents/folders/${folderId}`);
}

export async function listWorkspaceDocumentFolderAssignments(
    kind: WorkspaceItemKind = "document",
): Promise<Record<string, string>> {
    const response = await api.get<Record<string, string>>("/workspace-office/folder-assignments", {
        params: { kind },
    });
    return response.data;
}

export async function moveWorkspaceDocumentToFolder(
    documentId: string,
    folderId: string | null,
): Promise<void> {
    await api.patch(`/workspace-documents/${documentId}/folder`, { folder_id: folderId });
}

export async function fileMyUnassignedWorkspaceItems(
    kind: WorkspaceItemKind = "all",
): Promise<PersonalFolderResult> {
    const response = await api.post<PersonalFolderResult>("/workspace-office/file-my-unassigned", null, {
        params: { kind },
    });
    return response.data;
}

export async function fileWorkspaceItemToPersonalFolder(
    documentId: string,
): Promise<PersonalFolderResult> {
    const response = await api.post<PersonalFolderResult>(
        `/workspace-office/items/${documentId}/personal-folder`,
    );
    return response.data;
}

export async function listWorkspaceSharingDirectory(): Promise<WorkspaceSharingDirectoryUser[]> {
    const response = await api.get<WorkspaceSharingDirectoryUser[]>("/workspace-office/sharing-directory");
    return response.data;
}

export async function importWorkspaceDocument(
    file: File,
    options?: { folderId?: string | null; visibility?: DocumentVisibility },
): Promise<ImportedWorkspaceDocument> {
    const form = new FormData();
    form.append("file", file);
    if (options?.folderId) form.append("folder_id", options.folderId);
    form.append("visibility", options?.visibility ?? "private");
    const response = await api.post<ImportedWorkspaceDocument>("/workspace-documents/import", form);
    if (!options?.folderId) await autoFileWorkspaceItem(response.data.id);
    return response.data;
}
