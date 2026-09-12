import type {
    CompanyRegistrationErrors,
    CompanyRegistrationForm,
    RegistrationStepId,
} from "../_types/company-registration";

const EMAIL_PATTERN =
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const PHONE_PATTERN =
    /^[+]?[\d\s()-]{8,20}$/;

function isValidUrl(value: string): boolean {
    try {
        const parsed = new URL(value);

        return (
            parsed.protocol === "http:" ||
            parsed.protocol === "https:"
        );
    } catch {
        return false;
    }
}

export function validateRegistrationStep(
    step: RegistrationStepId,
    form: CompanyRegistrationForm,
): CompanyRegistrationErrors {
    const errors: CompanyRegistrationErrors = {};

    if (step === "company") {
        if (!form.company_name.trim()) {
            errors.company_name =
                "Company name is required.";
        }

        if (!form.company_phone.trim()) {
            errors.company_phone =
                "Company phone number is required.";
        } else if (
            !PHONE_PATTERN.test(
                form.company_phone.trim(),
            )
        ) {
            errors.company_phone =
                "Enter a valid company phone number.";
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
                "License number is too short.";
        }
    }

    if (step === "operations") {
        if (!form.district.trim()) {
            errors.district =
                "Select the company district.";
        }

        if (!form.address.trim()) {
            errors.address =
                "Company physical address is required.";
        }

        if (
            form.company_email.trim() &&
            !EMAIL_PATTERN.test(
                form.company_email.trim(),
            )
        ) {
            errors.company_email =
                "Enter a valid company email address.";
        }

        if (
            form.website.trim() &&
            !isValidUrl(form.website.trim())
        ) {
            errors.website =
                "Enter a complete website URL, for example https://company.co.ls.";
        }
    }

    if (step === "owner") {
        if (!form.first_name.trim()) {
            errors.first_name =
                "First name is required.";
        }

        if (!form.last_name.trim()) {
            errors.last_name =
                "Last name is required.";
        }

        if (!form.owner_phone.trim()) {
            errors.owner_phone =
                "Owner phone number is required.";
        } else if (
            !PHONE_PATTERN.test(
                form.owner_phone.trim(),
            )
        ) {
            errors.owner_phone =
                "Enter a valid owner phone number.";
        }

        if (
            form.owner_email.trim() &&
            !EMAIL_PATTERN.test(
                form.owner_email.trim(),
            )
        ) {
            errors.owner_email =
                "Enter a valid owner email address.";
        }

        if (!form.town_or_village.trim()) {
            errors.town_or_village =
                "Town or village is required.";
        }

        if (!form.physical_address.trim()) {
            errors.physical_address =
                "Owner physical address is required.";
        }

        if (form.password.length < 8) {
            errors.password =
                "Password must contain at least 8 characters.";
        }

        if (
            form.password !==
            form.confirm_password
        ) {
            errors.confirm_password =
                "Passwords do not match.";
        }
    }

    if (step === "review") {
        if (!form.accept_terms) {
            errors.accept_terms =
                "You must confirm the declaration before submitting.";
        }
    }

    return errors;
}

export function hasValidationErrors(
    errors: CompanyRegistrationErrors,
): boolean {
    return Object.keys(errors).length > 0;
}
