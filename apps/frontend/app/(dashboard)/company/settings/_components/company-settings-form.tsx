"use client";

import {
    AlertCircle,
    Building2,
    ContactRound,
    Loader2,
    MapPinned,
    RotateCcw,
    Save,
    ShieldCheck,
    WalletCards,
} from "lucide-react";

import type { CompanySettingsModel } from "../_hooks/use-company-settings";
import { LESOTHO_DISTRICTS } from "../_lib/company-settings";
import { SettingsInput, SettingsSelect } from "./settings-field";

type Props = Pick<
    CompanySettingsModel,
    | "form"
    | "errors"
    | "canManage"
    | "submitting"
    | "isDirty"
    | "updateField"
    | "reset"
    | "save"
>;

export function CompanySettingsForm({ form, errors, canManage, submitting, isDirty, updateField, reset, save }: Props) {
    return (
        <form onSubmit={save} noValidate className="overflow-hidden rounded-3xl border bg-card shadow-sm">
            <div className="border-b p-5 sm:p-6">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                        <h2 className="text-xl font-black">Company profile</h2>
                        <p className="mt-1 text-sm text-muted-foreground">Update the official tenant details used throughout LoanHub.</p>
                    </div>
                    {isDirty && <span className="w-fit rounded-full bg-amber-100 px-3 py-1.5 text-xs font-black text-amber-700 dark:bg-amber-950/40 dark:text-amber-400">Unsaved changes</span>}
                </div>
            </div>

            <div className="space-y-8 p-5 sm:p-6">
                {!canManage && (
                    <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-300">
                        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0" />
                        <div><p className="font-black">Read-only access</p><p className="mt-1 leading-6">Only a company owner or administrator can edit company settings.</p></div>
                    </div>
                )}
                {errors.form && (
                    <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-950/30 dark:text-red-300">
                        <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
                        <div><p className="font-black">Update failed</p><p className="mt-1">{errors.form}</p></div>
                    </div>
                )}

                <FormSection icon={Building2} title="Legal identity" description="Official company details used for verification, reporting and agreements.">
                    <div className="grid gap-5 md:grid-cols-2">
                        <SettingsInput className="md:col-span-2" label="Company name" name="name" value={form.name} onChange={(value) => updateField("name", value)} error={errors.name} placeholder="Registered company name" autoComplete="organization" disabled={!canManage} required />
                        <SettingsInput label="Registration number" name="registration_number" value={form.registration_number} onChange={(value) => updateField("registration_number", value)} error={errors.registration_number} placeholder="Company registration reference" disabled={!canManage} />
                        <SettingsInput label="Lending licence number" name="license_number" value={form.license_number} onChange={(value) => updateField("license_number", value)} error={errors.license_number} placeholder="Regulatory licence reference" disabled={!canManage} />
                    </div>
                </FormSection>

                <FormSection icon={ContactRound} title="Contact information" description="Primary company communication channels used for notices and authorised contact." bordered>
                    <div className="grid gap-5 md:grid-cols-2">
                        <SettingsInput label="Company phone" name="phone" value={form.phone} onChange={(value) => updateField("phone", value)} error={errors.phone} placeholder="+266 5800 0000" autoComplete="tel" disabled={!canManage} required />
                        <SettingsInput label="Company email" name="email" type="email" value={form.email} onChange={(value) => updateField("email", value)} error={errors.email} placeholder="info@company.co.ls" autoComplete="email" disabled={!canManage} />
                        <SettingsInput className="md:col-span-2" label="Website" name="website" type="url" value={form.website} onChange={(value) => updateField("website", value)} error={errors.website} placeholder="https://company.co.ls" hint="Include https:// at the beginning." disabled={!canManage} />
                    </div>
                </FormSection>

                <FormSection icon={MapPinned} title="Operating location" description="The primary location associated with this company tenant." bordered>
                    <div className="grid gap-5 md:grid-cols-2">
                        <SettingsSelect label="District" name="district" value={form.district} options={LESOTHO_DISTRICTS} onChange={(value) => updateField("district", value)} error={errors.district} disabled={!canManage} required />
                        <SettingsInput label="Physical address" name="address" value={form.address} onChange={(value) => updateField("address", value)} error={errors.address} placeholder="Building, street and area" autoComplete="street-address" disabled={!canManage} required />
                    </div>
                </FormSection>

                <FormSection
                    icon={WalletCards}
                    title="M-Pesa through IthutePayBridge"
                    description="This is the only M-Pesa setting your company needs in LoanHub. IthutePayBridge centrally manages the API key, platform public key, Origin, callbacks, SessionKey and provider configuration."
                    bordered
                >
                    <div className="grid gap-5 md:grid-cols-2">
                        <SettingsInput
                            label="M-Pesa business shortcode"
                            name="mpesa_shortcode"
                            value={form.mpesa_shortcode}
                            onChange={(value) => updateField("mpesa_shortcode", value.replace(/\D/g, "").slice(0, 12))}
                            error={errors.mpesa_shortcode}
                            placeholder="e.g. 123456"
                            hint="Used automatically for both money IN (C2B) and money OUT (B2C). Leave blank until Vodacom has authorised this shortcode for the PayBridge application."
                            inputMode="numeric"
                            disabled={!canManage}
                        />
                        <div className="rounded-2xl border bg-muted/30 p-4 text-sm leading-6 text-muted-foreground">
                            <p className="font-black text-foreground">No provider credentials are required here.</p>
                            <p className="mt-1">LoanHub sends this shortcode server-to-server. Customers and borrowers never choose or override the destination shortcode.</p>
                        </div>
                    </div>
                </FormSection>
            </div>

            {canManage && (
                <div className="flex flex-col-reverse gap-3 border-t bg-muted/20 p-5 sm:flex-row sm:justify-end sm:p-6">
                    <button type="button" onClick={reset} disabled={!isDirty || submitting} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border bg-background px-4 text-sm font-black transition hover:bg-muted disabled:opacity-50"><RotateCcw className="h-4 w-4" />Discard changes</button>
                    <button type="submit" disabled={!isDirty || submitting} className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground transition hover:bg-primary/90 disabled:opacity-50">
                        {submitting ? <><Loader2 className="h-4 w-4 animate-spin" />Saving changes...</> : <><Save className="h-4 w-4" />Save settings</>}
                    </button>
                </div>
            )}
        </form>
    );
}

function FormSection({ icon: Icon, title, description, bordered = false, children }: { icon: typeof Building2; title: string; description: string; bordered?: boolean; children: React.ReactNode }) {
    return (
        <section className={bordered ? "border-t pt-8" : ""}>
            <div className="mb-5 flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary"><Icon className="h-5 w-5" /></div>
                <div><h3 className="text-lg font-black">{title}</h3><p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p></div>
            </div>
            {children}
        </section>
    );
}
