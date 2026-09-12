"use client";

import { FormEvent, useState } from "react";
import { Building2, PlusCircle } from "lucide-react";
import { useRouter } from "next/navigation";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input as ShadcnInput } from "@/components/ui/input";
import { LoadingButton } from "@/components/ui/loading-button";
import { NativeSelect } from "@/components/ui/native-select";
import { Textarea } from "@/components/ui/textarea";

import { useAppDispatch, useAppSelector } from "@/store/hooks";
import {
    createCompany,
    LoanCompanyPayload,
} from "@/store/slices/companiesSlice";

const initialForm: LoanCompanyPayload = {
    name: "",
    registration_number: "",
    license_number: "",
    phone: "",
    email: "",
    website: "",
    address: "",
    district: "",
    status: "pending",
    is_active: true,
};

export function CreateCompanyForm() {
    const router = useRouter();
    const dispatch = useAppDispatch();

    const { actionLoadingId, error } = useAppSelector((state) => state.companies);

    const [form, setForm] = useState<LoanCompanyPayload>(initialForm);

    const loading = actionLoadingId === "create";

    const updateField = (
        field: keyof LoanCompanyPayload,
        value: string | boolean,
    ) => {
        setForm((current) => ({
            ...current,
            [field]: value,
        }));
    };

    const resetForm = () => {
        setForm(initialForm);
    };

    const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        const result = await dispatch(createCompany(form));

        if (createCompany.fulfilled.match(result)) {
            router.push(
                `/register-company-admin?companyId=${result.payload.id}&companyName=${encodeURIComponent(result.payload.name)}`,
            );
        }
    };

    return (
        <section className="rounded-[2rem] border border-border bg-card p-6 shadow-sm">
            <div className="mb-6 flex items-start gap-4">
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                    <Building2 className="h-6 w-6" />
                </div>

                <div>
                    <h2 className="text-xl font-black">Company Details</h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Submit your loan company information.
                    </p>
                </div>
            </div>

            {error && (
                <div className="mb-5 rounded-2xl border border-destructive/30 bg-destructive/10 p-4 text-sm font-semibold text-destructive">
                    {error}
                </div>
            )}

            <form onSubmit={handleSubmit} className="grid gap-4">
                <div className="grid gap-4 md:grid-cols-2">
                    <Input
                        label="Company Name"
                        value={form.name}
                        onChange={(value) => updateField("name", value)}
                        required
                    />

                    <Input
                        label="Registration Number"
                        value={form.registration_number}
                        onChange={(value) => updateField("registration_number", value)}
                        required
                    />

                    <Input
                        label="License Number"
                        value={form.license_number}
                        onChange={(value) => updateField("license_number", value)}
                        required
                    />

                    <Input
                        label="Phone"
                        value={form.phone}
                        onChange={(value) => updateField("phone", value)}
                        required
                    />

                    <Input
                        label="Email"
                        type="email"
                        value={form.email}
                        onChange={(value) => updateField("email", value)}
                        required
                    />

                    <Input
                        label="Website"
                        value={form.website}
                        onChange={(value) => updateField("website", value)}
                    />

                    <Input
                        label="District"
                        value={form.district}
                        onChange={(value) => updateField("district", value)}
                        required
                    />

                    <div>
                        <label className="mb-2 block text-sm font-black">Status</label>

                        <NativeSelect
                            value={form.status}
                            onChange={(event) => updateField("status", event.target.value)}
                            className="h-12 w-full cursor-pointer rounded-2xl border border-border bg-background px-4 text-sm font-bold outline-none transition-all focus:border-primary focus:ring-4 focus:ring-primary/10"
                        >
                            <option value="pending">Pending</option>
                        </NativeSelect>
                    </div>
                </div>

                <div>
                    <label className="mb-2 block text-sm font-black">Address</label>

                    <Textarea
                        value={form.address}
                        onChange={(event) => updateField("address", event.target.value)}
                        rows={3}
                        required
                        className="w-full resize-none rounded-2xl border border-border bg-background px-4 py-3 text-sm font-semibold outline-none transition-all focus:border-primary focus:ring-4 focus:ring-primary/10"
                    />
                </div>

                <label className="flex cursor-pointer items-center gap-3 rounded-2xl border border-border bg-background p-4">
                    <Checkbox
                        checked={form.is_active}
                        onCheckedChange={(value) => updateField("is_active", value === true)}
                    />

                    <span className="text-sm font-bold">Company account active</span>
                </label>

                <div className="flex flex-col gap-3 md:flex-row md:justify-end">
                    <Button type="button" variant="outline" onClick={resetForm} disabled={loading} className="h-12 rounded-2xl px-6">
                        Reset
                    </Button>

                    <LoadingButton type="submit" loading={loading} loadingText="Creating company..." className="h-12 rounded-2xl px-6">
                        <PlusCircle className="h-4 w-4" />
                        Continue
                    </LoadingButton>
                </div>
            </form>
        </section>
    );
}

function Input({
                   label,
                   value,
                   onChange,
                   type = "text",
                   required,
               }: {
    label: string;
    value: string | undefined;
    onChange: (value: string) => void;
    type?: string;
    required?: boolean;
}) {
    return (
        <div>
            <label className="mb-2 block text-sm font-black">{label}</label>

            <ShadcnInput
                type={type}
                value={value ?? ""}
                required={required}
                onChange={(event) => onChange(event.target.value)}
                className="h-12 rounded-2xl px-4 font-semibold"
            />
        </div>
    );
}