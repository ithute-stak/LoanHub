"use client";

import Link from "next/link";
import { FormEvent, useState, type ReactNode } from "react";
import { ArrowLeft, CheckCircle2, Landmark, Loader2, ShieldCheck } from "lucide-react";

import { registerCompanyOwner } from "@/api/companyRegistration";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import type {
    CompanyOwnerRegistrationPayload,
    InstitutionType,
} from "@/types/companyRegistration";
import { getErrorMessage } from "@/utils/apiError";

const DISTRICTS = [
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
];

type RegistrationForm = {
    institution_type: InstitutionType;
    company_name: string;
    registration_number: string;
    license_number: string;
    company_phone: string;
    company_email: string;
    website: string;
    address: string;
    district: string;
    first_name: string;
    middle_name: string;
    last_name: string;
    owner_phone: string;
    owner_email: string;
    national_id: string;
    password: string;
    confirm_password: string;
};

const INITIAL_FORM: RegistrationForm = {
    institution_type: "loan_company",
    company_name: "",
    registration_number: "",
    license_number: "",
    company_phone: "",
    company_email: "",
    website: "",
    address: "",
    district: "Maseru",
    first_name: "",
    middle_name: "",
    last_name: "",
    owner_phone: "",
    owner_email: "",
    national_id: "",
    password: "",
    confirm_password: "",
};

export default function RegisterInstitutionPage() {
    const [form, setForm] = useState(INITIAL_FORM);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [reference, setReference] = useState<string | null>(null);

    function update<K extends keyof RegistrationForm>(
        field: K,
        value: RegistrationForm[K],
    ) {
        setForm((current) => ({ ...current, [field]: value }));
        setError(null);
    }

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (submitting) return;
        if (form.password !== form.confirm_password) {
            setError("The passwords do not match.");
            return;
        }
        if (
            form.password.length < 10 ||
            !/[A-Z]/.test(form.password) ||
            !/[a-z]/.test(form.password) ||
            !/[0-9]/.test(form.password)
        ) {
            setError("Use at least 10 characters with uppercase, lowercase and a number.");
            return;
        }

        const payload: CompanyOwnerRegistrationPayload = {
            institution_type: form.institution_type,
            company_name: form.company_name.trim(),
            registration_number: form.registration_number.trim() || null,
            license_number: form.license_number.trim() || null,
            company_phone: form.company_phone.trim(),
            company_email: form.company_email.trim() || null,
            website: form.website.trim() || null,
            address: form.address.trim() || null,
            district: form.district,
            owner_email: form.owner_email.trim() || null,
            owner_phone: form.owner_phone.trim(),
            password: form.password,
            first_name: form.first_name.trim(),
            middle_name: form.middle_name.trim() || null,
            last_name: form.last_name.trim(),
            national_id: form.national_id.trim() || null,
            nationality: "Mosotho",
            physical_address: form.address.trim() || null,
        };

        setSubmitting(true);
        setError(null);
        try {
            const response = await registerCompanyOwner(payload);
            setReference(response.company_id);
        } catch (caught: unknown) {
            setError(getErrorMessage(caught, "Institution registration could not be submitted."));
        } finally {
            setSubmitting(false);
        }
    }

    if (reference) {
        return (
            <main className="flex min-h-screen items-center justify-center bg-slate-50 p-5">
                <section className="w-full max-w-xl rounded-3xl border bg-white p-8 text-center shadow-xl">
                    <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
                        <CheckCircle2 className="h-8 w-8" />
                    </div>
                    <h1 className="mt-5 text-2xl font-black">Institution profile submitted</h1>
                    <p className="mt-3 text-sm leading-6 text-slate-600">
                        The system owner must verify the institution and its regulatory details before activation.
                    </p>
                    <p className="mt-4 rounded-xl bg-slate-100 p-3 text-xs font-bold text-slate-600">
                        Application reference: {reference}
                    </p>
                    <Button asChild className="mt-6">
                        <Link href="/login">Return to login</Link>
                    </Button>
                </section>
            </main>
        );
    }

    return (
        <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,rgba(30,97,185,0.12),transparent_28%),linear-gradient(180deg,#f7fbff,#eef4fb)] p-4 sm:p-8">
            <div className="mx-auto max-w-5xl">
                <Link href="/login" className="inline-flex items-center gap-2 text-sm font-black text-primary">
                    <ArrowLeft className="h-4 w-4" /> Back to login
                </Link>

                <section className="mt-5 overflow-hidden rounded-[2rem] border bg-white shadow-xl">
                    <header className="border-b bg-slate-950 p-6 text-white sm:p-8">
                        <div className="flex items-center gap-3">
                            <div className="rounded-2xl bg-white/10 p-3">
                                <Landmark className="h-6 w-6" />
                            </div>
                            <div>
                                <p className="text-xs font-black uppercase tracking-[0.16em] text-blue-200">
                                    Regulated institution onboarding
                                </p>
                                <h1 className="mt-1 text-3xl font-black">Open a LoanHub institution profile</h1>
                            </div>
                        </div>
                        <p className="mt-4 max-w-3xl text-sm leading-6 text-slate-300">
                            Banks, lenders, microfinance institutions, cooperatives and government programmes can register as isolated LoanHub tenants. Registration does not imply regulatory approval.
                        </p>
                    </header>

                    <form onSubmit={submit} className="space-y-8 p-6 sm:p-8">
                        {error && (
                            <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-bold text-red-700">
                                {error}
                            </div>
                        )}

                        <FormSection title="Institution identity" description="Legal and regulatory information used during platform verification.">
                            <div className="space-y-2 md:col-span-2">
                                <Label htmlFor="institution-type">Institution type</Label>
                                <NativeSelect
                                    id="institution-type"
                                    value={form.institution_type}
                                    onChange={(event) => update("institution_type", event.target.value as InstitutionType)}
                                    className="h-12 rounded-xl"
                                >
                                    <option value="commercial_bank">Commercial bank</option>
                                    <option value="loan_company">Loan company</option>
                                    <option value="microfinance_institution">Microfinance institution</option>
                                    <option value="financial_cooperative">Financial cooperative</option>
                                    <option value="development_finance_institution">Development finance institution</option>
                                    <option value="government_lending_program">Government lending programme</option>
                                </NativeSelect>
                            </div>
                            <Field label="Institution name" value={form.company_name} onChange={(value) => update("company_name", value)} required />
                            <Field label="Registration number" value={form.registration_number} onChange={(value) => update("registration_number", value)} />
                            <Field label="Regulatory licence number" value={form.license_number} onChange={(value) => update("license_number", value)} />
                            <Field label="Institution phone" value={form.company_phone} onChange={(value) => update("company_phone", value)} required />
                            <Field label="Institution email" type="email" value={form.company_email} onChange={(value) => update("company_email", value)} />
                            <Field label="Website" type="url" value={form.website} onChange={(value) => update("website", value)} />
                            <div className="space-y-2">
                                <Label htmlFor="district">District</Label>
                                <NativeSelect id="district" value={form.district} onChange={(event) => update("district", event.target.value)} className="h-12 rounded-xl">
                                    {DISTRICTS.map((district) => <option key={district} value={district}>{district}</option>)}
                                </NativeSelect>
                            </div>
                            <Field label="Physical address" value={form.address} onChange={(value) => update("address", value)} required />
                        </FormSection>

                        <FormSection title="Authorised owner account" description="The initial owner can add bank staff and delegate roles after approval.">
                            <Field label="First name" value={form.first_name} onChange={(value) => update("first_name", value)} required />
                            <Field label="Middle name" value={form.middle_name} onChange={(value) => update("middle_name", value)} />
                            <Field label="Last name" value={form.last_name} onChange={(value) => update("last_name", value)} required />
                            <Field label="National ID" value={form.national_id} onChange={(value) => update("national_id", value)} />
                            <Field label="Owner phone" value={form.owner_phone} onChange={(value) => update("owner_phone", value)} required />
                            <Field label="Owner email" type="email" value={form.owner_email} onChange={(value) => update("owner_email", value)} />
                            <Field label="Password" type="password" value={form.password} onChange={(value) => update("password", value)} required />
                            <Field label="Confirm password" type="password" value={form.confirm_password} onChange={(value) => update("confirm_password", value)} required />
                        </FormSection>

                        <div className="flex items-start gap-3 rounded-2xl border bg-slate-50 p-4 text-sm text-slate-600">
                            <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" />
                            <p>
                                Platform approval verifies the submitted profile for LoanHub access. The institution remains responsible for obtaining and maintaining every licence required by the Central Bank of Lesotho or another competent authority.
                            </p>
                        </div>

                        <Button type="submit" size="lg" disabled={submitting} className="w-full gap-2">
                            {submitting ? <Loader2 className="h-5 w-5 animate-spin" /> : <Landmark className="h-5 w-5" />}
                            {submitting ? "Submitting…" : "Submit institution profile"}
                        </Button>
                    </form>
                </section>
            </div>
        </main>
    );
}

function FormSection({
    title,
    description,
    children,
}: {
    title: string;
    description: string;
    children: ReactNode;
}) {
    return (
        <section>
            <h2 className="text-xl font-black">{title}</h2>
            <p className="mt-1 text-sm text-slate-600">{description}</p>
            <div className="mt-5 grid gap-5 md:grid-cols-2">{children}</div>
        </section>
    );
}

function Field({
    label,
    value,
    onChange,
    type = "text",
    required = false,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    type?: string;
    required?: boolean;
}) {
    const id = `register-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    return (
        <div className="space-y-2">
            <Label htmlFor={id}>{label}</Label>
            <Input
                id={id}
                type={type}
                value={value}
                required={required}
                onChange={(event) => onChange(event.target.value)}
                className="h-12 rounded-xl"
            />
        </div>
    );
}
