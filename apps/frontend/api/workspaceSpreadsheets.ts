import { api } from "@/lib/api";
import { fileWorkspaceItemToPersonalFolder } from "@/api/workspaceDocuments";
import type { DocumentVisibility, WorkspaceDocument } from "@/types/workspaceDocuments";
import type {
    CreateWorkspaceSpreadsheetPayload,
    PublishWorkspaceSpreadsheetPayload,
    PublishedWorkspaceSpreadsheet,
    SaveWorkspaceSpreadsheetPayload,
    SpreadsheetExportFormat,
} from "@/types/workspaceSpreadsheets";

async function autoFileSpreadsheet(documentId: string): Promise<void> {
    try {
        await fileWorkspaceItemToPersonalFolder(documentId);
    } catch {
        // Spreadsheet creation/import succeeded. The Office organizer repairs
        // unassigned work when it next loads, so filing should not mask success.
    }
}

export async function createWorkspaceSpreadsheet(
    payload: CreateWorkspaceSpreadsheetPayload,
): Promise<WorkspaceDocument> {
    const response = await api.post<WorkspaceDocument>("/workspace-spreadsheets", payload);
    await autoFileSpreadsheet(response.data.id);
    return response.data;
}

export async function importWorkspaceSpreadsheet(
    file: File,
    options: {
        title?: string;
        visibility: DocumentVisibility;
        is_confidential?: boolean;
    },
): Promise<WorkspaceDocument> {
    const form = new FormData();
    form.append("file", file);
    if (options.title?.trim()) form.append("title", options.title.trim());
    form.append("visibility", options.visibility);
    form.append("is_confidential", String(Boolean(options.is_confidential)));
    const response = await api.post<WorkspaceDocument>("/workspace-spreadsheets/import", form);
    await autoFileSpreadsheet(response.data.id);
    return response.data;
}

export async function saveWorkspaceSpreadsheet(
    documentId: string,
    payload: SaveWorkspaceSpreadsheetPayload,
): Promise<WorkspaceDocument> {
    const response = await api.patch<WorkspaceDocument>(`/workspace-spreadsheets/${documentId}`, payload);
    return response.data;
}

export async function refreshWorkspaceSpreadsheetData(documentId: string): Promise<WorkspaceDocument> {
    const response = await api.post<WorkspaceDocument>(`/workspace-spreadsheets/${documentId}/refresh-loanhub-data`);
    return response.data;
}

export async function downloadWorkspaceSpreadsheet(
    documentId: string,
    format: SpreadsheetExportFormat,
    title: string,
): Promise<void> {
    const response = await api.get<Blob>(`/workspace-spreadsheets/${documentId}/export/${format}`, {
        responseType: "blob",
    });
    const safeTitle = title.replace(/[^a-zA-Z0-9 _-]+/g, "_").trim() || "workbook";
    const url = URL.createObjectURL(response.data);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = `${safeTitle}.${format}`;
    window.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
}

export async function publishWorkspaceSpreadsheet(
    documentId: string,
    payload: PublishWorkspaceSpreadsheetPayload,
): Promise<PublishedWorkspaceSpreadsheet> {
    const response = await api.post<PublishedWorkspaceSpreadsheet>(
        `/workspace-spreadsheets/${documentId}/publish`,
        payload,
    );
    return response.data;
}
