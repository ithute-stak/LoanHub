"use client";

import { useCallback, useEffect, useState, type ReactNode } from "react";
import {
    BadgeCheck,
    CheckCircle2,
    CircleAlert,
    Landmark,
    Loader2,
    Network,
    Save,
    Scale,
    ShieldCheck,
    Sparkles,
} from "lucide-react";

import {
    getGovStackCapabilities,
    getInstitutionGovernanceProfile,
    getInstitutionReadiness,
    getInstitutionRoles,
    updateInstitutionGovernanceProfile,
    type GovStackCapability,
    type InstitutionGovernanceProfile,
    type InstitutionGovernanceUpdate,
    type InstitutionReadiness,
    type InstitutionRole,
} from "@/api/institutionGovernance";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { titleCase } from "@/lib/format";
import type { InstitutionType } from "@/store/slices/companiesSlice";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type Props = {
    canManage: boolean;
    institutionType: InstitutionType;
    companyId?: string;
};

export function InstitutionGovernanceSettings({
    canManage,
    institutionType,
    companyId,
}: Props) {
    const [form, setForm] = useState<InstitutionGovernanceProfile | null>(null);
    const [readiness, setReadiness] = useState<InstitutionReadiness | null>(null);
    const [roles, setRoles] = useState<InstitutionRole[]>([]);
    const [capabilities, setCapabilities] = useState<GovStackCapability[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [profile, score, roleCatalog, govStack] = await Promise.all([
                getInstitutionGovernanceProfile(companyId),
                getInstitutionReadiness(companyId),
                getInstitutionRoles(),
                getGovStackCapabilities(),
            ]);
            setForm(profile);
            setReadiness(score);
            setRoles(roleCatalog);
            setCapabilities(govStack);
        } catch (caught: unknown) {
            setError(getErrorMessage(caught, "Governance information could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, [companyId]);

    useEffect(() => {
        void load();
    }, [load]);

    function update<K extends keyof InstitutionGovernanceUpdate>(
        field: K,
        value: InstitutionGovernanceUpdate[K],
    ) {
        setForm((current) => current ? { ...current, [field]: value } : current);
    }

    async function save() {
        if (!form || saving || !canManage) return;
        setSaving(true);
        try {
            const payload = Object.fromEntries(
                Object.entries(form).filter(
                    ([key]) => !["id", "company_id", "created_at", "updated_at"].includes(key),
                ),
            ) as InstitutionGovernanceUpdate;
            const updated = await updateInstitutionGovernanceProfile(payload, companyId);
            setForm(updated);
            setReadiness(await getInstitutionReadiness(companyId));
            toast.success("Institution governance controls updated");
        } catch (caught: unknown) {
            toast.error(getErrorMessage(caught, "Governance controls could not be saved."));
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return (
            <div className="flex min-h-64 items-center justify-center gap-2 rounded-3xl border bg-card text-sm font-bold text-muted-foreground">
                <Loader2 className="h-5 w-5 animate-spin" /> Loading governance controls…
            </div>
        );
    }

    if (!form || error) {
        return (
            <section className="rounded-3xl border border-destructive/30 bg-destructive/5 p-6">
                <p className="font-black text-destructive">Governance workspace unavailable</p>
                <p className="mt-2 text-sm text-muted-foreground">{error}</p>
                <Button type="button" variant="outline" className="mt-4" onClick={() => void load()}>
                    Retry
                </Button>
            </section>
        );
    }

    const isBank = institutionType === "commercial_bank";

    return (
        <div className="space-y-6">
            <section className="grid gap-4 md:grid-cols-3">
                <article className="rounded-3xl border bg-card p-5 shadow-sm">
                    <div className="flex items-center gap-3">
                        <div className="rounded-2xl bg-primary/10 p-3 text-primary">
                            <BadgeCheck className="h-5 w-5" />
                        </div>
                        <div>
                            <p className="text-xs font-black uppercase text-muted-foreground">
                                Readiness score
                            </p>
                            <p className="text-2xl font-black">
                                {readiness?.score_percent ?? 0}%
                            </p>
                        </div>
                    </div>
                    <p className="mt-3 text-xs leading-5 text-muted-foreground">
                        {readiness?.completed_required_controls ?? 0} of{" "}
                        {readiness?.required_controls ?? 0} required controls complete
                    </p>
                </article>
                <article className="rounded-3xl border bg-card p-5 shadow-sm">
                    <div className="flex items-center gap-3">
                        <div className="rounded-2xl bg-emerald-500/10 p-3 text-emerald-600">
                            <Landmark className="h-5 w-5" />
                        </div>
                        <div>
                            <p className="text-xs font-black uppercase text-muted-foreground">
                                Institution type
                            </p>
                            <p className="text-lg font-black">{titleCase(institutionType)}</p>
                        </div>
                    </div>
                    <p className="mt-3 text-xs leading-5 text-muted-foreground">
                        {isBank
                            ? "Commercial-bank controls and role recommendations apply."
                            : "Controls are adjusted to the selected institution category."}
                    </p>
                </article>
                <article className="rounded-3xl border bg-card p-5 shadow-sm">
                    <div className="flex items-center gap-3">
                        <div className="rounded-2xl bg-amber-500/10 p-3 text-amber-700">
                            <ShieldCheck className="h-5 w-5" />
                        </div>
                        <div>
                            <p className="text-xs font-black uppercase text-muted-foreground">
                                Missing recommended roles
                            </p>
                            <p className="text-2xl font-black">
                                {readiness?.missing_recommended_roles.length ?? 0}
                            </p>
                        </div>
                    </div>
                    <p className="mt-3 text-xs leading-5 text-muted-foreground">
                        Assign roles in People & staff → Access & roles.
                    </p>
                </article>
            </section>

            <section className="rounded-3xl border bg-card shadow-sm">
                <div className="border-b p-6">
                    <h2 className="flex items-center gap-2 text-xl font-black">
                        <Scale className="h-5 w-5 text-primary" /> Licensing and accountable contacts
                    </h2>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Record regulator, licence and named control owners. This does not replace regulator approval.
                    </p>
                </div>
                <div className="grid gap-5 p-6 md:grid-cols-2">
                    <TextField label="Regulator" value={form.regulator_name ?? ""} disabled={!canManage} onChange={(value) => update("regulator_name", value || null)} placeholder="Central Bank of Lesotho" />
                    <TextField label="Licence category" value={form.regulatory_license_category ?? ""} disabled={!canManage} onChange={(value) => update("regulatory_license_category", value || null)} placeholder="Commercial bank / credit provider" />
                    <TextField label="Licence expiry date" type="date" value={form.license_expiry_date ?? ""} disabled={!canManage} onChange={(value) => update("license_expiry_date", value || null)} />
                    <TextField label="Bank code" value={form.bank_code ?? ""} disabled={!canManage} onChange={(value) => update("bank_code", value || null)} />
                    <TextField label="SWIFT / BIC" value={form.swift_bic ?? ""} disabled={!canManage} onChange={(value) => update("swift_bic", value || null)} />
                    <TextField label="Complaints contact" value={form.complaints_contact ?? ""} disabled={!canManage} onChange={(value) => update("complaints_contact", value || null)} placeholder="complaints@institution.co.ls" />
                    <TextField label="AML/CFT officer name" value={form.aml_cft_officer_name ?? ""} disabled={!canManage} onChange={(value) => update("aml_cft_officer_name", value || null)} />
                    <TextField label="AML/CFT officer email" type="email" value={form.aml_cft_officer_email ?? ""} disabled={!canManage} onChange={(value) => update("aml_cft_officer_email", value || null)} />
                    <TextField label="Data-protection officer name" value={form.data_protection_officer_name ?? ""} disabled={!canManage} onChange={(value) => update("data_protection_officer_name", value || null)} />
                    <TextField label="Data-protection officer email" type="email" value={form.data_protection_officer_email ?? ""} disabled={!canManage} onChange={(value) => update("data_protection_officer_email", value || null)} />
                    <TextField label="Regulatory reporting email" type="email" value={form.regulatory_reporting_contact_email ?? ""} disabled={!canManage} onChange={(value) => update("regulatory_reporting_contact_email", value || null)} />
                    <TextField label="Privacy notice URL" type="url" value={form.privacy_notice_url ?? ""} disabled={!canManage} onChange={(value) => update("privacy_notice_url", value || null)} placeholder="https://institution.co.ls/privacy" />
                    <TextField label="Data retention (months)" type="number" value={String(form.data_retention_months)} disabled={!canManage} onChange={(value) => update("data_retention_months", Math.min(120, Math.max(1, Number(value) || 1)))} />
                </div>
            </section>

            <section className="grid gap-6 xl:grid-cols-2">
                <ControlSection
                    icon={ShieldCheck}
                    title="Privacy, security and inclusion"
                    description="Operational safeguards supporting privacy, accessibility and resilient service delivery."
                >
                    <ControlCheck label="Purpose-specific consent management" checked={form.consent_management_enabled} disabled={!canManage} onChange={(checked) => update("consent_management_enabled", checked)} />
                    <ControlCheck label="Controlled customer data export" checked={form.data_export_enabled} disabled={!canManage} onChange={(checked) => update("data_export_enabled", checked)} />
                    <ControlCheck label="Low-bandwidth journeys verified" checked={form.low_bandwidth_supported} disabled={!canManage} onChange={(checked) => update("low_bandwidth_supported", checked)} />
                    <ControlCheck label="Accessibility review completed" checked={form.accessibility_reviewed} disabled={!canManage} onChange={(checked) => update("accessibility_reviewed", checked)} />
                    <ControlCheck label="English and Sesotho journeys supported" checked={form.english_sesotho_supported} disabled={!canManage} onChange={(checked) => update("english_sesotho_supported", checked)} />
                    <ControlCheck label="Business-continuity exercise passed" checked={form.business_continuity_tested} disabled={!canManage} onChange={(checked) => update("business_continuity_tested", checked)} />
                    <ControlCheck label="Incident-response exercise passed" checked={form.incident_response_tested} disabled={!canManage} onChange={(checked) => update("incident_response_tested", checked)} />
                </ControlSection>

                <ControlSection
                    icon={Sparkles}
                    title="Responsible AI"
                    description="AI-supported decisions remain explainable, monitored and subject to accountable human review."
                >
                    <ControlCheck label="AI-supported decisioning enabled" checked={form.ai_decisioning_enabled} disabled={!canManage} onChange={(checked) => update("ai_decisioning_enabled", checked)} />
                    <ControlCheck label="Human review is mandatory" checked={form.ai_human_review_required} disabled={!canManage || !form.ai_decisioning_enabled} onChange={(checked) => update("ai_human_review_required", checked)} />
                    <ControlCheck label="Decision explanations are mandatory" checked={form.ai_explainability_required} disabled={!canManage || !form.ai_decisioning_enabled} onChange={(checked) => update("ai_explainability_required", checked)} />
                    <ControlCheck label="Bias and fairness monitoring enabled" checked={form.ai_bias_monitoring_enabled} disabled={!canManage || !form.ai_decisioning_enabled} onChange={(checked) => update("ai_bias_monitoring_enabled", checked)} />
                </ControlSection>
            </section>

            <section className="rounded-3xl border bg-card p-6 shadow-sm">
                <h2 className="flex items-center gap-2 text-xl font-black">
                    <Network className="h-5 w-5 text-primary" /> GovStack and digital-public-good readiness
                </h2>
                <div className="mt-5 grid gap-5 md:grid-cols-2">
                    <div className="space-y-2">
                        <Label htmlFor="govstack-status">GovStack interoperability</Label>
                        <NativeSelect id="govstack-status" value={form.govstack_interoperability_status} disabled={!canManage} onChange={(event) => update("govstack_interoperability_status", event.target.value as InstitutionGovernanceProfile["govstack_interoperability_status"])} className="h-11 rounded-xl">
                            <option value="not_started">Not started</option>
                            <option value="planned">Planned</option>
                            <option value="in_progress">In progress</option>
                            <option value="ready">Ready</option>
                        </NativeSelect>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="dpg-status">DPG Standard assessment</Label>
                        <NativeSelect id="dpg-status" value={form.dpg_readiness_status} disabled={!canManage} onChange={(event) => update("dpg_readiness_status", event.target.value as InstitutionGovernanceProfile["dpg_readiness_status"])} className="h-11 rounded-xl">
                            <option value="not_started">Not started</option>
                            <option value="assessment">Assessment</option>
                            <option value="remediation">Remediation</option>
                            <option value="ready_for_review">Ready for review</option>
                        </NativeSelect>
                    </div>
                    <ControlCheck label="Supported OpenAPI specification published" checked={form.open_api_published} disabled={!canManage} onChange={(checked) => update("open_api_published", checked)} />
                    <div className="space-y-2 md:col-span-2">
                        <Label htmlFor="interoperability-notes">Interoperability notes</Label>
                        <textarea
                            id="interoperability-notes"
                            value={form.interoperability_notes ?? ""}
                            disabled={!canManage}
                            onChange={(event) => update("interoperability_notes", event.target.value || null)}
                            className="min-h-28 w-full rounded-xl border bg-background p-3 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
                            placeholder="Document authorised integrations, standards, owners and remaining dependencies."
                        />
                    </div>
                </div>
                <div className="mt-6 grid gap-3 md:grid-cols-2">
                    {capabilities.map((capability) => (
                        <article key={capability.key} className="rounded-2xl border p-4">
                            <div className="flex items-center justify-between gap-3">
                                <p className="font-black">{capability.label}</p>
                                <span className="rounded-full bg-primary/10 px-2.5 py-1 text-[11px] font-black text-primary">
                                    {titleCase(capability.status)}
                                </span>
                            </div>
                            <p className="mt-2 text-xs leading-5 text-muted-foreground">
                                {capability.implementation}
                            </p>
                        </article>
                    ))}
                </div>
            </section>

            <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
                <div className="rounded-3xl border bg-card p-6 shadow-sm">
                    <h2 className="text-xl font-black">Readiness controls</h2>
                    <div className="mt-4 space-y-3">
                        {readiness?.controls.map((control) => (
                            <div key={control.key} className="flex items-start gap-3 rounded-2xl border p-4">
                                {control.state === "complete" ? (
                                    <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
                                ) : control.state === "attention" ? (
                                    <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-amber-600" />
                                ) : (
                                    <BadgeCheck className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
                                )}
                                <div>
                                    <p className="text-sm font-black">{control.label}</p>
                                    <p className="mt-1 text-xs leading-5 text-muted-foreground">{control.detail}</p>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
                <div className="rounded-3xl border bg-card p-6 shadow-sm">
                    <h2 className="text-xl font-black">Institution role catalogue</h2>
                    <div className="mt-4 space-y-3">
                        {roles.map((role) => (
                            <div key={role.role} className="rounded-2xl border p-4">
                                <p className="text-sm font-black">{role.label}</p>
                                <p className="mt-1 text-[11px] font-bold uppercase text-primary">
                                    {titleCase(role.scope)}
                                </p>
                                <p className="mt-2 text-xs leading-5 text-muted-foreground">{role.purpose}</p>
                            </div>
                        ))}
                    </div>
                </div>
            </section>

            {canManage && (
                <div className="sticky bottom-4 flex justify-end">
                    <Button type="button" size="lg" disabled={saving} onClick={() => void save()} className="gap-2 shadow-lg">
                        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                        {saving ? "Saving…" : "Save governance controls"}
                    </Button>
                </div>
            )}
        </div>
    );
}

function TextField({
    label,
    value,
    onChange,
    disabled,
    type = "text",
    placeholder,
}: {
    label: string;
    value: string;
    onChange: (value: string) => void;
    disabled: boolean;
    type?: string;
    placeholder?: string;
}) {
    const id = `governance-${label.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
    return (
        <div className="space-y-2">
            <Label htmlFor={id}>{label}</Label>
            <Input id={id} type={type} value={value} disabled={disabled} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} className="h-11 rounded-xl" />
        </div>
    );
}

function ControlCheck({
    label,
    checked,
    onChange,
    disabled,
}: {
    label: string;
    checked: boolean;
    onChange: (checked: boolean) => void;
    disabled: boolean;
}) {
    return (
        <label className="flex items-center gap-3 rounded-2xl border p-4 text-sm font-bold">
            <Checkbox checked={checked} disabled={disabled} onCheckedChange={(value) => onChange(value === true)} />
            <span>{label}</span>
        </label>
    );
}

function ControlSection({
    icon: Icon,
    title,
    description,
    children,
}: {
    icon: typeof ShieldCheck;
    title: string;
    description: string;
    children: ReactNode;
}) {
    return (
        <section className="rounded-3xl border bg-card p-6 shadow-sm">
            <h2 className="flex items-center gap-2 text-xl font-black">
                <Icon className="h-5 w-5 text-primary" /> {title}
            </h2>
            <p className="mt-1 text-sm leading-6 text-muted-foreground">{description}</p>
            <div className="mt-5 space-y-3">{children}</div>
        </section>
    );
}
