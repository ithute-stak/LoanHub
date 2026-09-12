"use client";

import { FormEvent, useMemo, useState } from "react";
import { Eye, EyeOff, KeyRound, Loader2, ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";

import { changePassword } from "@/api/auth";
import { Input } from "@/components/ui/input";
import { getErrorMessage } from "@/utils/apiError";
import { toast } from "@/utils/toast";
import { useAppDispatch, useAppSelector } from "@/store/hooks";
import { logoutUser } from "@/store/slices/authSlice";

export default function ChangePasswordPage() {
    const router = useRouter();
    const dispatch = useAppDispatch();
    const user = useAppSelector((state) => state.auth.user);
    const [currentPassword, setCurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [showPasswords, setShowPasswords] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const passwordReady = useMemo(
        () =>
            currentPassword.length >= 6
            && newPassword.length >= 10
            && newPassword === confirmPassword
            && /[a-z]/.test(newPassword)
            && /[A-Z]/.test(newPassword)
            && /\d/.test(newPassword),
        [confirmPassword, currentPassword, newPassword],
    );

    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (!passwordReady || submitting) return;

        setSubmitting(true);
        setError(null);
        try {
            const result = await changePassword({
                current_password: currentPassword,
                new_password: newPassword,
            });
            toast.success(result.message);
            await dispatch(logoutUser());
            router.replace("/login");
        } catch (caught: unknown) {
            setError(getErrorMessage(caught, "The password could not be changed."));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
            <section className="w-full max-w-xl overflow-hidden rounded-3xl border bg-card shadow-xl">
                <div className="border-b bg-gradient-to-r from-primary/10 via-card to-emerald-500/10 p-6 sm:p-8">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
                        <KeyRound className="h-7 w-7" />
                    </div>
                    <h1 className="mt-5 text-3xl font-black">Create your private password</h1>
                    <p className="mt-2 leading-7 text-muted-foreground">
                        {user?.must_change_password
                            ? "The system owner issued a temporary password. Replace it before using LoanHub."
                            : "Change your LoanHub password and sign in again securely."}
                    </p>
                </div>

                <form onSubmit={submit} className="space-y-5 p-6 sm:p-8">
                    {error ? (
                        <div className="rounded-2xl border border-destructive/30 bg-destructive/10 p-4 text-sm font-semibold text-destructive">
                            {error}
                        </div>
                    ) : null}

                    <PasswordField
                        id="current-password"
                        label="Temporary or current password"
                        value={currentPassword}
                        show={showPasswords}
                        autoComplete="current-password"
                        onChange={setCurrentPassword}
                    />
                    <PasswordField
                        id="new-password"
                        label="New password"
                        value={newPassword}
                        show={showPasswords}
                        autoComplete="new-password"
                        onChange={setNewPassword}
                    />
                    <PasswordField
                        id="confirm-password"
                        label="Confirm new password"
                        value={confirmPassword}
                        show={showPasswords}
                        autoComplete="new-password"
                        onChange={setConfirmPassword}
                    />

                    <button
                        type="button"
                        onClick={() => setShowPasswords((current) => !current)}
                        className="inline-flex items-center gap-2 text-sm font-bold text-primary"
                    >
                        {showPasswords ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                        {showPasswords ? "Hide passwords" : "Show passwords"}
                    </button>

                    <div className="rounded-2xl border bg-muted/30 p-4 text-sm leading-6 text-muted-foreground">
                        <p className="flex items-center gap-2 font-bold text-foreground">
                            <ShieldCheck className="h-4 w-4 text-primary" /> Password requirements
                        </p>
                        <p className="mt-1">At least 10 characters with uppercase, lowercase and a number.</p>
                    </div>

                    <button
                        type="submit"
                        disabled={!passwordReady || submitting}
                        className="inline-flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-primary px-5 font-black text-primary-foreground disabled:opacity-50"
                    >
                        {submitting ? <Loader2 className="h-5 w-5 animate-spin" /> : <KeyRound className="h-5 w-5" />}
                        {submitting ? "Changing password…" : "Change password and sign in again"}
                    </button>
                </form>
            </section>
        </main>
    );
}

function PasswordField({
    id,
    label,
    value,
    show,
    autoComplete,
    onChange,
}: {
    id: string;
    label: string;
    value: string;
    show: boolean;
    autoComplete: string;
    onChange: (value: string) => void;
}) {
    return (
        <label htmlFor={id} className="block space-y-2">
            <span className="text-sm font-black">{label}</span>
            <Input
                id={id}
                type={show ? "text" : "password"}
                value={value}
                autoComplete={autoComplete}
                onChange={(event) => onChange(event.target.value)}
                className="h-12 rounded-xl"
            />
        </label>
    );
}
