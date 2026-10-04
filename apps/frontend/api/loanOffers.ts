import { api } from "@/lib/api";
import type {
    LoanOffer,
    LoanOfferCreatePayload,
    LoanOfferUpdatePayload,
    QuickLoanAffordabilityPreviewResult,
} from "@/types/loan_offer";

export async function listOffersByRequest(requestId: string): Promise<LoanOffer[]> {
    const response = await api.get<LoanOffer[]>(
        `/loan-offers/request/${requestId}`,
    );
    return response.data;
}

export async function previewQuickLoanAffordability(
    payload: LoanOfferCreatePayload,
): Promise<QuickLoanAffordabilityPreviewResult> {
    const response = await api.post<QuickLoanAffordabilityPreviewResult>(
        "/loan-offers/quick-affordability-preview",
        {
            loan_request_id: payload.loan_request_id,
            approved_amount: payload.approved_amount,
            term_months: payload.term_months,
            interest_rate_percent: payload.interest_rate_percent ?? 0,
            processing_fee: payload.processing_fee ?? 0,
            calculation_method: payload.calculation_method,
            installment_due_dates: payload.installment_due_dates,
        },
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
