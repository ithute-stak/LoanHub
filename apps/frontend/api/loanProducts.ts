import { api } from "@/lib/api";
import type {
    LoanProduct,
    LoanProductCreatePayload,
    LoanProductUpdatePayload,
} from "@/types/loanProduct";

export async function listLoanProducts(): Promise<LoanProduct[]> {
    const response = await api.get<LoanProduct[]>("/loan-products/");
    return response.data;
}

export async function listPublicLoanProducts(
    companyId?: string,
): Promise<LoanProduct[]> {
    const response = await api.get<LoanProduct[]>("/loan-products/public", {
        params: companyId ? { company_id: companyId } : undefined,
    });
    return response.data;
}

export async function createLoanProduct(
    payload: LoanProductCreatePayload,
): Promise<LoanProduct> {
    const response = await api.post<LoanProduct>("/loan-products/", payload);
    return response.data;
}

export async function updateLoanProduct(
    productId: string,
    payload: LoanProductUpdatePayload,
): Promise<LoanProduct> {
    const response = await api.put<LoanProduct>(
        `/loan-products/${productId}`,
        payload,
    );
    return response.data;
}

export async function setLoanProductActive(
    productId: string,
    active: boolean,
): Promise<LoanProduct> {
    const response = active
        ? await api.patch<LoanProduct>(`/loan-products/${productId}/activate`)
        : await api.patch<LoanProduct>(`/loan-products/${productId}/deactivate`);
    return response.data;
}

export async function deleteLoanProduct(productId: string): Promise<void> {
    await api.delete(`/loan-products/${productId}`);
}
