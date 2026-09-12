"use client";


import { Input } from "@/components/ui/input";
import { LoadingButton } from "@/components/ui/loading-button";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, KeyRound, ShieldCheck } from "lucide-react";
import { type FormEvent, useState } from "react";

import { requestPasswordReset } from "@/api/auth";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";

export default function ForgotPasswordPage() {
    const [identifier, setIdentifier] = useState("");
    const [submitting, setSubmitting] = useState(false);
    const [reference, setReference] = useState<string | null>(null);

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!identifier.trim() || submitting) return;
        setSubmitting(true);
        try {
            const result = await requestPasswordReset(identifier.trim());
            setReference(result.request_reference);
            toast.success("Secure account-recovery request submitted");
        } catch (error) {
            toast.error(getErrorMessage(error, "Could not submit the recovery request"));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <main className="flex min-h-screen items-center justify-center bg-muted/20 p-4 sm:p-8">
            <section className="w-full max-w-xl overflow-hidden rounded-3xl border bg-card shadow-2xl">
                <div className="bg-gradient-to-br from-primary/15 via-background to-emerald-500/10 p-7 sm:p-9">
                    <Link href="/login" className="inline-flex items-center gap-2 text-sm font-black text-muted-foreground hover:text-foreground">
                        <ArrowLeft className="h-4 w-4" /> Back to login
                    </Link>
                    <div className="mt-7 flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
                        <KeyRound className="h-7 w-7" />
                    </div>
                    <h1 className="mt-5 text-3xl font-black">Restore account access</h1>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                        Enter the phone number or email linked to your LoanHub account. Platform support receives a private request without exposing whether an account exists.
                    </p>
                </div>

                {reference ? (
                    <div className="p-7 sm:p-9">
                        <div className="flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-emerald-800 dark:border-emerald-900 dark:bg-emerald-950/30 dark:text-emerald-300">
                            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
                            <div>
                                <p className="font-black">Request received</p>
                                <p className="mt-1 text-sm leading-6">Use reference <strong>{reference}</strong> when platform support contacts you. Never share your password, mobile-money PIN, private key or one-time code.</p>
                            </div>
                        </div>
                        <Link href="/login" className="mt-6 inline-flex h-12 w-full items-center justify-center rounded-xl bg-primary px-5 text-sm font-black text-primary-foreground">Return to login</Link>
                    </div>
                ) : (
                    <form onSubmit={submit} className="space-y-5 p-7 sm:p-9">
                        <label className="block">
                            <span className="mb-2 block text-sm font-black">Phone number or email</span>
                            <Input value={identifier} onChange={(event) => setIdentifier(event.target.value)} autoComplete="username" required className="h-12 w-full rounded-xl border bg-background px-4 text-sm outline-none focus:border-primary focus:ring-2 focus:ring-primary/20" placeholder="+266 5800 0000 or name@example.com" />
                        </label>
                        <div className="flex items-start gap-3 rounded-2xl border bg-muted/30 p-4 text-xs leading-5 text-muted-foreground">
                            <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                            LoanHub does not send existing passwords. An authorised platform owner verifies identity and guides the secure recovery process.
                        </div>
                        <LoadingButton type="submit" loading={submitting} loadingText="Submitting request..." disabled={!identifier.trim()} className="h-12 w-full">
                            Submit recovery request
                        </LoadingButton>
                    </form>
                )}
            </section>
        </main>
    );
}
