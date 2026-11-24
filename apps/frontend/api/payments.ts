import { api } from "@/lib/api";
import type { PaymentTransaction } from "@/types/payment";

export async function listPayments(options?: { refresh?: boolean }): Promise<PaymentTransaction[]> {
    const response = await api.get<PaymentTransaction[]>("/payments/", {
        loanHubCache: options?.refresh ? { mode: "refresh" } : undefined,
    });
    return response.data;
}

export async function getPayment(paymentId: string): Promise<PaymentTransaction> {
    const response = await api.get<PaymentTransaction>(`/payments/${paymentId}`);
    return response.data;
}
