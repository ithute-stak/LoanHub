import { api } from "@/lib/api";
import type { PaymentTransaction } from "@/types/payment";

export async function listPayments(): Promise<PaymentTransaction[]> {
    const response = await api.get<PaymentTransaction[]>("/payments/");
    return response.data;
}

export async function getPayment(paymentId: string): Promise<PaymentTransaction> {
    const response = await api.get<PaymentTransaction>(`/payments/${paymentId}`);
    return response.data;
}
