import { api } from "@/lib/api";
import type {
    LoanRequest,
    LoanRequestCreatePayload,
    LoanRequestUpdatePayload,
} from "@/types/loanRequest";
import type { Loan, PaymentResult } from "@/types/loan";
import type { PaymentMethod } from "@/types/expenseManagement";

export async function listAllLoanRequests(): Promise<LoanRequest[]> {
    const response = await api.get<LoanRequest[]>("/loan_requests/");
    return response.data;
}

export async function listMyLoanRequests(): Promise<LoanRequest[]> {
    const response = await api.get<LoanRequest[]>("/loan_requests/my");
    return response.data;
}

export async function createLoanRequest(
    payload: LoanRequestCreatePayload,
): Promise<LoanRequest> {
    const response = await api.post<LoanRequest>("/loan_requests/", payload);
    return response.data;
}

export async function updateLoanRequest(
    requestId: string,
    payload: LoanRequestUpdatePayload,
): Promise<LoanRequest> {
    const response = await api.patch<LoanRequest>(
        `/loan_requests/${requestId}`,
        payload,
    );
    return response.data;
}

export async function cancelLoanRequest(requestId: string): Promise<LoanRequest> {
    const response = await api.post<LoanRequest>(
        `/loan_requests/${requestId}/cancel`,
    );
    return response.data;
}

export async function acceptLoanOffer(
    requestId: string,
    offerId: string,
): Promise<Loan> {
    const response = await api.post<Loan>(
        `/loan_requests/${requestId}/offers/${offerId}/accept`,
    );
    return response.data;
}


export type RequestServiceFeePaymentPayload = {
    payment_method: PaymentMethod;
    proof_reference?: string | null;
    proof_url?: string | null;
    proof_notes?: string | null;
    notes?: string | null;
    idempotency_key?: string;
};

export async function recordServiceFeePayment(
    requestId: string,
    payload: RequestServiceFeePaymentPayload,
): Promise<PaymentResult> {
    const response = await api.post<PaymentResult>(`/loan_requests/${requestId}/service-fee-payment`, payload);
    return response.data;
}

export const recordCashServiceFee = recordServiceFeePayment;
