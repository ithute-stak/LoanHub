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

export function CompanyOwnerStep({
    form,
    errors,
    updateField,
}: Props) {
    return (
        <section>
            <StepHeading
                eyebrow="Step 3"
                title="Create the company-owner account"
                description="This person becomes the first administrator and receives company-wide permissions after approval."
            />

            <div className="grid gap-5 md:grid-cols-2">
                <TextField
                    label="First name"
                    name="first_name"
                    value={form.first_name}
                    onChange={(value) =>
                        updateField(
                            "first_name",
                            value,
                        )
                    }
                    error={errors.first_name}
                    autoComplete="given-name"
                    required
                />

                <TextField
                    label="Middle name"
                    name="middle_name"
                    value={form.middle_name}
                    onChange={(value) =>
                        updateField(
                            "middle_name",
                            value,
                        )
                    }
                    error={errors.middle_name}
                    autoComplete="additional-name"
                />

                <TextField
                    label="Last name"
                    name="last_name"
                    value={form.last_name}
                    onChange={(value) =>
                        updateField(
                            "last_name",
                            value,
                        )
                    }
                    error={errors.last_name}
                    autoComplete="family-name"
                    required
                />

                <TextField
                    label="National ID"
                    name="national_id"
                    value={form.national_id}
                    onChange={(value) =>
                        updateField(
                            "national_id",
                            value,
                        )
                    }
                    error={errors.national_id}
                    placeholder="Optional during early onboarding"
                />

                <TextField
                    label="Owner phone"
                    name="owner_phone"
                    value={form.owner_phone}
                    onChange={(value) =>
                        updateField(
                            "owner_phone",
                            value,
                        )
                    }
                    error={errors.owner_phone}
                    placeholder="+266 5800 0000"
                    autoComplete="tel"
                    required
                />

                <TextField
                    label="Owner email"
                    name="owner_email"
                    type="email"
                    value={form.owner_email}
                    onChange={(value) =>
                        updateField(
                            "owner_email",
                            value,
                        )
                    }
                    error={errors.owner_email}
                    placeholder="owner@example.com"
                    autoComplete="email"
                />

                <TextField
                    label="Town or village"
                    name="town_or_village"
                    value={form.town_or_village}
                    onChange={(value) =>
                        updateField(
                            "town_or_village",
                            value,
                        )
                    }
                    error={errors.town_or_village}
                    required
                />

                <TextField
                    label="Owner physical address"
                    name="physical_address"
                    value={form.physical_address}
                    onChange={(value) =>
                        updateField(
                            "physical_address",
                            value,
                        )
                    }
                    error={
                        errors.physical_address
                    }
                    autoComplete="street-address"
                    required
                />

                <TextField
                    label="Password"
                    name="password"
                    type="password"
                    value={form.password}
                    onChange={(value) =>
                        updateField(
                            "password",
                            value,
                        )
                    }
                    error={errors.password}
                    hint="Use at least 8 characters. A longer passphrase is recommended."
                    autoComplete="new-password"
                    minLength={8}
                    required
                />

                <TextField
                    label="Confirm password"
                    name="confirm_password"
                    type="password"
                    value={
                        form.confirm_password
                    }
                    onChange={(value) =>
                        updateField(
                            "confirm_password",
                            value,
                        )
                    }
                    error={
                        errors.confirm_password
                    }
                    autoComplete="new-password"
                    minLength={8}
                    required
                />
            </div>
        </section>
    );
}
