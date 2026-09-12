export type RegistrationStepId =
    | "company"
    | "operations"
    | "owner"
    | "review";

export type CompanyRegistrationForm = {
    company_name: string;
    registration_number: string;
    license_number: string;
    company_phone: string;
    company_email: string;
    website: string;
    address: string;
    district: string;

    owner_email: string;
    owner_phone: string;
    password: string;
    confirm_password: string;

    first_name: string;
    middle_name: string;
    last_name: string;
    national_id: string;
    town_or_village: string;
    physical_address: string;

    accept_terms: boolean;
};

export type CompanyRegistrationField =
    keyof CompanyRegistrationForm;

export type CompanyRegistrationErrors =
    Partial<
        Record<
            CompanyRegistrationField | "form",
            string
        >
    >;

export type RegistrationStep = {
    id: RegistrationStepId;
    title: string;
    shortTitle: string;
    description: string;
};

export type CompanyRegistrationPayload = {
    company_name: string;
    registration_number: string | null;
    license_number: string | null;
    company_phone: string;
    company_email: string | null;
    website: string | null;
    address: string;
    district: string;

    owner_email: string | null;
    owner_phone: string;
    password: string;

    first_name: string;
    middle_name: string | null;
    last_name: string;
    national_id: string | null;
    nationality: "Mosotho";
    town_or_village: string;
    physical_address: string;
};
