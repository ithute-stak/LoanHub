import { api } from "@/lib/api";
import type {
    LoanOffer,
    LoanOfferCreatePayload,
    LoanOfferUpdatePayload,
} from "@/types/loan_offer";

export async function listOffersByRequest(requestId: string): Promise<LoanOffer[]> {
    const response = await api.get<LoanOffer[]>(
        `/loan-offers/request/${requestId}`,
    );
    return response.data;
}

export async function createLoanOffer(
    payload: LoanOfferCreatePayload,
): Promise<LoanOffer> {
    const response = await api.post<LoanOffer>("/loan-offers/", payload);
    return response.data;
}

export async function updateLoanOffer(
    offerId: string,
    payload: Omit<LoanOfferUpdatePayload, "id">,
): Promise<LoanOffer> {
    const response = await api.patch<LoanOffer>(
        `/loan-offers/${offerId}`,
        payload,
    );
    return response.data;
}

export async function withdrawLoanOffer(offerId: string): Promise<LoanOffer> {
    const response = await api.post<LoanOffer>(`/loan-offers/${offerId}/withdraw`);
    return response.data;
}
