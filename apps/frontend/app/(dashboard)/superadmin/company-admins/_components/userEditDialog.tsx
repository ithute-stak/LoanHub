"use client";


import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { NativeSelect } from "@/components/ui/native-select";
import {
    AlertCircle,
    Building2,
    CalendarDays,
    CheckCircle2,
    Loader2,
    Mail,
    MapPin,
    Phone,
    ShieldCheck,
    UserRound,
} from "lucide-react";

import {
    useState,
    type ChangeEvent,
    type FormEvent,
} from "react";
import { api } from "@/lib/api";

import type {
    CompanyStaff,
    StaffUser,
} from "@/types/companyStuff";

import type {
    Gender,
    MaritalStatus,
    Person,
} from "@/types/person";
import {CustomDialog} from "@/components/ui/custom-dialog";

const USERS_API_PATH = "/auth/users";
const PEOPLE_API_PATH = "/people";
const COMPANY_STAFF_API_PATH = "/company-staff";

export type SavedAdminResult = {
    userId: string;
    email: string | null;
    phone: string;
    accountIsActive: boolean;
    staffIsActive: boolean;
    person: Person;
};

type Props = {
    admin: CompanyStaff;
    companyName: string;
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSaved: (result: SavedAdminResult) => void;
};

type FormState = {
    email: string;
    phone: string;

    first_name: string;
    middle_name: string;
    last_name: string;

    gender: Gender | "";
    date_of_birth: string;

    national_id: string;
    passport_number: string;
    marital_status: MaritalStatus | "";

    nationality: string;
    district: string;
    town_or_village: string;
    physical_address: string;

    account_is_active: boolean;
    staff_is_active: boolean;
};

type FormErrors = Partial<
    Record<keyof FormState, string>
>;

const inputClassName = [
    "h-11 w-full rounded-xl border bg-background px-3 text-sm",
    "outline-none transition placeholder:text-muted-foreground",
    "focus:border-primary focus:ring-2 focus:ring-primary/20",
    "disabled:cursor-not-allowed disabled:opacity-60",
].join(" ");

const textareaClassName = [
    "min-h-24 w-full resize-y rounded-xl border bg-background",
    "px-3 py-2.5 text-sm outline-none transition",
    "placeholder:text-muted-foreground",
    "focus:border-primary focus:ring-2 focus:ring-primary/20",
    "disabled:cursor-not-allowed disabled:opacity-60",
].join(" ");

function createInitialForm(
    admin: CompanyStaff,
): FormState {
    const user = admin.user;
    const person = user?.person;

    return {
        email: user?.email ?? "",
        phone: user?.phone ?? "",

        first_name: person?.first_name ?? "",
        middle_name: person?.middle_name ?? "",
        last_name: person?.last_name ?? "",

        gender: person?.gender ?? "",
        date_of_birth: person?.date_of_birth ?? "",

        national_id: person?.national_id ?? "",
        passport_number:
            person?.passport_number ?? "",

        marital_status:
            person?.marital_status ?? "",

        nationality:
            person?.nationality ?? "Mosotho",

        district: person?.district ?? "",

        town_or_village:
            person?.town_or_village ?? "",

        physical_address:
            person?.physical_address ?? "",

        account_is_active:
            user?.is_active ?? true,

        staff_is_active: admin.is_active,
    };
}

function cleanOptionalValue(
    value: string,
): string | null {
    const cleanedValue = value.trim();

    return cleanedValue || null;
}

function getErrorMessage(error: unknown): string {
    if (
        typeof error === "object" &&
        error !== null &&
        "response" in error
    ) {
        const requestError = error as {
            response?: {
                data?: {
                    detail?:
                        | string
                        | Array<{
                        msg?: string;
                    }>;
                };
            };
        };

        const detail =
            requestError.response?.data?.detail;

        if (typeof detail === "string") {
            return detail;
        }

        if (Array.isArray(detail)) {
            return detail
                .map((item) => item.msg)
                .filter(Boolean)
                .join(", ");
        }
    }

    if (error instanceof Error) {
        return error.message;
    }

    return "Failed to update the administrator";
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
        <p className="mt-1.5 flex items-center gap-1 text-xs text-red-600">
            <AlertCircle className="h-3.5 w-3.5" />
            {message}
        </p>
    );
}

function SectionHeader({
                           icon,
                           title,
                           description,
                       }: {
    icon: React.ReactNode;
    title: string;
    description: string;
}) {
    return (
        <div className="mb-5 flex items-start gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                {icon}
            </div>

            <div>
                <h3 className="font-bold">
                    {title}
                </h3>

                <p className="mt-0.5 text-xs text-muted-foreground">
                    {description}
                </p>
            </div>
        </div>
    );
}

export function UserEditDialog({
                                   admin,
                                   companyName,
                                   open,
                                   onOpenChange,
                                   onSaved,
                               }: Props) {
    const existingPerson =
        admin.user?.person ?? null;

    const [form, setForm] =
        useState<FormState>(() =>
            createInitialForm(admin),
        );

    const [errors, setErrors] =
        useState<FormErrors>({});

    const [requestError, setRequestError] =
        useState<string | null>(null);

    const [submitting, setSubmitting] =
        useState(false);

    function handleOpenChange(
        nextOpen: boolean,
    ) {
        if (submitting) {
            return;
        }

        onOpenChange(nextOpen);
    }

    function handleChange(
        event: ChangeEvent<
            | HTMLInputElement
            | HTMLSelectElement
            | HTMLTextAreaElement
        >,
    ) {
        const target = event.target;
        const field =
            target.name as keyof FormState;

        const value =
            target instanceof HTMLInputElement &&
            target.type === "checkbox"
                ? target.checked
                : target.value;

        setForm((currentForm) => ({
            ...currentForm,
            [field]: value,
        }));

        setErrors((currentErrors) => ({
            ...currentErrors,
            [field]: undefined,
        }));

        setRequestError(null);
    }

    function validateForm(): boolean {
        const nextErrors: FormErrors = {};

        if (!form.first_name.trim()) {
            nextErrors.first_name =
                "First name is required";
        }

        if (!form.last_name.trim()) {
            nextErrors.last_name =
                "Last name is required";
        }

        if (!form.phone.trim()) {
            nextErrors.phone =
                "Phone number is required";
        }

        if (
            form.email.trim() &&
            !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(
                form.email.trim(),
            )
        ) {
            nextErrors.email =
                "Enter a valid email address";
        }

        setErrors(nextErrors);

        return (
            Object.keys(nextErrors).length === 0
        );
    }

    async function handleSubmit(
        event: FormEvent<HTMLFormElement>,
    ) {
        event.preventDefault();

        if (!validateForm()) {
            return;
        }

        setSubmitting(true);
        setRequestError(null);

        const email = cleanOptionalValue(
            form.email,
        );

        const phone = form.phone.trim();

        const personPayload = {
            first_name:
                form.first_name.trim(),

            middle_name:
                cleanOptionalValue(
                    form.middle_name,
                ),

            last_name:
                form.last_name.trim(),

            gender:
                form.gender || null,

            date_of_birth:
                form.date_of_birth || null,

            national_id:
                cleanOptionalValue(
                    form.national_id,
                ),

            passport_number:
                cleanOptionalValue(
                    form.passport_number,
                ),

            marital_status:
                form.marital_status || null,

            nationality:
                cleanOptionalValue(
                    form.nationality,
                ),

            district:
                cleanOptionalValue(
                    form.district,
                ),

            town_or_village:
                cleanOptionalValue(
                    form.town_or_village,
                ),

            physical_address:
                cleanOptionalValue(
                    form.physical_address,
                ),
        };

        try {
            const userResponse =
                await api.put<StaffUser>(
                    `${USERS_API_PATH}/${admin.user_id}`,
                    {
                        email,
                        phone,
                        is_active:
                        form.account_is_active,
                    },
                );

            let savedPerson: Person;

            if (existingPerson) {
                const response =
                    await api.put<Person>(
                        `${PEOPLE_API_PATH}/${existingPerson.id}`,
                        personPayload,
                    );

                savedPerson = response.data;
            } else {
                const response =
                    await api.post<Person>(
                        `${PEOPLE_API_PATH}/`,
                        {
                            user_id:
                            admin.user_id,

                            ...personPayload,
                        },
                    );

                savedPerson = response.data;
            }

            if (
                form.staff_is_active !==
                admin.is_active
            ) {
                await api.put(
                    `${COMPANY_STAFF_API_PATH}/${admin.id}`,
                    {
                        is_active:
                        form.staff_is_active,
                    },
                );
            }

            onSaved({
                userId: admin.user_id,

                email:
                    userResponse.data.email ??
                    email,

                phone:
                    userResponse.data.phone ??
                    phone,

                accountIsActive:
                    userResponse.data
                        .is_active ??
                    form.account_is_active,

                staffIsActive:
                form.staff_is_active,

                person: savedPerson,
            });

            onOpenChange(false);
        } catch (error: unknown) {
            setRequestError(
                getErrorMessage(error),
            );
        } finally {
            setSubmitting(false);
        }
    }

    const dialogTitle = existingPerson
        ? "Edit administrator"
        : "Complete administrator profile";

    return (
        <CustomDialog
            open={open}
            onOpenChange={handleOpenChange}
            title={dialogTitle}
            banner="/ithute-solutions-mark.png"
        >
            <form onSubmit={handleSubmit}>
                <div className="border-b bg-muted/20 px-5 py-4 sm:px-8">
                    <div className="flex flex-wrap items-center gap-2">
                        <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1.5 text-xs font-medium">
                            <Building2 className="h-3.5 w-3.5 text-primary" />
                            {companyName}
                        </span>

                        <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-3 py-1.5 text-xs font-medium">
                            <ShieldCheck className="h-3.5 w-3.5 text-primary" />
                            Company administrator
                        </span>

                        {!existingPerson && (
                            <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-100 px-3 py-1.5 text-xs font-semibold text-amber-700 dark:bg-amber-950/40 dark:text-amber-300">
                                <AlertCircle className="h-3.5 w-3.5" />
                                Profile required
                            </span>
                        )}
                    </div>
                </div>

                <div className="space-y-6 px-5 py-6 sm:px-8">
                    {requestError && (
                        <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300">
                            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />

                            <div>
                                <p className="font-bold">
                                    Unable to save changes
                                </p>

                                <p className="mt-1">
                                    {requestError}
                                </p>
                            </div>
                        </div>
                    )}

                    <section className="rounded-2xl border bg-card p-4 sm:p-5">
                        <SectionHeader
                            icon={
                                <UserRound className="h-5 w-5" />
                            }
                            title="Personal information"
                            description="Enter the administrator’s legal and identifying details."
                        />

                        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                            <label>
                                <span className="mb-1.5 block text-sm font-medium">
                                    First name{" "}
                                    <span className="text-red-500">
                                        *
                                    </span>
                                </span>

                                <Input
                                    autoFocus
                                    name="first_name"
                                    value={
                                        form.first_name
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="First name"
                                    className={
                                        inputClassName
                                    }
                                />

                                <FieldError
                                    message={
                                        errors.first_name
                                    }
                                />
                            </label>

                            <label>
                                <span className="mb-1.5 block text-sm font-medium">
                                    Middle name
                                </span>

                                <Input
                                    name="middle_name"
                                    value={
                                        form.middle_name
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="Middle name"
                                    className={
                                        inputClassName
                                    }
                                />
                            </label>

                            <label>
                                <span className="mb-1.5 block text-sm font-medium">
                                    Last name{" "}
                                    <span className="text-red-500">
                                        *
                                    </span>
                                </span>

                                <Input
                                    name="last_name"
                                    value={
                                        form.last_name
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="Last name"
                                    className={
                                        inputClassName
                                    }
                                />

                                <FieldError
                                    message={
                                        errors.last_name
                                    }
                                />
                            </label>

                            <label>
                                <span className="mb-1.5 block text-sm font-medium">
                                    Gender
                                </span>

                                <NativeSelect
                                    name="gender"
                                    value={form.gender}
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    className={
                                        inputClassName
                                    }
                                >
                                    <option value="">
                                        Select gender
                                    </option>

                                    <option value="male">
                                        Male
                                    </option>

                                    <option value="female">
                                        Female
                                    </option>

                                    <option value="other">
                                        Other
                                    </option>
                                </NativeSelect>
                            </label>

                            <label>
                                <span className="mb-1.5 flex items-center gap-1.5 text-sm font-medium">
                                    <CalendarDays className="h-4 w-4 text-muted-foreground" />
                                    Date of birth
                                </span>

                                <Input
                                    type="date"
                                    name="date_of_birth"
                                    value={
                                        form.date_of_birth
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    className={
                                        inputClassName
                                    }
                                />
                            </label>

                            <label>
                                <span className="mb-1.5 block text-sm font-medium">
                                    Marital status
                                </span>

                                <NativeSelect
                                    name="marital_status"
                                    value={
                                        form.marital_status
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    className={
                                        inputClassName
                                    }
                                >
                                    <option value="">
                                        Select status
                                    </option>

                                    <option value="single">
                                        Single
                                    </option>

                                    <option value="married">
                                        Married
                                    </option>

                                    <option value="divorced">
                                        Divorced
                                    </option>

                                    <option value="widowed">
                                        Widowed
                                    </option>
                                </NativeSelect>
                            </label>

                            <label>
                                <span className="mb-1.5 block text-sm font-medium">
                                    National ID
                                </span>

                                <Input
                                    name="national_id"
                                    value={
                                        form.national_id
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="National ID"
                                    className={
                                        inputClassName
                                    }
                                />
                            </label>

                            <label>
                                <span className="mb-1.5 block text-sm font-medium">
                                    Passport number
                                </span>

                                <Input
                                    name="passport_number"
                                    value={
                                        form.passport_number
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="Passport number"
                                    className={
                                        inputClassName
                                    }
                                />
                            </label>

                            <label>
                                <span className="mb-1.5 block text-sm font-medium">
                                    Nationality
                                </span>

                                <Input
                                    name="nationality"
                                    value={
                                        form.nationality
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="Nationality"
                                    className={
                                        inputClassName
                                    }
                                />
                            </label>
                        </div>
                    </section>

                    <section className="rounded-2xl border bg-card p-4 sm:p-5">
                        <SectionHeader
                            icon={
                                <Mail className="h-5 w-5" />
                            }
                            title="Contact information"
                            description="Update the user’s sign-in and contact details."
                        />

                        <div className="grid gap-4 sm:grid-cols-2">
                            <label>
                                <span className="mb-1.5 flex items-center gap-1.5 text-sm font-medium">
                                    <Mail className="h-4 w-4 text-muted-foreground" />
                                    Email address
                                </span>

                                <Input
                                    type="email"
                                    name="email"
                                    value={form.email}
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="user@example.com"
                                    className={
                                        inputClassName
                                    }
                                />

                                <FieldError
                                    message={
                                        errors.email
                                    }
                                />
                            </label>

                            <label>
                                <span className="mb-1.5 flex items-center gap-1.5 text-sm font-medium">
                                    <Phone className="h-4 w-4 text-muted-foreground" />
                                    Phone number
                                    <span className="text-red-500">
                                        *
                                    </span>
                                </span>

                                <Input
                                    name="phone"
                                    value={form.phone}
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="58000000"
                                    className={
                                        inputClassName
                                    }
                                />

                                <FieldError
                                    message={
                                        errors.phone
                                    }
                                />
                            </label>
                        </div>
                    </section>

                    <section className="rounded-2xl border bg-card p-4 sm:p-5">
                        <SectionHeader
                            icon={
                                <MapPin className="h-5 w-5" />
                            }
                            title="Address"
                            description="Enter the administrator’s residential location."
                        />

                        <div className="grid gap-4 sm:grid-cols-2">
                            <label>
                                <span className="mb-1.5 block text-sm font-medium">
                                    District
                                </span>

                                <NativeSelect
                                    name="district"
                                    value={form.district}
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    className={
                                        inputClassName
                                    }
                                >
                                    <option value="">
                                        Select district
                                    </option>

                                    <option value="Berea">
                                        Berea
                                    </option>

                                    <option value="Butha-Buthe">
                                        Butha-Buthe
                                    </option>

                                    <option value="Leribe">
                                        Leribe
                                    </option>

                                    <option value="Mafeteng">
                                        Mafeteng
                                    </option>

                                    <option value="Maseru">
                                        Maseru
                                    </option>

                                    <option value="Mohale's Hoek">
                                        Mohale&apos;s Hoek
                                    </option>

                                    <option value="Mokhotlong">
                                        Mokhotlong
                                    </option>

                                    <option value="Qacha's Nek">
                                        Qacha&apos;s Nek
                                    </option>

                                    <option value="Quthing">
                                        Quthing
                                    </option>

                                    <option value="Thaba-Tseka">
                                        Thaba-Tseka
                                    </option>
                                </NativeSelect>
                            </label>

                            <label>
                                <span className="mb-1.5 block text-sm font-medium">
                                    Town or village
                                </span>

                                <Input
                                    name="town_or_village"
                                    value={
                                        form.town_or_village
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="Town or village"
                                    className={
                                        inputClassName
                                    }
                                />
                            </label>

                            <label className="sm:col-span-2">
                                <span className="mb-1.5 block text-sm font-medium">
                                    Physical address
                                </span>

                                <Textarea
                                    name="physical_address"
                                    value={
                                        form.physical_address
                                    }
                                    onChange={
                                        handleChange
                                    }
                                    disabled={
                                        submitting
                                    }
                                    placeholder="Full physical address"
                                    className={
                                        textareaClassName
                                    }
                                />
                            </label>
                        </div>
                    </section>

                    <section className="rounded-2xl border bg-card p-4 sm:p-5">
                        <SectionHeader
                            icon={
                                <ShieldCheck className="h-5 w-5" />
                            }
                            title="Account access"
                            description="Control the user account and company assignment."
                        />

                        <div className="grid gap-3 sm:grid-cols-2">
                            <label className="flex cursor-pointer items-center justify-between gap-4 rounded-2xl border bg-background p-4">
                                <div>
                                    <p className="text-sm font-bold">
                                        User account
                                    </p>

                                    <p className="mt-1 text-xs text-muted-foreground">
                                        Allow this user to sign in.
                                    </p>
                                </div>

                                <Input
                                    type="checkbox"
                                    name="account_is_active"
                                    checked={
                                        form.account_is_active
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

                            <label className="flex cursor-pointer items-center justify-between gap-4 rounded-2xl border bg-background p-4">
                                <div>
                                    <p className="text-sm font-bold">
                                        Company assignment
                                    </p>

                                    <p className="mt-1 text-xs text-muted-foreground">
                                        Keep this administrator active.
                                    </p>
                                </div>

                                <Input
                                    type="checkbox"
                                    name="staff_is_active"
                                    checked={
                                        form.staff_is_active
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
                </div>

                <div className="sticky bottom-0 flex flex-col-reverse gap-3 border-t bg-card/95 px-5 py-4 backdrop-blur sm:flex-row sm:items-center sm:justify-between sm:px-8">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        {existingPerson ? (
                            <>
                                <CheckCircle2 className="h-4 w-4 text-green-600" />
                                Existing profile will be updated.
                            </>
                        ) : (
                            <>
                                <AlertCircle className="h-4 w-4 text-amber-600" />
                                A new person profile will be created.
                            </>
                        )}
                    </div>

                    <div className="flex items-center justify-end gap-3">
                        <button
                            type="button"
                            onClick={() =>
                                handleOpenChange(false)
                            }
                            disabled={submitting}
                            className="h-11 rounded-xl border bg-background px-5 text-sm font-semibold transition hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            Cancel
                        </button>

                        <button
                            type="submit"
                            disabled={submitting}
                            className="inline-flex h-11 min-w-40 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground shadow-sm transition hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                            {submitting ? (
                                <>
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    Saving...
                                </>
                            ) : (
                                <>
                                    <CheckCircle2 className="h-4 w-4" />
                                    Save changes
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </form>
        </CustomDialog>
    );
}