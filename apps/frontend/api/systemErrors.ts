import { api } from "@/lib/api";
import type {
    SystemErrorListResponse,
    SystemErrorLog,
} from "@/types/systemError";

export async function listSystemErrors(params?: {
    page?: number;
    page_size?: number;
    unresolved_only?: boolean;
    severity?: string;
    search?: string;
}): Promise<SystemErrorListResponse> {
    const response = await api.get<SystemErrorListResponse>(
        "/system-errors",
        { params },
    );
    return response.data;
}

export async function resolveSystemError(
    errorId: string,
    resolutionNotes: string,
): Promise<SystemErrorLog> {
    const response = await api.patch<SystemErrorLog>(
        `/system-errors/${errorId}/resolve`,
        { resolution_notes: resolutionNotes },
    );
    return response.data;
}

export async function reopenSystemError(
    errorId: string,
): Promise<SystemErrorLog> {
    const response = await api.patch<SystemErrorLog>(
        `/system-errors/${errorId}/reopen`,
    );
    return response.data;
}
