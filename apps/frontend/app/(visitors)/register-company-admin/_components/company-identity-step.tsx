"use client";

import type {
    CompanyRegistrationModel,
} from "../_hooks/use-company-registration";
import {
    TextField,
} from "./form-field";
import {
    StepHeading,
} from "./step-heading";

type Props = Pick<
    CompanyRegistrationModel,
    "form" | "errors" | "updateField"
>;

export function CompanyIdentityStep({
    form,
    errors,
    updateField,
}: Props) {
    return (
        <section>
            <StepHeading
                eyebrow="Step 1"
                title="Tell us about the company"
                description="Enter the legal identity and primary contact number of the lending business."
            />

            <div className="grid gap-5 md:grid-cols-2">
                <div className="md:col-span-2">
                    <TextField
                        label="Registered company name"
                        name="company_name"
                        value={form.company_name}
                        onChange={(value) =>
                            updateField(
                                "company_name",
                                value,
                            )
                        }
                        error={errors.company_name}
                        placeholder="Example Finance (Pty) Ltd"
                        autoComplete="organization"
                        required
                    />
                </div>

                <TextField
                    label="Registration number"
                    name="registration_number"
                    value={
                        form.registration_number
                    }
                    onChange={(value) =>
                        updateField(
                            "registration_number",
                            value,
                        )
                    }
                    error={
                        errors.registration_number
                    }
                    placeholder="Optional during early onboarding"
                    hint="The official company registration number."
                />

                <TextField
                    label="Lending licence number"
                    name="license_number"
                    value={form.license_number}
                    onChange={(value) =>
                        updateField(
                            "license_number",
                            value,
                        )
                    }
                    error={errors.license_number}
                    placeholder="Optional if verification is pending"
                    hint="The licence or regulator reference used for lending."
                />

                <div className="md:col-span-2">
                    <TextField
                        label="Company phone number"
                        name="company_phone"
                        value={form.company_phone}
                        onChange={(value) =>
                            updateField(
                                "company_phone",
                                value,
                            )
                        }
                        error={errors.company_phone}
                        placeholder="+266 5800 0000"
                        autoComplete="tel"
                        required
                    />
                </div>
            </div>
        </section>
    );
}
