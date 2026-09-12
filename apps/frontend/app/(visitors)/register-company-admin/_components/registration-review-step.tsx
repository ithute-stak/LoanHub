"use client";


import { Input } from "@/components/ui/input";
import type {
    ReactNode,
} from "react";

import {
    Building2,
    MapPin,
    ShieldCheck,
    UserRound,
} from "lucide-react";

import type {
    CompanyRegistrationModel,
} from "../_hooks/use-company-registration";
import {
    StepHeading,
} from "./step-heading";

type Props = Pick<
    CompanyRegistrationModel,
    | "form"
    | "errors"
    | "ownerFullName"
    | "updateField"
>;

function ReviewCard({
    icon: Icon,
    title,
    children,
}: {
    icon: typeof Building2;
    title: string;
    children: ReactNode;
}) {
    return (
        <article className="rounded-2xl border bg-muted/20 p-4">
            <div className="flex items-center gap-2">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/10 text-primary">
                    <Icon className="h-4 w-4" />
                </div>

                <h3 className="font-black">
                    {title}
                </h3>
            </div>

            <div className="mt-4 space-y-2 text-sm">
                {children}
            </div>
        </article>
    );
}

function ReviewRow({
    label,
    value,
}: {
    label: string;
    value?: string | null;
}) {
    return (
        <div className="flex items-start justify-between gap-4">
            <span className="text-muted-foreground">
                {label}
            </span>

            <span className="max-w-[60%] text-right font-bold">
                {value?.trim() ||
                    "Not provided"}
            </span>
        </div>
    );
}

export function RegistrationReviewStep({
    form,
    errors,
    ownerFullName,
    updateField,
}: Props) {
    return (
        <section>
            <StepHeading
                eyebrow="Step 4"
                title="Review the application"
                description="Confirm that the company and owner information is correct before submission."
            />

            <div className="grid gap-4 xl:grid-cols-2">
                <ReviewCard
                    icon={Building2}
                    title="Company identity"
                >
                    <ReviewRow
                        label="Company"
                        value={form.company_name}
                    />

                    <ReviewRow
                        label="Registration"
                        value={
                            form.registration_number
                        }
                    />

                    <ReviewRow
                        label="Licence"
                        value={form.license_number}
                    />

                    <ReviewRow
                        label="Phone"
                        value={form.company_phone}
                    />
                </ReviewCard>

                <ReviewCard
                    icon={MapPin}
                    title="Operations"
                >
                    <ReviewRow
                        label="District"
                        value={form.district}
                    />

                    <ReviewRow
                        label="Address"
                        value={form.address}
                    />

                    <ReviewRow
                        label="Email"
                        value={form.company_email}
                    />

                    <ReviewRow
                        label="Website"
                        value={form.website}
                    />
                </ReviewCard>

                <ReviewCard
                    icon={UserRound}
                    title="Company owner"
                >
                    <ReviewRow
                        label="Name"
                        value={ownerFullName}
                    />

                    <ReviewRow
                        label="Phone"
                        value={form.owner_phone}
                    />

                    <ReviewRow
                        label="Email"
                        value={form.owner_email}
                    />

                    <ReviewRow
                        label="Town"
                        value={
                            form.town_or_village
                        }
                    />
                </ReviewCard>

                <ReviewCard
                    icon={ShieldCheck}
                    title="Approval process"
                >
                    <p className="leading-6 text-muted-foreground">
                        The company starts with a
                        pending status. LoanHub
                        administrators verify company
                        information before lending
                        features are activated.
                    </p>
                </ReviewCard>
            </div>

            <label className="mt-6 flex cursor-pointer items-start gap-3 rounded-2xl border border-primary/20 bg-primary/5 p-4">
                <Input
                    type="checkbox"
                    checked={form.accept_terms}
                    onChange={(event) =>
                        updateField(
                            "accept_terms",
                            event.target.checked,
                        )
                    }
                    className="mt-1 h-4 w-4 rounded border-primary accent-primary"
                />

                <span>
                    <span className="block text-sm font-black">
                        Application declaration
                    </span>

                    <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                        I confirm that the information
                        provided is accurate and that I
                        am authorised to register this
                        company on LoanHub.
                    </span>

                    {errors.accept_terms && (
                        <span className="mt-2 block text-xs font-semibold text-red-600 dark:text-red-400">
                            {errors.accept_terms}
                        </span>
                    )}
                </span>
            </label>
        </section>
    );
}
