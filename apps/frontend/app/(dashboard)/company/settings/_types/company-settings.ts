export type CompanySettingsForm = {
    name: string;
    registration_number: string;
    license_number: string;
    phone: string;
    email: string;
    website: string;
    address: string;
    district: string;
    mpesa_shortcode: string;
};

export type CompanySettingsField = keyof CompanySettingsForm;

export type CompanySettingsErrors = Partial<
    Record<CompanySettingsField | "form", string>
>;
