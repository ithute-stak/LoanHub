"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { RefreshCcw, Save, ShieldCheck, SlidersHorizontal } from "lucide-react";

import { originationApi, toOriginationPolicyUpdate } from "@/api/origination";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import type { OriginationPolicy, OriginationPolicyUpdate } from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type TopUpRules = Pick<
    OriginationPolicyUpdate,
    | "allow_top_up"
    | "top_up_min_paid_percent"
    | "top_up_min_paid_installments"
    | "top_up_owner_exception_enabled"
    | "top_up_require_positive_history"
    | "top_up_settle_existing_balance"
>;

type Props = {
    canManage: boolean;
};

function rulesFromPolicy(policy: OriginationPolicy): TopUpRules {
    return {
        allow_top_up: policy.allow_top_up,
        top_up_min_paid_percent: Number(policy.top_up_min_paid_percent),
        top_up_min_paid_installments: Number(policy.top_up_min_paid_installments),
        top_up_owner_exception_enabled: policy.top_up_owner_exception_enabled,
        top_up_require_positive_history: policy.top_up_require_positive_history,
        top_up_settle_existing_balance: policy.top_up_settle_existing_balance,
    };
}

export function CompanyTopUpRulesSettings({ canManage }: Props) {
    const [rules, setRules] = useState<TopUpRules | null>(null);
    const [policyVersion, setPolicyVersion] = useState<number | null>(null);
    const [loading, setLoading] = useState(canManage);
    const [saving, setSaving] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);

    const load = useCallback(async () => {
        if (!canManage) {
            setLoading(false);
            return;
        }

        setLoading(true);
        setLoadError(null);
        try {
            const policy = await originationApi.getPolicy();
            setRules(rulesFromPolicy(policy));
            setPolicyVersion(policy.version);
        } catch (error: unknown) {
            setLoadError(getErrorMessage(error, "Loan top-up rules could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, [canManage]);

    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    const ruleSummary = useMemo(() => {
        if (!rules) return "";
        if (!rules.allow_top_up) return "Top-ups are disabled for this company.";

        const thresholdParts = [`${rules.top_up_min_paid_percent}% of the existing loan paid`];
        if (rules.top_up_min_paid_installments > 0) {
            thresholdParts.push(`${rules.top_up_min_paid_installments} paid instalment${rules.top_up_min_paid_installments === 1 ? "" : "s"}`);
        }
        if (rules.top_up_require_positive_history) thresholdParts.push("positive repayment history");

        return `Normal eligibility requires ${thresholdParts.join(", ")}.`;
    }, [rules]);

    async function save(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canManage || !rules) return;

        if (rules.top_up_min_paid_percent < 0 || rules.top_up_min_paid_percent > 100) {
            toast.error("Top-up paid percentage must be between 0% and 100%.");
            return;
        }
        if (
            !Number.isInteger(rules.top_up_min_paid_installments)
            || rules.top_up_min_paid_installments < 0
            || rules.top_up_min_paid_installments > 120
        ) {
            toast.error("Top-up paid instalments must be a whole number between 0 and 120.");
            return;
        }

        setSaving(true);
        try {
            const latest = await originationApi.getPolicy();
            const updated = await originationApi.updatePolicy({
                ...toOriginationPolicyUpdate(latest),
                ...rules,
            });
            setRules(rulesFromPolicy(updated));
            setPolicyVersion(updated.version);
            toast.success("Loan top-up rules updated", {
                description: `Policy version ${updated.version} is now active for this company.`,
            });
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Loan top-up rules could not be saved."));
        } finally {
            setSaving(false);
        }
    }

    if (!canManage) {
        return (
            <Alert>
                <ShieldCheck className="h-4 w-4" />
                <AlertTitle>Company-management setting</AlertTitle>
                <AlertDescription>
                    Only the company owner or company administrator can change company-wide loan top-up rules.
                </AlertDescription>
            </Alert>
        );
    }

    if (loading) {
        return (
            <Card className="rounded-3xl">
                <CardContent className="flex min-h-52 items-center justify-center p-8 text-sm font-bold text-muted-foreground">
                    Loading this company&apos;s top-up rules…
                </CardContent>
            </Card>
        );
    }

    if (loadError || !rules) {
        return (
            <Alert variant="destructive">
                <ShieldCheck className="h-4 w-4" />
                <AlertTitle>Top-up rules unavailable</AlertTitle>
                <AlertDescription className="space-y-3">
                    <p>{loadError ?? "The company policy could not be loaded."}</p>
                    <Button type="button" size="sm" variant="outline" onClick={() => void load()}>
                        <RefreshCcw className="h-4 w-4" /> Retry
                    </Button>
                </AlertDescription>
            </Alert>
        );
    }

    return (
        <form onSubmit={save} className="space-y-6">
            <Card className="overflow-hidden rounded-3xl border-primary/20">
                <CardHeader className="border-b bg-gradient-to-r from-primary/10 via-card to-emerald-500/10">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                            <CardTitle className="flex items-center gap-2">
                                <SlidersHorizontal className="h-5 w-5 text-primary" />
                                Company loan top-up rules
                            </CardTitle>
                            <CardDescription className="mt-2 max-w-3xl leading-6">
                                These rules belong only to the active company. LoanHub checks them whenever this company&apos;s borrower requests a top-up; other companies keep their own independent rules.
                            </CardDescription>
                        </div>
                        <Badge variant="outline" className="w-fit">Policy v{policyVersion ?? "—"}</Badge>
                    </div>
                </CardHeader>

                <CardContent className="space-y-6 p-5 sm:p-7">
                    <div className="rounded-2xl border bg-muted/20 p-4">
                        <RuleCheckbox
                            id="allow-top-up"
                            label="Allow loan top-ups"
                            description="Turn this off to prevent new top-up applications for this company."
                            checked={rules.allow_top_up}
                            onChange={(checked) => setRules({ ...rules, allow_top_up: checked })}
                        />
                    </div>

                    <div className={`grid gap-5 md:grid-cols-2 ${rules.allow_top_up ? "" : "opacity-60"}`}>
                        <NumberRule
                            id="top-up-paid-percent"
                            label="Minimum existing loan paid (%)"
                            description="Percentage of the current loan that must already be paid before normal top-up eligibility."
                            value={rules.top_up_min_paid_percent}
                            min={0}
                            max={100}
                            step="0.001"
                            disabled={!rules.allow_top_up}
                            onChange={(value) => setRules({ ...rules, top_up_min_paid_percent: value })}
                        />
                        <NumberRule
                            id="top-up-paid-installments"
                            label="Minimum paid instalments"
                            description="Number of fully paid instalments required in addition to the percentage threshold. Use 0 to disable this threshold."
                            value={rules.top_up_min_paid_installments}
                            min={0}
                            max={120}
                            step="1"
                            disabled={!rules.allow_top_up}
                            onChange={(value) => setRules({ ...rules, top_up_min_paid_installments: value })}
                        />
                    </div>

                    <div className={`grid gap-3 lg:grid-cols-3 ${rules.allow_top_up ? "" : "opacity-60"}`}>
                        <RuleCheckbox
                            id="top-up-positive-history"
                            label="Require positive repayment history"
                            description="Block normal eligibility when the current loan is defaulted or overdue."
                            checked={rules.top_up_require_positive_history}
                            disabled={!rules.allow_top_up}
                            onChange={(checked) => setRules({ ...rules, top_up_require_positive_history: checked })}
                        />
                        <RuleCheckbox
                            id="top-up-settle-balance"
                            label="Settle existing loan balance"
                            description="Treat the top-up as a replacement facility that first settles the old balance."
                            checked={rules.top_up_settle_existing_balance}
                            disabled={!rules.allow_top_up}
                            onChange={(checked) => setRules({ ...rules, top_up_settle_existing_balance: checked })}
                        />
                        <RuleCheckbox
                            id="top-up-owner-exception"
                            label="Allow owner exceptions"
                            description="Permit a company owner to approve a documented exception when the normal threshold is not met."
                            checked={rules.top_up_owner_exception_enabled}
                            disabled={!rules.allow_top_up}
                            onChange={(checked) => setRules({ ...rules, top_up_owner_exception_enabled: checked })}
                        />
                    </div>

                    <Alert>
                        <ShieldCheck className="h-4 w-4" />
                        <AlertTitle>How LoanHub will apply this policy</AlertTitle>
                        <AlertDescription>
                            {ruleSummary} {rules.allow_top_up && rules.top_up_settle_existing_balance
                                ? "The old outstanding balance is included in the replacement facility before additional cash is calculated."
                                : ""} {rules.allow_top_up && rules.top_up_owner_exception_enabled
                                ? "A failed normal threshold may be routed for a documented company-owner exception where policy permits."
                                : ""}
                        </AlertDescription>
                    </Alert>

                    <div className="flex flex-col-reverse gap-3 border-t pt-5 sm:flex-row sm:items-center sm:justify-between">
                        <p className="text-xs leading-5 text-muted-foreground">
                            Saving creates a new company policy version. Existing assessment snapshots remain auditable under the version used at the time.
                        </p>
                        <div className="flex shrink-0 gap-2">
                            <Button type="button" variant="outline" disabled={saving} onClick={() => void load()}>
                                <RefreshCcw className="h-4 w-4" /> Reload
                            </Button>
                            <LoadingButton type="submit" loading={saving} loadingText="Saving rules…">
                                <Save className="h-4 w-4" /> Save top-up rules
                            </LoadingButton>
                        </div>
                    </div>
                </CardContent>
            </Card>
        </form>
    );
}

function NumberRule({
    id,
    label,
    description,
    value,
    min,
    max,
    step,
    disabled,
    onChange,
}: {
    id: string;
    label: string;
    description: string;
    value: number;
    min: number;
    max: number;
    step: string;
    disabled?: boolean;
    onChange: (value: number) => void;
}) {
    return (
        <div className="rounded-2xl border bg-card p-4">
            <Label htmlFor={id} className="font-black">{label}</Label>
            <p className="mt-1 min-h-10 text-xs leading-5 text-muted-foreground">{description}</p>
            <Input
                id={id}
                className="mt-3"
                type="number"
                min={min}
                max={max}
                step={step}
                disabled={disabled}
                value={Number.isFinite(value) ? value : 0}
                onChange={(event) => onChange(Number(event.target.value))}
            />
        </div>
    );
}

function RuleCheckbox({
    id,
    label,
    description,
    checked,
    disabled,
    onChange,
}: {
    id: string;
    label: string;
    description: string;
    checked: boolean;
    disabled?: boolean;
    onChange: (checked: boolean) => void;
}) {
    return (
        <label htmlFor={id} className="flex cursor-pointer items-start gap-3 rounded-2xl border bg-card p-4">
            <Checkbox
                id={id}
                className="mt-0.5"
                checked={checked}
                disabled={disabled}
                onCheckedChange={(value) => onChange(Boolean(value))}
            />
            <span>
                <span className="block text-sm font-black">{label}</span>
                <span className="mt-1 block text-xs leading-5 text-muted-foreground">{description}</span>
            </span>
        </label>
    );
}
