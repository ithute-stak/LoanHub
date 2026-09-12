import { api } from "@/lib/api";
import type {
    MarketplaceRequestCard,
    MarketplaceEvidenceDocument,
    MarketplaceRequestDetail,
    MarketplaceUnlock,
    UnlockMarketplacePayload,
} from "@/types/marketplace";

export async function listMarketplaceRequests(): Promise<MarketplaceRequestCard[]> {
    const response = await api.get<MarketplaceRequestCard[]>("/marketplace/requests");
    return response.data;
}

export async function getMarketplaceRequest(
    requestId: string,
): Promise<MarketplaceRequestDetail> {
    const response = await api.get<MarketplaceRequestDetail>(
        `/marketplace/requests/${requestId}`,
    );
    return response.data;
}

export async function unlockMarketplaceRequest(
    requestId: string,
    payload: UnlockMarketplacePayload,
): Promise<MarketplaceUnlock> {
    const response = await api.post<MarketplaceUnlock>(
        `/marketplace/requests/${requestId}/unlock`,
        payload,
    );
    return response.data;
}

export async function downloadMarketplaceEvidence(
    document: MarketplaceEvidenceDocument,
): Promise<void> {
    const response = await api.get<Blob>(`/files/${document.id}/download`, {
        responseType: "blob",
    });
    const url = URL.createObjectURL(response.data);
    const anchor = window.document.createElement("a");
    anchor.href = url;
    anchor.download = document.original_name;
    window.document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
}
