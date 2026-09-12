import { api } from "@/lib/api";
import type { InstitutionType } from "@/store/slices/companiesSlice";
import type { UserRole } from "@/types/auth";

export type InstitutionGovernanceProfile = {
    id: string;
    company_id: string;
    regulator_name: string | null;
    regulatory_license_category: string | null;
    license_expiry_date: string | null;
    bank_code: string | null;
    swift_bic: string | null;
    aml_cft_officer_name: string | null;
    aml_cft_officer_email: string | null;
    data_protection_officer_name: string | null;
    data_protection_officer_email: string | null;
    regulatory_reporting_contact_email: string | null;
    complaints_contact: string | null;
    privacy_notice_url: string | null;
    data_retention_months: number;
    consent_management_enabled: boolean;
    data_export_enabled: boolean;
    ai_decisioning_enabled: boolean;
    ai_human_review_required: boolean;
    ai_explainability_required: boolean;
    ai_bias_monitoring_enabled: boolean;
    govstack_interoperability_status: "not_started" | "planned" | "in_progress" | "ready";
    dpg_readiness_status: "not_started" | "assessment" | "remediation" | "ready_for_review";
    open_api_published: boolean;
    low_bandwidth_supported: boolean;
    accessibility_reviewed: boolean;
    english_sesotho_supported: boolean;
    business_continuity_tested: boolean;
    incident_response_tested: boolean;
    interoperability_notes: string | null;
    created_at: string;
    updated_at: string;
};

export type InstitutionGovernanceUpdate = Partial<Omit<
    InstitutionGovernanceProfile,
    "id" | "company_id" | "created_at" | "updated_at"
>>;

export type ReadinessControl = {
    key: string;
    category: string;
    label: string;
    state: "complete" | "attention" | "not_applicable";
    required: boolean;
    detail: string;
};

export type InstitutionReadiness = {
    company_id: string;
    institution_type: InstitutionType;
    score_percent: number;
    completed_required_controls: number;
    required_controls: number;
    controls: ReadinessControl[];
    assigned_roles: UserRole[];
    missing_recommended_roles: UserRole[];
};

export type InstitutionRole = {
    role: UserRole;
    label: string;
    scope: "institution" | "branch" | "institution_or_branch";
    purpose: string;
};

export type GovStackCapability = {
    key: string;
    label: string;
    status: "implemented" | "integration_ready" | "planned";
    implementation: string;
};

function oversightConfig(companyId?: string) {
    return companyId ? { params: { company_id: companyId } } : undefined;
}

export async function getInstitutionGovernanceProfile(
    companyId?: string,
): Promise<InstitutionGovernanceProfile> {
    const response = await api.get<InstitutionGovernanceProfile>(
        "/institution-governance/profile",
        oversightConfig(companyId),
    );
    return response.data;
}

export async function updateInstitutionGovernanceProfile(
    payload: InstitutionGovernanceUpdate,
    companyId?: string,
): Promise<InstitutionGovernanceProfile> {
    const response = await api.put<InstitutionGovernanceProfile>(
        "/institution-governance/profile",
        payload,
        oversightConfig(companyId),
    );
    return response.data;
}

export async function getInstitutionReadiness(
    companyId?: string,
): Promise<InstitutionReadiness> {
    const response = await api.get<InstitutionReadiness>(
        "/institution-governance/readiness",
        oversightConfig(companyId),
    );
    return response.data;
}

export async function getInstitutionRoles(): Promise<InstitutionRole[]> {
    const response = await api.get<InstitutionRole[]>("/institution-governance/roles");
    return response.data;
}

export async function getGovStackCapabilities(): Promise<GovStackCapability[]> {
    const response = await api.get<GovStackCapability[]>(
        "/institution-governance/govstack-capabilities",
    );
    return response.data;
}
