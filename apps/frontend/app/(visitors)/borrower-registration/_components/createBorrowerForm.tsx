"use client";

import { FormEvent, useState } from "react";
import {
    UserPlus,
    ChevronLeft,
    ChevronRight,
    CheckCircle2,
    AlertCircle,
} from "lucide-react";

import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { createBorrower } from "@/store/features/thunks/borrowerThunks";
import { CreateBorrowerPayload } from "@/types/borrower";
import { Button } from "@/components/ui/button";
import { Checkbox as ShadcnCheckbox } from "@/components/ui/checkbox";
import { Input as ShadcnInput } from "@/components/ui/input";
import { LoadingButton } from "@/components/ui/loading-button";
import { EmployerGroupRegistrationField } from "@/components/clients/employer-group-registration-field";

const steps = ["Account", "Personal", "Address", "Employment", "Loans"];

const initialForm: CreateBorrowerPayload = {
    email: "",
    phone: "",
    password_hash: "",
    first_name: "",
    middle_name: "",
    last_name: "",
    gender: "male",
    date_of_birth: "",
    national_id: "",
    passport_number: "",
    marital_status: "single",
    nationality: "Mosotho",
    district: "",
    town_or_village: "",
    physical_address: "",
    employment_status: "employed",
    employer_name: "",
    employer_group_id: null,
    new_employer_group: null,
    income_day: null,
    job_title: "",
    monthly_income: 0,
    salary_date: "",
    has_existing_loans: false,
    existing_loan_total: 0,
    consent_to_share_profile: false,
    consent_to_credit_checks: false,
};

export function CreateBorrowerForm() {
    const dispatch = useAppDispatch();
    const { loading, error } = useAppSelector((s) => s.borrowers);

    const [step, setStep] = useState(0);
    const [form, setForm] = useState<CreateBorrowerPayload>(initialForm);

    const [passwordConfirm, setPasswordConfirm] = useState("");
    const [passwordError, setPasswordError] = useState("");

    const updateField = <K extends keyof CreateBorrowerPayload>(
        field: K,
        value: CreateBorrowerPayload[K]
    ) => {
        setForm((prev) => ({ ...prev, [field]: value }));
    };

    function validateStep(currentStep: number): boolean {
        setPasswordError("");

        if (currentStep === 0) {
            if (!form.email || !form.email.includes("@")) {
                setPasswordError("Valid email required");
                return false;
            }
            if (!form.phone) {
                setPasswordError("Phone required");
                return false;
            }
            if (!form.password_hash || form.password_hash.length < 8) {
                setPasswordError("Password must be at least 8 characters");
                return false;
            }
            if (form.password_hash !== passwordConfirm) {
                setPasswordError("Passwords do not match");
                return false;
            }
        }

        if (currentStep === 1) {
            if (!form.first_name || !form.last_name || !form.date_of_birth || !form.national_id) {
                setPasswordError("Fill all required personal details");
                return false;
            }
        }

        if (currentStep === 2) {
            if (!form.district || !form.town_or_village || !form.physical_address) {
                setPasswordError("Fill all address fields");
                return false;
            }
        }

        if (currentStep === 3) {
            const needsIncomeDay = ["employed", "self_employed", "pensioner"].includes(form.employment_status);
            const hasGroup = Boolean(form.employer_group_id || form.new_employer_group);
            if (form.employment_status === "employed" && !hasGroup) {
                setPasswordError("Select an employer/work group or add a new group.");
                return false;
            }
            if (needsIncomeDay && !form.income_day) {
                setPasswordError("Enter the day of the month when you normally receive income.");
                return false;
            }
        }

        if (currentStep === 4) {
            if (!form.consent_to_credit_checks) {
                setPasswordError("You must consent to credit checks to continue.");
                return false;
            }
        }

        return true;
    }

    // Handles intermediate navigation checks safely
    const handleNext = () => {
        if (!validateStep(step)) return;
        setStep((p) => p + 1);
    };

    async function handleSubmit(e: FormEvent<HTMLFormElement>) {
        e.preventDefault();

        // 1. Double check validation of the final step criteria
        if (!validateStep(step)) return;

        // 2. Prevent submission if we aren't explicitly on the last step view
        if (step !== steps.length - 1) return;

        await dispatch(createBorrower(form));
    }

    return (
        <div className="mx-auto w-full max-w-2xl rounded-2xl border border-border bg-card p-6 shadow-sm sm:p-8">
            <div className="mb-8">
                <h2 className="text-xl font-semibold tracking-tight text-foreground sm:text-2xl">Create Borrower Profile</h2>
                <p className="text-sm text-muted-foreground mt-1">Please fulfill your documentation workflow details below.</p>
            </div>

            {/* PROGRESS STEPPER */}
            <div className="mb-8 relative flex items-center justify-between w-full">
                {steps.map((s, index) => (
                    <div key={s} className="flex flex-col items-center flex-1 relative">
                        {index < steps.length - 1 && (
                            <div
                                className={`absolute top-5 left-[50%] right-[-50%] h-[2px] -translate-y-1/2 transition-colors duration-300 z-0
                                    ${index < step ? "bg-primary" : "bg-muted"}
                                `}
                            />
                        )}

                        <div
                            className={`flex h-10 w-10 items-center justify-center rounded-full text-sm font-semibold border-2 transition-all duration-300 z-10 relative
                                ${index < step ? "bg-primary border-primary text-primary-foreground" : ""}
                                ${index === step ? "bg-background border-primary text-primary shadow-sm shadow-primary/20 scale-105" : ""}
                                ${index > step ? "bg-background border-muted text-muted-foreground" : ""}
                            `}
                        >
                            {index < step ? (
                                <CheckCircle2 className="h-5 w-5" />
                            ) : (
                                <span>{index + 1}</span>
                            )}
                        </div>
                        <span className={`mt-2 text-xs font-medium transition-colors duration-200 hidden sm:inline
                            ${index === step ? "text-foreground font-semibold" : "text-muted-foreground"}
                        `}>
                            {s}
                        </span>
                    </div>
                ))}
            </div>

            <form onSubmit={handleSubmit} className="space-y-6">
                {/* GLOBAL ERRORS */}
                {(error || passwordError) && (
                    <div className="flex items-start gap-3 rounded-xl border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive animate-in fade-in-50 duration-200">
                        <AlertCircle className="h-5 w-5 mt-0.5 shrink-0" />
                        <div>
                            <p className="font-medium">Please correct the following errors:</p>
                            <p className="text-xs opacity-90 mt-0.5">{error || passwordError}</p>
                        </div>
                    </div>
                )}

                {/* FORM FIELDS STEPS */}
                <div className="grid gap-4 sm:grid-cols-2">
                    {step === 0 && (
                        <>
                            <Input label="Email Address" type="email" value={form.email} onChange={(v) => updateField("email", v)} placeholder="name@example.com" />
                            <Input label="Phone Number" type="tel" value={form.phone} onChange={(v) => updateField("phone", v)} placeholder="+266..." />
                            <Input label="Password" type="password" value={form.password_hash} onChange={(v) => updateField("password_hash", v)} placeholder="••••••••" />
                            <Input label="Confirm Password" type="password" value={passwordConfirm} onChange={setPasswordConfirm} placeholder="••••••••" />
                        </>
                    )}

                    {step === 1 && (
                        <>
                            <Input label="First Name" value={form.first_name} onChange={(v) => updateField("first_name", v)} />
                            <Input label="Middle Name" value={form.middle_name} onChange={(v) => updateField("middle_name", v)} />
                            <Input label="Last Name" value={form.last_name} onChange={(v) => updateField("last_name", v)} />
                            <Input label="Date of Birth" type="date" value={form.date_of_birth} onChange={(v) => updateField("date_of_birth", v)} />
                            <Input label="National ID" value={form.national_id} onChange={(v) => updateField("national_id", v)} />
                        </>
                    )}

                    {step === 2 && (
                        <>
                            <Input label="District" value={form.district} onChange={(v) => updateField("district", v)} />
                            <Input label="Town / Village" value={form.town_or_village} onChange={(v) => updateField("town_or_village", v)} />
                            <div className="sm:col-span-2">
                                <Input label="Physical Address" value={form.physical_address} onChange={(v) => updateField("physical_address", v)} />
                            </div>
                        </>
                    )}

                    {step === 3 && (
                        <>
                            <div className="sm:col-span-2">
                                <EmployerGroupRegistrationField
                                    employerGroupId={form.employer_group_id}
                                    employerName={form.employer_name}
                                    newEmployerGroup={form.new_employer_group}
                                    required={form.employment_status === "employed"}
                                    onChange={(selection) => setForm((current) => ({ ...current, ...selection }))}
                                />
                            </div>
                            <Input label="Job Title" value={form.job_title} onChange={(v) => updateField("job_title", v)} />
                            <Input
                                label="Income / pay day (1–31)"
                                type="number"
                                value={form.income_day ? String(form.income_day) : ""}
                                onChange={(v) => updateField("income_day", v ? Number(v) : null)}
                                placeholder="e.g. 20"
                            />
                            <div className="sm:col-span-2">
                                <Input
                                    label="Monthly Income"
                                    type="number"
                                    value={form.monthly_income === 0 ? "" : String(form.monthly_income)}
                                    onChange={(v) => updateField("monthly_income", Number(v))}
                                    placeholder="0.00"
                                />
                            </div>
                        </>
                    )}

                    {step === 4 && (
                        <div className="sm:col-span-2 space-y-4 pt-2">
                            <Checkbox
                                label="I currently hold active existing financial loans"
                                description="Check this box if you have outstanding credit accounts elsewhere."
                                checked={form.has_existing_loans}
                                onChange={(v) => updateField("has_existing_loans", v)}
                            />
                            <Checkbox
                                label="Consent to background profile resource sharing"
                                description="Allow our system infrastructure to synchronize profiles across platform entities."
                                checked={form.consent_to_share_profile}
                                onChange={(v) => updateField("consent_to_share_profile", v)}
                            />
                            <Checkbox
                                label="Consent to mandatory bureau credit checks"
                                description="I authorize formal credit inquiries regarding my active consumer history."
                                checked={form.consent_to_credit_checks}
                                onChange={(v) => updateField("consent_to_credit_checks", v)}
                            />
                        </div>
                    )}
                </div>

                {/* ACTION NAVIGATION CONTROLS */}
                <div className="flex items-center justify-between border-t border-border pt-6 mt-8">
                    <Button
                        type="button"
                        disabled={step === 0 || loading}
                        onClick={() => setStep((p) => p - 1)}
                        className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-input bg-background px-4 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground disabled:opacity-40 disabled:pointer-events-none"
                    >
                        <ChevronLeft className="h-4 w-4" />
                        <span>Back</span>
                    </Button>

                    {step < steps.length - 1 ? (
                        <Button
                            type="button"
                            onClick={handleNext}
                            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90 shadow-sm shadow-primary/10"
                        >
                            <span>Continue</span>
                            <ChevronRight className="h-4 w-4" />
                        </Button>
                    ) : (
                        <LoadingButton
                            type="submit"
                            loading={loading}
                            loadingText="Registering profile..."
                            className="h-11 min-w-[150px]"
                        >
                            <UserPlus className="h-4 w-4" />
                            Register Profile
                        </LoadingButton>
                    )}
                </div>
            </form>
        </div>
    );
}

/* ---------------- RE-STYLED FORM COMPONENT ELEMENTS ---------------- */

interface InputProps {
    label: string;
    value: string;
    onChange: (v: string) => void;
    type?: React.HTMLInputTypeAttribute;
    placeholder?: string;
}

function Input({ label, value, onChange, type = "text", placeholder }: InputProps) {
    return (
        <div className="space-y-1.5 w-full">
            <label className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/90 block">
                {label}
            </label>
            <ShadcnInput
                type={type}
                value={value}
                placeholder={placeholder}
                onChange={(event) => onChange(event.target.value)}
                className="h-11 rounded-xl"
            />
        </div>
    );
}

interface CheckboxProps {
    label: string;
    description?: string;
    checked: boolean;
    onChange: (v: boolean) => void;
}

function Checkbox({ label, description, checked, onChange }: CheckboxProps) {
    return (
        <label className="flex items-start gap-3 rounded-xl border border-border/60 bg-muted/30 p-4 transition-all hover:bg-muted/60 cursor-pointer select-none">
            <ShadcnCheckbox
                checked={checked}
                onCheckedChange={(value) => onChange(value === true)}
                className="mt-0.5 shrink-0"
            />
            <div className="space-y-0.5">
                <span className="text-sm font-medium text-foreground block">{label}</span>
                {description && <span className="text-xs text-muted-foreground block">{description}</span>}
            </div>
        </label>
    );
}