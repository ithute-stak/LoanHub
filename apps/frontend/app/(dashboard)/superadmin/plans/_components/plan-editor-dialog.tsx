"use client";

import { FormEvent, useEffect, useState } from "react";
import { Save, Settings2 } from "lucide-react";
import { toast } from "@/utils/toast";

import { CustomDialog } from "@/components/ui/custom-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { LoadingButton } from "@/components/ui/loading-button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type {
    SubscriptionPlan,
    SubscriptionPlanCreatePayload,
    SubscriptionPlanFeatures,
    SubscriptionPlanLimits,
    SubscriptionPlanUpdatePayload,
} from "@/types/billing";

import type { PlanEditorMode } from "../_types/plan-page";
import {
    getExtraJson,
    KNOWN_FEATURE_KEYS,
    KNOWN_LIMIT_KEYS,
    mergeFeatures,
    mergeLimits,
    normalizePlanCode,
    parseJsonObject,
} from "../_lib/plan-utils";

type Props = {
    open: boolean;
    mode: PlanEditorMode;
    plan: SubscriptionPlan | null;
    saving: boolean;
    onOpenChange: (open: boolean) => void;
    onSubmit: (
        payload: SubscriptionPlanCreatePayload | SubscriptionPlanUpdatePayload,
    ) => Promise<void>;
};

type FormState = {
    code: string;
    name: string;
    description: string;
    monthlyPrice: string;
    annualPrice: string;
    unlockFee: string;
    transactionFee: string;
    branches: string;
    staff: string;
    products: string;
    marketplaceFullAccess: boolean;
    advancedAnalytics: boolean;
    customBranding: boolean;
    apiAccess: boolean;
    prioritySupport: boolean;
    auditExports: boolean;
    isActive: boolean;
    isPublic: boolean;
    extraFeaturesJson: string;
    extraLimitsJson: string;
};

const EMPTY_FORM: FormState = {
    code: "",
    name: "",
    description: "",
    monthlyPrice: "0",
    annualPrice: "0",
    unlockFee: "0",
    transactionFee: "0",
    branches: "1",
    staff: "5",
    products: "3",
    marketplaceFullAccess: false,
    advancedAnalytics: false,
    customBranding: false,
    apiAccess: false,
    prioritySupport: false,
    auditExports: false,
    isActive: true,
    isPublic: true,
    extraFeaturesJson: "{}",
    extraLimitsJson: "{}",
};

function toForm(plan: SubscriptionPlan | null): FormState {
    if (!plan) return EMPTY_FORM;
    return {
        code: plan.code,
        name: plan.name,
        description: plan.description ?? "",
        monthlyPrice: String(plan.monthly_price),
        annualPrice: String(plan.annual_price),
        unlockFee: String(plan.marketplace_unlock_fee),
        transactionFee: String(plan.transaction_fee_percent),
        branches: String(plan.limits?.branches ?? 1),
        staff: String(plan.limits?.staff ?? 5),
        products: String(plan.limits?.products ?? 3),
        marketplaceFullAccess: Boolean(plan.features?.marketplace_full_access),
        advancedAnalytics: Boolean(plan.features?.advanced_analytics),
        customBranding: Boolean(plan.features?.custom_branding),
        apiAccess: Boolean(plan.features?.api_access),
        prioritySupport: Boolean(plan.features?.priority_support),
        auditExports: Boolean(plan.features?.audit_exports),
        isActive: plan.is_active,
        isPublic: plan.is_public,
        extraFeaturesJson: getExtraJson(plan.features, KNOWN_FEATURE_KEYS),
        extraLimitsJson: getExtraJson(plan.limits, KNOWN_LIMIT_KEYS),
    };
}

function NumberField({
    id,
    label,
    value,
    onChange,
    step = "1",
    min = "0",
    hint,
}: {
    id: string;
    label: string;
    value: string;
    onChange: (value: string) => void;
    step?: string;
    min?: string;
    hint?: string;
}) {
    return (
        <div className="space-y-2">
            <Label htmlFor={id}>{label}</Label>
            <Input
                id={id}
                type="number"
                min={min}
                step={step}
                value={value}
                onChange={(event) => onChange(event.target.value)}
                className="h-11"
            />
            {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        </div>
    );
}

function ToggleField({
    label,
    description,
    checked,
    onCheckedChange,
    disabled = false,
}: {
    label: string;
    description: string;
    checked: boolean;
    onCheckedChange: (checked: boolean) => void;
    disabled?: boolean;
}) {
    return (
        <div className="flex items-start justify-between gap-4 rounded-2xl border bg-background p-4">
            <div>
                <p className="font-bold">{label}</p>
                <p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p>
            </div>
            <Switch checked={checked} onCheckedChange={onCheckedChange} disabled={disabled} />
        </div>
    );
}

export function PlanEditorDialog({
    open,
    mode,
    plan,
    saving,
    onOpenChange,
    onSubmit,
}: Props) {
    const [form, setForm] = useState<FormState>(EMPTY_FORM);

    useEffect(() => {
        if (!open) return;
        const timer = window.setTimeout(() => setForm(toForm(plan)), 0);
        return () => window.clearTimeout(timer);
    }, [open, plan]);

    function update<K extends keyof FormState>(key: K, value: FormState[K]) {
        setForm((current) => ({ ...current, [key]: value }));
    }

    async function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        try {
            const code = normalizePlanCode(form.code);
            if (mode === "create" && !/^[A-Z][A-Z0-9_]*$/.test(code)) {
                throw new Error("Plan code must start with a letter and contain only A-Z, 0-9 and underscores");
            }
            if (form.name.trim().length < 2) throw new Error("Plan name is required");

            const monthlyPrice = Number(form.monthlyPrice);
            const annualPrice = Number(form.annualPrice);
            const unlockFee = Number(form.unlockFee);
            const transactionFee = Number(form.transactionFee);
            const branches = Number(form.branches);
            const staff = Number(form.staff);
            const products = Number(form.products);

            const numbers = [monthlyPrice, annualPrice, unlockFee, transactionFee];
            if (numbers.some((value) => !Number.isFinite(value) || value < 0)) {
                throw new Error("Prices and fees must be valid non-negative numbers");
            }
            if (transactionFee > 100) throw new Error("Transaction fee cannot exceed 100%");
            if ([branches, staff, products].some((value) => !Number.isInteger(value) || value < -1)) {
                throw new Error("Limits must be whole numbers of -1 or greater");
            }

            const extraFeatures = parseJsonObject(form.extraFeaturesJson, "Extra features");
            const extraLimits = parseJsonObject(form.extraLimitsJson, "Extra limits");

            const knownFeatures: SubscriptionPlanFeatures = {
                marketplace_full_access: form.marketplaceFullAccess,
                advanced_analytics: form.advancedAnalytics,
                custom_branding: form.customBranding,
                api_access: form.apiAccess,
                priority_support: form.prioritySupport,
                audit_exports: form.auditExports,
            };
            const knownLimits: SubscriptionPlanLimits = { branches, staff, products };

            const shared: SubscriptionPlanUpdatePayload = {
                name: form.name.trim(),
                description: form.description.trim() || null,
                monthly_price: monthlyPrice,
                annual_price: annualPrice,
                marketplace_unlock_fee: unlockFee,
                transaction_fee_percent: transactionFee,
                features: mergeFeatures(extraFeatures, knownFeatures),
                limits: mergeLimits(extraLimits, knownLimits),
                is_active: form.isActive,
                is_public: form.isPublic,
            };

            await onSubmit(mode === "create" ? { code, ...shared } : shared);
        } catch (error: unknown) {
            toast.error(error instanceof Error ? error.message : "Please check the plan configuration");
        }
    }

    const starterLocked = mode === "edit" && plan?.code === "STARTER";

    return (
        <CustomDialog
            open={open}
            onOpenChange={onOpenChange}
            title={mode === "create" ? "Create pricing plan" : `Edit ${plan?.name ?? "plan"}`}
            contentClassName="sm:max-w-5xl"
        >
            <form onSubmit={handleSubmit} className="space-y-7 p-5 sm:p-7">
                <section className="space-y-4">
                    <div className="flex items-center gap-2">
                        <Settings2 className="h-5 w-5 text-primary" />
                        <h3 className="text-lg font-black">Plan identity</h3>
                    </div>
                    <div className="grid gap-4 md:grid-cols-2">
                        <div className="space-y-2">
                            <Label htmlFor="plan-code">Plan code</Label>
                            <Input
                                id="plan-code"
                                value={form.code}
                                onChange={(event) => update("code", event.target.value)}
                                disabled={mode === "edit"}
                                placeholder="GROWTH"
                                className="h-11 uppercase"
                            />
                            <p className="text-xs text-muted-foreground">Permanent internal identifier. It cannot be changed later.</p>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="plan-name">Display name</Label>
                            <Input
                                id="plan-name"
                                value={form.name}
                                onChange={(event) => update("name", event.target.value)}
                                placeholder="Growth"
                                className="h-11"
                            />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="plan-description">Description</Label>
                        <Textarea
                            id="plan-description"
                            value={form.description}
                            onChange={(event) => update("description", event.target.value)}
                            placeholder="Explain who this plan is designed for..."
                            className="min-h-24"
                        />
                    </div>
                </section>

                <section className="space-y-4">
                    <h3 className="text-lg font-black">Pricing and platform fees</h3>
                    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                        <NumberField id="monthly-price" label="Monthly price (LSL)" value={form.monthlyPrice} onChange={(value) => update("monthlyPrice", value)} step="0.01" />
                        <NumberField id="annual-price" label="Annual price (LSL)" value={form.annualPrice} onChange={(value) => update("annualPrice", value)} step="0.01" />
                        <NumberField id="unlock-fee" label="Marketplace unlock fee" value={form.unlockFee} onChange={(value) => update("unlockFee", value)} step="0.01" />
                        <NumberField id="transaction-fee" label="Transaction fee (%)" value={form.transactionFee} onChange={(value) => update("transactionFee", value)} step="0.001" />
                    </div>
                </section>

                <section className="space-y-4">
                    <h3 className="text-lg font-black">Resource limits</h3>
                    <div className="grid gap-4 sm:grid-cols-3">
                        <NumberField id="branch-limit" label="Branches" value={form.branches} onChange={(value) => update("branches", value)} min="-1" hint="Use -1 for unlimited and 0 to disable." />
                        <NumberField id="staff-limit" label="Staff accounts" value={form.staff} onChange={(value) => update("staff", value)} min="-1" hint="Use -1 for unlimited and 0 to disable." />
                        <NumberField id="product-limit" label="Loan products" value={form.products} onChange={(value) => update("products", value)} min="-1" hint="Use -1 for unlimited and 0 to disable." />
                    </div>
                </section>

                <section className="space-y-4">
                    <h3 className="text-lg font-black">Feature access</h3>
                    <div className="grid gap-3 md:grid-cols-2">
                        <ToggleField label="Full marketplace access" description="Companies can view complete eligible requests without paying per unlock." checked={form.marketplaceFullAccess} onCheckedChange={(value) => update("marketplaceFullAccess", value)} />
                        <ToggleField label="Advanced analytics" description="Unlock enhanced tenant dashboards and performance reporting." checked={form.advancedAnalytics} onCheckedChange={(value) => update("advancedAnalytics", value)} />
                        <ToggleField label="Custom branding" description="Allow tenant logos, colours and branded documents." checked={form.customBranding} onCheckedChange={(value) => update("customBranding", value)} />
                        <ToggleField label="API access" description="Allow approved programmatic access and integrations." checked={form.apiAccess} onCheckedChange={(value) => update("apiAccess", value)} />
                        <ToggleField label="Priority support" description="Mark tenants for priority operational support." checked={form.prioritySupport} onCheckedChange={(value) => update("prioritySupport", value)} />
                        <ToggleField label="Audit exports" description="Allow advanced compliance and audit data exports." checked={form.auditExports} onCheckedChange={(value) => update("auditExports", value)} />
                    </div>
                </section>

                <section className="space-y-4">
                    <h3 className="text-lg font-black">Availability</h3>
                    <div className="grid gap-3 md:grid-cols-2">
                        <ToggleField
                            label="Plan active"
                            description={starterLocked ? "STARTER is the required fallback and cannot be deactivated." : "Inactive plans cannot be purchased or used as a current fallback."}
                            checked={form.isActive}
                            onCheckedChange={(value) => update("isActive", value)}
                            disabled={starterLocked}
                        />
                        <ToggleField label="Visible to companies" description="Public plans appear on the company subscription page." checked={form.isPublic} onCheckedChange={(value) => update("isPublic", value)} />
                    </div>
                </section>

                <details className="rounded-2xl border bg-muted/20 p-4">
                    <summary className="cursor-pointer font-black">Advanced custom JSON configuration</summary>
                    <p className="mt-2 text-xs leading-5 text-muted-foreground">Add future feature flags or limits without changing the page. Known fields above take priority over matching JSON keys.</p>
                    <div className="mt-4 grid gap-4 lg:grid-cols-2">
                        <div className="space-y-2">
                            <Label htmlFor="extra-features">Extra features JSON</Label>
                            <Textarea id="extra-features" value={form.extraFeaturesJson} onChange={(event) => update("extraFeaturesJson", event.target.value)} className="min-h-40 font-mono text-xs" />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="extra-limits">Extra limits JSON</Label>
                            <Textarea id="extra-limits" value={form.extraLimitsJson} onChange={(event) => update("extraLimitsJson", event.target.value)} className="min-h-40 font-mono text-xs" />
                        </div>
                    </div>
                </details>

                <div className="sticky bottom-0 -mx-5 -mb-5 flex flex-col-reverse gap-3 border-t bg-card/95 px-5 py-4 backdrop-blur sm:-mx-7 sm:-mb-7 sm:flex-row sm:justify-end sm:px-7">
                    <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>Cancel</Button>
                    <LoadingButton type="submit" loading={saving} loadingText="Saving plan...">
                        <Save className="h-4 w-4" />{mode === "create" ? "Create plan" : "Save changes"}
                    </LoadingButton>
                </div>
            </form>
        </CustomDialog>
    );
}
