import { api } from "@/lib/api";
import type { ExternalFileShare, ManagedFile, ManagedFileList } from "@/types/files";

export async function listManagedFiles(params?: {
    search?: string;
    category?: string;
    skip?: number;
    limit?: number;
}): Promise<ManagedFileList> {
    const response = await api.get<ManagedFileList>("/files", { params });
    return response.data;
}

export async function uploadManagedFile(payload: {
    file: File;
    category: string;
    visibility: string;
    description?: string;
    isConfidential?: boolean;
    linkedEntityType?: string;
    linkedEntityId?: string;
}): Promise<ManagedFile> {
    const form = new FormData();
    form.append("file", payload.file);
    form.append("category", payload.category);
    form.append("visibility", payload.visibility);
    if (payload.description) form.append("description", payload.description);
    if (payload.linkedEntityType) form.append("linked_entity_type", payload.linkedEntityType);
    if (payload.linkedEntityId) form.append("linked_entity_id", payload.linkedEntityId);
    form.append("is_confidential", String(Boolean(payload.isConfidential)));

    const response = await api.post<ManagedFile>("/files/upload", form);
    return response.data;
}

export async function deleteManagedFile(fileId: string): Promise<void> {
    await api.delete(`/files/${fileId}`);
}

export async function downloadManagedFile(file: ManagedFile): Promise<void> {
    const response = await api.get<Blob>(`/files/${file.id}/download`, {
        responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = file.original_name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
}


export async function createExternalFileShare(
    fileId: string,
    payload: { expires_in_hours?: number; label?: string; allow_download?: boolean },
): Promise<ExternalFileShare> {
    const response = await api.post<ExternalFileShare>(`/files/${fileId}/external-shares`, payload);
    return response.data;
}

export async function listExternalFileShares(fileId: string): Promise<ExternalFileShare[]> {
    const response = await api.get<ExternalFileShare[]>(`/files/${fileId}/external-shares`);
    return response.data;
}

export async function revokeExternalFileShare(fileId: string, shareId: string): Promise<void> {
    await api.delete(`/files/${fileId}/external-shares/${shareId}`);
}
