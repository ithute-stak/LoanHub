"use client";

import type {
    CompanyRegistrationModel,
} from "../_hooks/use-company-registration";
import {
    DISTRICTS,
} from "../_lib/registration-constants";
import {
    SelectField,
    TextField,
} from "./form-field";
import {
    StepHeading,
} from "./step-heading";

type Props = Pick<
    CompanyRegistrationModel,
    "form" | "errors" | "updateField"
>;

export function CompanyOperationsStep({
    form,
    errors,
    updateField,
}: Props) {
    return (
        <section>
            <StepHeading
                eyebrow="Step 2"
                title="Where does the company operate?"
                description="Add the official communication channels and the primary operating address."
            />

            <div className="grid gap-5 md:grid-cols-2">
                <TextField
                    label="Company email"
                    name="company_email"
                    type="email"
                    value={form.company_email}
                    onChange={(value) =>
                        updateField(
                            "company_email",
                            value,
                        )
                    }
                    error={errors.company_email}
                    placeholder="info@company.co.ls"
                    autoComplete="email"
                />

                <TextField
                    label="Company website"
                    name="website"
                    type="url"
                    value={form.website}
                    onChange={(value) =>
                        updateField(
                            "website",
                            value,
                        )
                    }
                    error={errors.website}
                    placeholder="https://company.co.ls"
                />

                <SelectField
                    label="Operating district"
                    name="district"
                    value={form.district}
                    onChange={(value) =>
                        updateField(
                            "district",
                            value,
                        )
                    }
                    options={DISTRICTS}
                    error={errors.district}
                    required
                />

                <TextField
                    label="Physical business address"
                    name="address"
                    value={form.address}
                    onChange={(value) =>
                        updateField(
                            "address",
                            value,
                        )
                    }
                    error={errors.address}
                    placeholder="Building, street and area"
                    autoComplete="street-address"
                    required
                />
            </div>
        </section>
    );
}
