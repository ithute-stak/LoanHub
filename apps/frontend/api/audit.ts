import { api } from "@/lib/api";
import type {
    AuditLogListResponse,
} from "@/types/audit";

export async function listAuditEvents(params?: {
    page?: number;
    page_size?: number;
    action?: string;
    entity_type?: string;
    search?: string;
}): Promise<AuditLogListResponse> {
    const response = await api.get<AuditLogListResponse>(
        "/audit/events",
        { params },
    );
    return response.data;
}
