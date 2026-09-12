"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { FileSignature, RefreshCcw, Save, ShieldCheck } from "lucide-react";

import {
    loanSettingsApi,
    type CompanyLoanSettings,
    type ContractTemplateStyleOption,
} from "@/api/loan-settings";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { LoadingButton } from "@/components/ui/loading-button";
import type { ContractTemplateStyle } from "@/types/origination";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";


type Props = {
    canManage: boolean;
};

export function CompanyLoanSettingsPanel({ canManage }: Props) {
    const [settings, setSettings] = useState<CompanyLoanSettings | null>(null);
    const [styles, setStyles] = useState<ContractTemplateStyleOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setLoadError(null);
        try {
            const [currentSettings, availableStyles] = await Promise.all([
                loanSettingsApi.getSettings(),
                loanSettingsApi.listContractTemplateStyles(),
            ]);
            setSettings(currentSettings);
            setStyles(availableStyles);
        } catch (error: unknown) {
            setLoadError(getErrorMessage(error, "Loan settings could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        const timer = window.setTimeout(() => void load(), 0);
        return () => window.clearTimeout(timer);
    }, [load]);

    async function save(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!canManage || !settings) return;

        setSaving(true);
        try {
            const updated = await loanSettingsApi.updateSettings({
                default_contract_template_style: settings.default_contract_template_style,
            });
            setSettings(updated);
            toast.success("Loan settings updated", {
                description: "New loan contracts will now use the selected company default template.",
            });
        } catch (error: unknown) {
            toast.error(getErrorMessage(error, "Loan settings could not be saved."));
        } finally {
            setSaving(false);
        }
    }

    if (loading) {
        return (
            <Card className="rounded-3xl">
                <CardContent className="flex min-h-52 items-center justify-center p-8 text-sm font-bold text-muted-foreground">
                    Loading this company&apos;s loan settings…
                </CardContent>
            </Card>
        );
    }

    if (loadError || !settings) {
        return (
            <Alert variant="destructive">
                <FileSignature className="h-4 w-4" />
                <AlertTitle>Loan settings unavailable</AlertTitle>
                <AlertDescription className="space-y-3">
                    <p>{loadError ?? "The company loan settings could not be loaded."}</p>
                    <Button type="button" size="sm" variant="outline" onClick={() => void load()}>
                        <RefreshCcw className="h-4 w-4" /> Retry
                    </Button>
                </AlertDescription>
            </Alert>
        );
    }

    const selectedStyle = styles.find(
        (item) => item.value === settings.default_contract_template_style,
    );

    return (
        <form onSubmit={save} className="space-y-6">
            <Card className="overflow-hidden rounded-3xl border-primary/20">
                <CardHeader className="border-b bg-gradient-to-r from-primary/10 via-card to-blue-500/10">
                    <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                            <CardTitle className="flex items-center gap-2">
                                <FileSignature className="h-5 w-5 text-primary" />
                                Company loan settings
                            </CardTitle>
                            <CardDescription className="mt-2 max-w-3xl leading-6">
                                Choose the contract template LoanHub should use automatically when this company generates a new loan contract. This setting belongs only to the active company.
                            </CardDescription>
                        </div>
                        <Badge variant="outline" className="w-fit">
                            {selectedStyle?.label ?? "Contract template"}
                        </Badge>
                    </div>
                </CardHeader>

                <CardContent className="space-y-6 p-5 sm:p-7">
                    {!canManage && (
                        <Alert>
                            <ShieldCheck className="h-4 w-4" />
                            <AlertTitle>Read-only company setting</AlertTitle>
                            <AlertDescription>
                                Only the company owner or company administrator can change the default loan contract.
                            </AlertDescription>
                        </Alert>
                    )}

                    <div className="max-w-2xl rounded-2xl border bg-card p-5">
                        <Label htmlFor="default-loan-contract" className="font-black">
                            Default loan contract
                        </Label>
                        <p className="mt-1 text-xs leading-5 text-muted-foreground">
                            This template is selected automatically when staff generate a contract. A specifically selected template can still be used when a workflow explicitly overrides the default.
                        </p>
                        <select
                            id="default-loan-contract"
                            value={settings.default_contract_template_style}
                            disabled={!canManage || saving}
                            onChange={(event) => setSettings({
                                ...settings,
                                default_contract_template_style: event.target.value as ContractTemplateStyle,
                            })}
                            className="mt-4 flex h-11 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-semibold shadow-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                            {styles.map((style) => (
                                <option key={style.value} value={style.value}>
                                    {style.label}
                                </option>
                            ))}
                        </select>
                    </div>

                    <Alert>
                        <FileSignature className="h-4 w-4" />
                        <AlertTitle>How the default is applied</AlertTitle>
                        <AlertDescription>
                            The choice applies to future contract generation for this company. Existing generated or signed contracts keep the template and legal snapshot that were recorded when they were created.
                        </AlertDescription>
                    </Alert>

                    <div className="flex flex-col-reverse gap-3 border-t pt-5 sm:flex-row sm:items-center sm:justify-between">
                        <p className="text-xs leading-5 text-muted-foreground">
                            Default: LoanHub Standard. Changing this setting does not rewrite existing contracts.
                        </p>
                        <div className="flex shrink-0 gap-2">
                            <Button type="button" variant="outline" disabled={saving} onClick={() => void load()}>
                                <RefreshCcw className="h-4 w-4" /> Reload
                            </Button>
                            {canManage && (
                                <LoadingButton type="submit" loading={saving} loadingText="Saving…">
                                    <Save className="h-4 w-4" /> Save loan settings
                                </LoadingButton>
                            )}
                        </div>
                    </div>
                </CardContent>
            </Card>
        </form>
    );
}
