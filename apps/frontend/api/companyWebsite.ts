import { api } from "@/lib/api";
import type {
    CompanyWebsiteProfile,
    CompanyWebsiteUpdate,
    PublicCompanyWebsite,
    PublicLoanProduct,
} from "@/types/companyWebsite";

export type CompanyWebsiteReadinessCheck = {
    key: string;
    label: string;
    passed: boolean;
    required: boolean;
    detail: string;
    weight: number;
};

export type CompanyWebsiteReadiness = {
    score: number;
    ready_to_publish: boolean;
    active_product_count: number;
    checks: CompanyWebsiteReadinessCheck[];
};

export async function getMyCompanyWebsite(): Promise<CompanyWebsiteProfile | null> {
    const response = await api.get<CompanyWebsiteProfile | null>("/company-websites/mine");
    return response.data;
}

export async function getCompanyWebsiteReadiness(): Promise<CompanyWebsiteReadiness> {
    const response = await api.get<CompanyWebsiteReadiness>("/company-websites/readiness");
    return response.data;
}

export async function getCompanyWebsiteLoanProducts(): Promise<PublicLoanProduct[]> {
    const response = await api.get<PublicLoanProduct[]>("/company-websites/loan-products");
    return response.data;
}

export async function startCompanyWebsite(): Promise<CompanyWebsiteProfile> {
    const response = await api.post<CompanyWebsiteProfile>("/company-websites/start");
    return response.data;
}

export async function updateCompanyWebsite(payload: CompanyWebsiteUpdate): Promise<CompanyWebsiteProfile> {
    const response = await api.patch<CompanyWebsiteProfile>("/company-websites/mine", payload);
    return response.data;
}

export async function publishCompanyWebsite(isPublished: boolean): Promise<CompanyWebsiteProfile> {
    const response = await api.post<CompanyWebsiteProfile>("/company-websites/publish", { is_published: isPublished });
    return response.data;
}

export async function getPublicCompanyWebsite(publicCode: string): Promise<PublicCompanyWebsite> {
    const response = await api.get<PublicCompanyWebsite>(`/company-websites/public/${encodeURIComponent(publicCode)}`);
    return response.data;
}