"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Check, Clipboard, KeyRound, Loader2, RefreshCcw, Save, ShieldCheck, UserRoundCog } from "lucide-react";

import {
    createCompanyOwnerTemporaryPassword,
    getCompanyOwnerAccount,
    updateCompanyOwnerAccount,
    type CompanyOwnerAccount,
} from "@/api/companyManagement";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import type { LoanCompany } from "@/store/slices/companiesSlice";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

type Props = {
    company: LoanCompany | null;
    open: boolean;
    onOpenChange: (open: boolean) => void;
};

export function CompanyOwnerAccessDialog({ company, open, onOpenChange }: Props) {
    const [account, setAccount] = useState<CompanyOwnerAccount | null>(null);
    const [phone, setPhone] = useState("");
    const [email, setEmail] = useState("");
    const [isActive, setIsActive] = useState(true);
    const [temporaryPassword, setTemporaryPassword] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [resetting, setResetting] = useState(false);
    const [copied, setCopied] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const load = useCallback(async () => {
        if (!company) return;
        setLoading(true);
        setError(null);
        try {
            const next = await getCompanyOwnerAccount(company.id);
            setAccount(next);
            setPhone(next.phone);
            setEmail(next.email ?? "");
            setIsActive(next.is_active);
        } catch (caught: unknown) {
            setAccount(null);
            setError(getErrorMessage(caught, "The company-owner account could not be loaded."));
        } finally {
            setLoading(false);
        }
    }, [company]);

    useEffect(() => {
        if (!open) return;
        setTemporaryPassword(null);
        setCopied(false);
        void load();
    }, [load, open]);

    async function save(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!company || !account || saving) return;
        if (phone.trim().length < 8) {
            setError("Enter a valid owner phone number.");
            return;
        }

        setSaving(true);
        setError(null);
        try {
            const updated = await updateCompanyOwnerAccount(company.id, {
                phone: phone.trim(),
                email: email.trim() || null,
                is_active: isActive,
            });
            setAccount(updated);
            setPhone(updated.phone);
            setEmail(updated.email ?? "");
            setIsActive(updated.is_active);
            toast.success("Company-owner login details updated. Existing sessions were revoked.");
        } catch (caught: unknown) {
            setError(getErrorMessage(caught, "The login details could not be updated."));
        } finally {
            setSaving(false);
        }
    }

    async function resetPassword() {
        if (!company || resetting) return;
        if (!window.confirm(`Create a new temporary password for ${account?.full_name ?? "this company owner"}? Existing sessions will be signed out.`)) {
            return;
        }

        setResetting(true);
        setTemporaryPassword(null);
        setCopied(false);
        setError(null);
        try {
            const result = await createCompanyOwnerTemporaryPassword(company.id);
            setTemporaryPassword(result.temporary_password);
            setAccount((current) => current ? { ...current, must_change_password: true } : current);
            toast.success("Temporary password created. It will only be shown in this dialog.");
        } catch (caught: unknown) {
            setError(getErrorMessage(caught, "A temporary password could not be created."));
        } finally {
            setResetting(false);
        }
    }

    async function copyTemporaryPassword() {
        if (!temporaryPassword) return;
        try {
            await navigator.clipboard.writeText(temporaryPassword);
            setCopied(true);
            toast.success("Temporary password copied.");
        } catch {
            toast.error("Copy failed. Select the password manually.");
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-2xl">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <UserRoundCog className="h-5 w-5 text-primary" /> Manage owner login
                    </DialogTitle>
                    <DialogDescription>
                        Assist the owner of {company?.name ?? "this company"} without viewing their existing password.
                    </DialogDescription>
                </DialogHeader>

                {loading ? (
                    <div className="flex min-h-52 items-center justify-center gap-2 text-sm font-bold text-muted-foreground">
                        <Loader2 className="h-5 w-5 animate-spin" /> Loading owner account…
                    </div>
                ) : error && !account ? (
                    <Alert variant="destructive">
                        <AlertTitle>Owner account unavailable</AlertTitle>
                        <AlertDescription className="space-y-3">
                            <p>{error}</p>
                            <Button type="button" size="sm" variant="outline" onClick={() => void load()}>
                                <RefreshCcw className="h-4 w-4" /> Retry
                            </Button>
                        </AlertDescription>
                    </Alert>
                ) : account ? (
                    <form onSubmit={save} className="space-y-5">
                        <div className="rounded-2xl border bg-muted/25 p-4">
                            <p className="font-black">{account.full_name}</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                                Company owner · {account.is_verified ? "Verified account" : "Verification pending"}
                            </p>
                        </div>

                        {error ? (
                            <div className="rounded-xl border border-destructive/30 bg-destructive/10 p-3 text-sm font-semibold text-destructive">
                                {error}
                            </div>
                        ) : null}

                        <div className="grid gap-4 sm:grid-cols-2">
                            <div className="space-y-2">
                                <Label htmlFor="owner-phone">Login phone number</Label>
                                <Input
                                    id="owner-phone"
                                    value={phone}
                                    onChange={(event) => setPhone(event.target.value)}
                                    className="h-11 rounded-xl"
                                    required
                                />
                            </div>
                            <div className="space-y-2">
                                <Label htmlFor="owner-email">Recovery email</Label>
                                <Input
                                    id="owner-email"
                                    type="email"
                                    value={email}
                                    onChange={(event) => setEmail(event.target.value)}
                                    className="h-11 rounded-xl"
                                />
                            </div>
                        </div>

                        <label className="flex cursor-pointer items-start gap-3 rounded-2xl border p-4">
                            <Checkbox checked={isActive} onCheckedChange={(value) => setIsActive(Boolean(value))} />
                            <span>
                                <span className="block text-sm font-black">Account active</span>
                                <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                                    Turning this off blocks sign-in. Saving login changes revokes all existing sessions.
                                </span>
                            </span>
                        </label>

                        <Alert>
                            <ShieldCheck className="h-4 w-4" />
                            <AlertTitle>Password privacy</AlertTitle>
                            <AlertDescription>
                                LoanHub never reveals the existing password. Create a temporary password only when identity has been verified through your support process.
                            </AlertDescription>
                        </Alert>

                        {temporaryPassword ? (
                            <div className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-amber-950 dark:border-amber-900 dark:bg-amber-950/30 dark:text-amber-100">
                                <p className="text-sm font-black">One-time temporary password</p>
                                <div className="mt-3 flex items-center gap-2">
                                    <code className="min-w-0 flex-1 overflow-x-auto rounded-xl border bg-background px-3 py-3 text-base font-black text-foreground">
                                        {temporaryPassword}
                                    </code>
                                    <Button type="button" variant="outline" size="icon" onClick={() => void copyTemporaryPassword()}>
                                        {copied ? <Check className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
                                    </Button>
                                </div>
                                <p className="mt-3 text-xs leading-5">
                                    Share it securely now. It will not be shown again, and the owner must replace it immediately after login.
                                </p>
                            </div>
                        ) : null}

                        <div className="flex flex-col gap-3 border-t pt-5 sm:flex-row sm:items-center sm:justify-between">
                            <Button type="button" variant="outline" disabled={resetting || saving} onClick={() => void resetPassword()}>
                                {resetting ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
                                {resetting ? "Creating…" : "Create temporary password"}
                            </Button>
                            <DialogFooter className="gap-2 sm:gap-2">
                                <Button type="button" variant="ghost" disabled={saving || resetting} onClick={() => onOpenChange(false)}>
                                    Close
                                </Button>
                                <Button type="submit" disabled={saving || resetting}>
                                    {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                                    {saving ? "Saving…" : "Save login details"}
                                </Button>
                            </DialogFooter>
                        </div>
                    </form>
                ) : null}
            </DialogContent>
        </Dialog>
    );
}
