"use client";

import { FormEvent, useEffect, useState } from "react";
import { Building2, Loader2, Save } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import type { InstitutionType, LoanCompany, LoanCompanyPayload } from "@/store/slices/companiesSlice";

type Props = {
    company: LoanCompany | null;
    open: boolean;
    isSaving: boolean;
    onOpenChange: (open: boolean) => void;
    onSave: (payload: Partial<LoanCompanyPayload>) => Promise<void>;
};

type CompanyForm = Pick<
    LoanCompany,
    | "name"
    | "institution_type"
    | "registration_number"
    | "license_number"
    | "phone"
    | "email"
    | "website"
    | "address"
    | "district"
>;

const EMPTY_FORM: CompanyForm = {
    name: "",
    institution_type: "loan_company",
    registration_number: "",
    license_number: "",
    phone: "",
    email: "",
    website: "",
    address: "",
    district: "",
};

export function CompanyEditDialog({
    company,
    open,
    isSaving,
    onOpenChange,
    onSave,
}: Props) {
    const [form, setForm] = useState<CompanyForm>(EMPTY_FORM);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!company || !open) return;
        setForm({
            name: company.name ?? "",
            institution_type: company.institution_type ?? "loan_company",
            registration_number: company.registration_number ?? "",
            license_number: company.license_number ?? "",
            phone: company.phone ?? "",
            email: company.email ?? "",
            website: company.website ?? "",
            address: company.address ?? "",
            district: company.district ?? "",
        });
        setError(null);
    }, [company, open]);

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!company || isSaving) return;
        if (!form.name.trim()) {
            setError("Company name is required.");
            return;
        }
        if (form.phone.trim().length < 8) {
            setError("Enter a valid company phone number.");
            return;
        }

        setError(null);
        await onSave({
            name: form.name.trim(),
            institution_type: form.institution_type,
            registration_number: form.registration_number.trim(),
            license_number: form.license_number.trim(),
            phone: form.phone.trim(),
            email: form.email.trim() || undefined,
            website: form.website.trim(),
            address: form.address.trim(),
            district: form.district.trim(),
        });
    }

    function update(field: keyof CompanyForm, value: string) {
        setForm((current) => ({ ...current, [field]: value }));
        setError(null);
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-3xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Building2 className="h-5 w-5 text-primary" /> Edit institution
                    </DialogTitle>
                    <DialogDescription>
                        Update {company?.name ?? "this company"} on behalf of its owner. Status and activation remain separate controlled actions.
                    </DialogDescription>
                </DialogHeader>

                <form onSubmit={submit} className="space-y-5">
                    {error ? (
                        <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm font-semibold text-destructive">
                            {error}
                        </div>
                    ) : null}

                    <div className="grid gap-4 sm:grid-cols-2">
                        <div className="space-y-2">
                            <Label htmlFor="company-institution-type">Institution type</Label>
                            <NativeSelect
                                id="company-institution-type"
                                value={form.institution_type}
                                onChange={(event) =>
                                    setForm((current) => ({
                                        ...current,
                                        institution_type: event.target.value as InstitutionType,
                                    }))
                                }
                                className="h-11 rounded-xl"
                            >
                                <option value="loan_company">Loan company</option>
                                <option value="commercial_bank">Commercial bank</option>
                                <option value="microfinance_institution">Microfinance institution</option>
                                <option value="financial_cooperative">Financial cooperative</option>
                                <option value="development_finance_institution">Development finance institution</option>
                                <option value="government_lending_program">Government lending programme</option>
                            </NativeSelect>
                        </div>
                        <CompanyField label="Institution name" field="name" value={form.name} onChange={update} required />
                        <CompanyField label="Phone" field="phone" value={form.phone} onChange={update} required />
                        <CompanyField label="Registration number" field="registration_number" value={form.registration_number} onChange={update} />
                        <CompanyField label="Licence number" field="license_number" value={form.license_number} onChange={update} />
                        <CompanyField label="Email" field="email" value={form.email} onChange={update} type="email" />
                        <CompanyField label="Website" field="website" value={form.website} onChange={update} type="url" />
                        <CompanyField label="District" field="district" value={form.district} onChange={update} />
                        <CompanyField label="Address" field="address" value={form.address} onChange={update} />
                    </div>

                    <DialogFooter>
                        <Button type="button" variant="outline" disabled={isSaving} onClick={() => onOpenChange(false)}>
                            Cancel
                        </Button>
                        <Button type="submit" disabled={isSaving}>
                            {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                            {isSaving ? "Saving…" : "Save company"}
                        </Button>
                    </DialogFooter>
                </form>
            </DialogContent>
        </Dialog>
    );
}

function CompanyField({
    label,
    field,
    value,
    onChange,
    type = "text",
    required = false,
}: {
    label: string;
    field: keyof CompanyForm;
    value: string;
    onChange: (field: keyof CompanyForm, value: string) => void;
    type?: string;
    required?: boolean;
}) {
    const id = `company-${field}`;
    return (
        <div className="space-y-2">
            <Label htmlFor={id}>{label}</Label>
            <Input
                id={id}
                type={type}
                value={value}
                required={required}
                onChange={(event) => onChange(field, event.target.value)}
                className="h-11 rounded-xl"
            />
        </div>
    );
}
