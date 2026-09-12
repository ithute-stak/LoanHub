"use client";


import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect } from "@/components/ui/native-select";
import {
    AlertCircle,
    Building2,
    CheckCircle2,
    GitBranch,
    Loader2,
    Mail,
    MapPin,
    Phone,
    Save,
} from "lucide-react";
import {
    useState,
    type ChangeEvent,
    type FormEvent,
    type ReactNode,
} from "react";

import {
    CustomDialog,
} from "@/components/ui/custom-dialog";

import type {
    LoanCompany,
} from "@/store/slices/companiesSlice";

import type {
    Branch,
    BranchCreatePayload,
} from "@/types/branch";

import type {
    BranchDialogState,
} from "../_types/branch-page";

import {
    createBranchFormValues,
    getRequestError,
    LESOTHO_DISTRICTS,
    toBranchPayload,
    validateBranchForm,
    type BranchFormErrors,
    type BranchFormValues,
} from "../_lib/branch-utils";

type Props = {
    state: BranchDialogState | null;
    companies: LoanCompany[];

    onOpenChange: (
        open: boolean,
    ) => void;

    onSubmit: (args: {
        mode: "create" | "edit";
        branch: Branch | null;
        payload: BranchCreatePayload;
    }) => Promise<void>;
};

const fieldClassName = [
    "h-11 w-full rounded-xl border bg-background px-3 text-sm",
    "outline-none transition placeholder:text-muted-foreground",
    "focus:border-primary focus:ring-2 focus:ring-primary/20",
    "disabled:cursor-not-allowed disabled:opacity-60",
].join(" ");

function FieldLabel({
    children,
    required = false,
}: {
    children: ReactNode;
    required?: boolean;
}) {
    return (
        <span className="mb-1.5 block text-sm font-bold">
            {children}

            {required && (
                <span className="text-red-500">
                    {" "}
                    *
                </span>
            )}
        </span>
    );
}

function FieldError({
    message,
}: {
    message?: string;
}) {
    if (!message) {
        return null;
    }

    return (
        <p className="mt-1.5 flex items-center gap-1 text-xs font-medium text-red-600">
            <AlertCircle className="h-3.5 w-3.5" />
            {message}
        </p>
    );
}

function SectionHeading({
    icon,
    title,
    description,
}: {
    icon: ReactNode;
    title: string;
    description: string;
}) {
    return (
        <div className="mb-5 flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                {icon}
            </div>

            <div>
                <h3 className="font-black">
                    {title}
                </h3>

                <p className="mt-0.5 text-xs text-muted-foreground">
                    {description}
                </p>
            </div>
        </div>
    );
}

function BranchFormDialogContent({
    state,
    companies,
    onOpenChange,
    onSubmit,
}: {
    state: BranchDialogState;
    companies: LoanCompany[];
    onOpenChange: (
        open: boolean,
    ) => void;
    onSubmit: Props["onSubmit"];
}) {
    const [values, setValues] =
        useState<BranchFormValues>(() =>
            createBranchFormValues(
                state.branch,
            ),
        );

    const [errors, setErrors] =
        useState<BranchFormErrors>({});

    const [
        requestError,
        setRequestError,
    ] = useState<string | null>(null);

    const [submitting, setSubmitting] =
        useState(false);

    const title =
        state.mode === "create"
            ? "Create company branch"
            : `Edit ${state.branch?.name ?? "branch"}`;

    function handleChange(
        event: ChangeEvent<
            | HTMLInputElement
            | HTMLSelectElement
            | HTMLTextAreaElement
        >,
    ) {
        const target = event.target;

        if (
            target instanceof HTMLInputElement &&
            target.type === "checkbox"
        ) {
            setValues((current) => ({
                ...current,
                is_active: target.checked,
            }));

            setErrors((current) => ({
                ...current,
                is_active: undefined,
            }));

            setRequestError(null);
            return;
        }

        const field =
            target.name as Exclude<
                keyof BranchFormValues,
                "is_active"
            >;

        setValues((current) => ({
            ...current,
            [field]: target.value,
        }));

        setErrors((current) => ({
            ...current,
            [field]: undefined,
        }));

        setRequestError(null);
    }

    async function handleSubmit(
        event: FormEvent<HTMLFormElement>,
    ) {
        event.preventDefault();

        const validationErrors =
            validateBranchForm(values);

        setErrors(
            validationErrors,
        );

        if (
            Object.keys(
                validationErrors,
            ).length > 0
        ) {
            return;
        }

        setSubmitting(true);
        setRequestError(null);

        try {
            await onSubmit({
                mode: state.mode,
                branch: state.branch,
                payload:
                    toBranchPayload(
                        values,
                    ),
            });
        } catch (error: unknown) {
            setRequestError(
                getRequestError(
                    error,
                    "The branch could not be saved",
                ),
            );
        } finally {
            setSubmitting(false);
        }
    }

    function handleOpenChange(
        open: boolean,
    ) {
        if (submitting) {
            return;
        }

        onOpenChange(open);
    }

    return (
        <CustomDialog
            open
            onOpenChange={
                handleOpenChange
            }
            title={title}
            banner="/loanhub-horizontal-logo.png"
            contentClassName="sm:max-w-4xl"
        >
            <form
                onSubmit={handleSubmit}
                className="flex min-h-0 flex-col"
            >
                <div className="space-y-6 px-5 py-6 sm:px-8">
                    {requestError && (
                        <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />

                            <div>
                                <p className="font-black">
                                    Unable to save branch
                                </p>

                                <p className="mt-1">
                                    {requestError}
                                </p>
                            </div>
                        </div>
                    )}

                    <section className="rounded-2xl border bg-card p-4 sm:p-5">
                        <SectionHeading
                            icon={
                                <Building2 className="h-5 w-5" />
                            }
                            title="Company assignment"
                            description="Choose the lending company that owns and operates this branch."
                        />

                        <label>
                            <FieldLabel required>
                                Company
                            </FieldLabel>

                            <NativeSelect
                                name="company_id"
                                value={
                                    values.company_id
                                }
                                onChange={
                                    handleChange
                                }
                                disabled={
                                    submitting
                                }
                                className={
                                    fieldClassName
                                }
                            >
                                <option value="">
                                    Select company
                                </option>

                                {[...companies]
                                    .sort(
                                        (
                                            first,
                                            second,
                                        ) =>
                                            first.name.localeCompare(
                                                second.name,
                                            ),
                                    )
                                    .map(
                                        (
                                            company,
                                        ) => (
                                            <option
                                                key={
                                                    company.id
                                                }
                                                value={
                                                    company.id
                                                }
                                            >
                                                {
                                                    company.name
                                                }
                                            </option>
                                        ),
                                    )}
                            </NativeSelect>

                            <FieldError
                                message={
                                    errors.company_id
                                }
                            />
                        </label>
                    </section>

                    <section className="rounded-2xl border bg-card p-4 sm:p-5">
                        <SectionHeading
                            icon={
                                <GitBranch className="h-5 w-5" />
                            }
                            title="Branch information"
                            description="Provide a clear branch name and its operating status."
                        />

                        <div className="grid gap-4 sm:grid-cols-2">
                            <label>
                                <FieldLabel required>
                                    Branch name
                                </FieldLabel>

                                <Input
                                    autoFocus
                                    name="name"
                                    value={
                                        values.name
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="e.g. Maseru Central"
                                    className={
                                        fieldClassName
                                    }
                                />

                                <FieldError
                                    message={
                                        errors.name
                                    }
                                />
                            </label>

                            <label className="flex cursor-pointer items-center justify-between gap-4 rounded-2xl border bg-background p-4">
                                <div>
                                    <p className="text-sm font-black">
                                        Active branch
                                    </p>

                                    <p className="mt-1 text-xs text-muted-foreground">
                                        Allow the branch to
                                        operate immediately.
                                    </p>
                                </div>

                                <Input
                                    type="checkbox"
                                    name="is_active"
                                    checked={
                                        values.is_active
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    className="h-5 w-5 accent-primary"
                                />
                            </label>
                        </div>
                    </section>

                    <section className="rounded-2xl border bg-card p-4 sm:p-5">
                        <SectionHeading
                            icon={
                                <MapPin className="h-5 w-5" />
                            }
                            title="Location"
                            description="Enter the branch district, town and full physical address."
                        />

                        <div className="grid gap-4 sm:grid-cols-2">
                            <label>
                                <FieldLabel required>
                                    District
                                </FieldLabel>

                                <NativeSelect
                                    name="district"
                                    value={
                                        values.district
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    className={
                                        fieldClassName
                                    }
                                >
                                    <option value="">
                                        Select district
                                    </option>

                                    {LESOTHO_DISTRICTS.map(
                                        (
                                            district,
                                        ) => (
                                            <option
                                                key={
                                                    district
                                                }
                                                value={
                                                    district
                                                }
                                            >
                                                {
                                                    district
                                                }
                                            </option>
                                        ),
                                    )}
                                </NativeSelect>

                                <FieldError
                                    message={
                                        errors.district
                                    }
                                />
                            </label>

                            <label>
                                <FieldLabel required>
                                    Town or village
                                </FieldLabel>

                                <Input
                                    name="town"
                                    value={
                                        values.town
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="Town or village"
                                    className={
                                        fieldClassName
                                    }
                                />

                                <FieldError
                                    message={
                                        errors.town
                                    }
                                />
                            </label>

                            <label className="sm:col-span-2">
                                <FieldLabel required>
                                    Physical address
                                </FieldLabel>

                                <Textarea
                                    name="address"
                                    value={
                                        values.address
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="Street, building, landmark and other useful directions"
                                    className="min-h-24 w-full resize-y rounded-xl border bg-background px-3 py-2.5 text-sm outline-none transition focus:border-primary focus:ring-2 focus:ring-primary/20 disabled:opacity-60"
                                />

                                <FieldError
                                    message={
                                        errors.address
                                    }
                                />
                            </label>
                        </div>
                    </section>

                    <section className="rounded-2xl border bg-card p-4 sm:p-5">
                        <SectionHeading
                            icon={
                                <Phone className="h-5 w-5" />
                            }
                            title="Contact information"
                            description="Add contact details clients and company staff can use."
                        />

                        <div className="grid gap-4 sm:grid-cols-2">
                            <label>
                                <FieldLabel required>
                                    Phone number
                                </FieldLabel>

                                <div className="relative">
                                    <Phone className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                                    <Input
                                        name="phone"
                                        value={
                                            values.phone
                                        }
                                        onChange={
                                            handleChange
                                        }
                                        disabled={
                                            submitting
                                        }
                                        placeholder="58000000"
                                        className={`${fieldClassName} pl-9`}
                                    />
                                </div>

                                <FieldError
                                    message={
                                        errors.phone
                                    }
                                />
                            </label>

                            <label>
                                <FieldLabel>
                                    Email address
                                </FieldLabel>

                                <div className="relative">
                                    <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />

                                    <Input
                                        type="email"
                                        name="email"
                                        value={
                                            values.email
                                        }
                                        onChange={
                                            handleChange
                                        }
                                        disabled={
                                            submitting
                                        }
                                        placeholder="branch@example.com"
                                        className={`${fieldClassName} pl-9`}
                                    />
                                </div>

                                <FieldError
                                    message={
                                        errors.email
                                    }
                                />
                            </label>
                        </div>
                    </section>
                </div>

                <div className="sticky bottom-0 flex flex-col-reverse gap-3 border-t bg-card/95 px-5 py-4 backdrop-blur sm:flex-row sm:items-center sm:justify-between sm:px-8">
                    <p className="flex items-center gap-2 text-xs text-muted-foreground">
                        <CheckCircle2 className="h-4 w-4 text-green-600" />

                        {state.mode === "create"
                            ? "The branch will be added to the selected company."
                            : "Existing branch information will be updated."}
                    </p>

                    <div className="flex items-center justify-end gap-3">
                        <button
                            type="button"
                            onClick={() =>
                                handleOpenChange(
                                    false,
                                )
                            }
                            disabled={submitting}
                            className="h-11 rounded-xl border bg-background px-5 text-sm font-black transition hover:bg-muted disabled:opacity-50"
                        >
                            Cancel
                        </button>

                        <button
                            type="submit"
                            disabled={submitting}
                            className="inline-flex h-11 min-w-40 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground shadow-sm transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Saving...
                                </>
                            ) : (
                                <>
                                    <Save className="h-4 w-4" />
                                    {state.mode ===
                                    "create"
                                        ? "Create branch"
                                        : "Save changes"}
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </form>
        </CustomDialog>
    );
}

export function BranchFormDialog(
    props: Props,
) {
    if (!props.state) {
        return null;
    }

    return (
        <BranchFormDialogContent
            key={
                props.state.branch?.id ??
                "create-branch"
            }
            state={props.state}
            companies={props.companies}
            onOpenChange={
                props.onOpenChange
            }
            onSubmit={props.onSubmit}
        />
    );
}
