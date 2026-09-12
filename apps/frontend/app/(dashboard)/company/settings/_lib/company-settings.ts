import type {
    CompanySettingsErrors,
    CompanySettingsForm,
} from "../_types/company-settings";

export const LESOTHO_DISTRICTS = [
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

export const EMPTY_COMPANY_FORM: CompanySettingsForm = {
    name: "",
    registration_number: "",
    license_number: "",
    phone: "",
    email: "",
    website: "",
    address: "",
    district: "",
    mpesa_shortcode: "",
};

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const PHONE_PATTERN = /^[+]?\d[\d\s()-]{6,19}$/;
const MPESA_SHORTCODE_PATTERN = /^\d{4,12}$/;

function isValidUrl(value: string): boolean {
    try {
        const url = new URL(value);
        return url.protocol === "http:" || url.protocol === "https:";
    } catch {
        return false;
    }
}

export function normalizeCompanyForm(
    form: CompanySettingsForm,
): CompanySettingsForm {
    return {
        name: form.name.trim(),
        registration_number: form.registration_number.trim(),
        license_number: form.license_number.trim(),
        phone: form.phone.trim(),
        email: form.email.trim(),
        website: form.website.trim(),
        address: form.address.trim(),
        district: form.district.trim(),
        mpesa_shortcode: form.mpesa_shortcode.trim(),
    };
}

export function validateCompanyForm(
    form: CompanySettingsForm,
): CompanySettingsErrors {
    const errors: CompanySettingsErrors = {};

    if (!form.name.trim()) {
        errors.name = "Company name is required.";
    }

    if (!form.phone.trim()) {
        errors.phone = "Company phone number is required.";
    } else if (!PHONE_PATTERN.test(form.phone.trim())) {
        errors.phone = "Enter a valid company phone number.";
    }

    if (form.email.trim() && !EMAIL_PATTERN.test(form.email.trim())) {
        errors.email = "Enter a valid company email address.";
    }

    if (form.website.trim() && !isValidUrl(form.website.trim())) {
        errors.website =
            "Enter a full URL, for example https://company.co.ls.";
    }

    if (
        form.registration_number.trim() &&
        form.registration_number.trim().length < 3
    ) {
        errors.registration_number =
            "Registration number is too short.";
    }

    if (
        form.license_number.trim() &&
        form.license_number.trim().length < 3
    ) {
        errors.license_number =
            "Licence number is too short.";
    }

    if (!form.district.trim()) {
        errors.district = "Select an operating district.";
    }

    if (!form.address.trim()) {
        errors.address = "Physical address is required.";
    }

    if (
        form.mpesa_shortcode.trim() &&
        !MPESA_SHORTCODE_PATTERN.test(form.mpesa_shortcode.trim())
    ) {
        errors.mpesa_shortcode = "Enter the 4 to 12 digit M-Pesa business shortcode.";
    }

    return errors;
}

export function calculateCompletion(
    form: CompanySettingsForm,
): number {
    const profileFields = [
        form.name,
        form.registration_number,
        form.license_number,
        form.phone,
        form.email,
        form.website,
        form.address,
        form.district,
    ];
    const completed = profileFields.filter((value) => value.trim()).length;
    return Math.round((completed / profileFields.length) * 100);
}
