import type {
    CompanyRegistrationForm,
    RegistrationStep,
} from "../_types/company-registration";

export const COMPANY_REGISTRATION_DRAFT_KEY =
    "loanhub-company-registration-draft-v1";

export const DISTRICTS = [
    "Berea",
    "Butha-Buthe",
    "Leribe",
    "Mafeteng",
    "Maseru",
    "Mohale's Hoek",
    "Mokhotlong",
    "Qacha's Nek",
    "Quthing",
    "Thaba-Tseka",
] as const;

export const REGISTRATION_STEPS: RegistrationStep[] = [
    {
        id: "company",
        title: "Company identity",
        shortTitle: "Company",
        description:
            "Tell us about the registered lending business.",
    },
    {
        id: "operations",
        title: "Operations and contact",
        shortTitle: "Operations",
        description:
            "Add the company location and official contacts.",
    },
    {
        id: "owner",
        title: "Company owner",
        shortTitle: "Owner",
        description:
            "Create the first company-owner account.",
    },
    {
        id: "review",
        title: "Review and submit",
        shortTitle: "Review",
        description:
            "Confirm the application before submission.",
    },
];

export const INITIAL_COMPANY_REGISTRATION_FORM:
    CompanyRegistrationForm = {
        company_name: "",
        registration_number: "",
        license_number: "",
        company_phone: "",
        company_email: "",
        website: "",
        address: "",
        district: "Maseru",

        owner_email: "",
        owner_phone: "",
        password: "",
        confirm_password: "",

        first_name: "",
        middle_name: "",
        last_name: "",
        national_id: "",
        town_or_village: "",
        physical_address: "",

        accept_terms: false,
    };
