export type CompanyWebsiteTemplate = "trust_community" | "modern_finance";

export type CompanyWebsiteProfile = {
    id: string;
    company_id: string;
    company_name: string;
    public_code: string;
    template_key: CompanyWebsiteTemplate;
    is_published: boolean;
    headline: string;
    subheadline: string | null;
    about: string | null;
    primary_color: string;
    accent_color: string;
    hero_badge: string | null;
    contact_phone: string | null;
    contact_email: string | null;
    show_loan_products: boolean;
    show_account_cta: boolean;
    custom_sections: Array<Record<string, unknown>>;
    published_at: string | null;
    created_at: string;
    updated_at: string | null;
};

export type CompanyWebsiteUpdate = Partial<Pick<
    CompanyWebsiteProfile,
    | "template_key"
    | "headline"
    | "subheadline"
    | "about"
    | "primary_color"
    | "accent_color"
    | "hero_badge"
    | "contact_phone"
    | "contact_email"
    | "show_loan_products"
    | "show_account_cta"
    | "custom_sections"
>>;

export type PublicLoanProduct = {
    id: string;
    name: string;
    description: string | null;
    min_amount: number;
    max_amount: number;
    min_term_months: number;
    max_term_months: number;
    interest_rate_percent: number;
    processing_fee: number;
};

export type PublicCompanyWebsite = {
    public_code: string;
    company_name: string;
    registration_number: string | null;
    license_number: string | null;
    company_phone: string | null;
    company_email: string | null;
    company_address: string | null;
    company_district: string | null;
    template_key: CompanyWebsiteTemplate;
    headline: string;
    subheadline: string | null;
    about: string | null;
    primary_color: string;
    accent_color: string;
    hero_badge: string | null;
    contact_phone: string | null;
    contact_email: string | null;
    show_loan_products: boolean;
    show_account_cta: boolean;
    custom_sections: Array<Record<string, unknown>>;
    loan_products: PublicLoanProduct[];
};
